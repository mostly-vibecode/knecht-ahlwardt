import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import json
import os
import uuid
from src.utils.helpers import get_target_timezone
from src.utils.traffic import check_traffic_debug
from src.utils.hof import HallOfFame


class ReminderView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None) # Persistent view
        self.cog = cog

    @discord.ui.button(label="Place Panel", style=discord.ButtonStyle.primary, emoji="➕", custom_id="reminder_place")
    async def place_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_place_interaction(interaction)

    @discord.ui.button(label="Fix Panels", style=discord.ButtonStyle.success, emoji="✅", custom_id="reminder_fix")
    async def fix_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_fix_interaction(interaction, is_reminder=True)

class Panels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracking_data = {
            "placed": 0, # Legacy
            "fixed_this_hour": 0
        }
        
        self.active_panels = [] # List of panel objects
        self.daily_batteries = {} # { user_id: count }
        
        self.daily_work = {
            "placed": {}, # { user_id: count }
            "fixes": {}   # { user_id: count }
        }
        self.daily_profit = {} # { user_id: amount }
        self.daily_batteries = {} # { user_id: count }
        
        self.lifetime_profit = {} # { user_id: amount }
        self.lifetime_work = {
             "placed": {},
             "fixes": {}
        }
        self.history = [] # List of archived daily stats
        self.last_reset_date = None
        self.tracking_message_id = None
        self.data_file = "data/panels.json"
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        
        self.settings_file = "config/settings.json"
        self.settings = {"panel_liveduration": 60}
        self.load_settings()

        self.hof = HallOfFame("config/mechanics.json")
        self.load_stats()

    async def cog_load(self):
        """Register persistent views on load."""
        self.bot.add_view(ReminderView(self))
        # Ensure reset check happens on load
        self.check_daily_reset()
        
    def load_settings(self):
        """Load settings from JSON."""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    self.settings = json.load(f)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save_stats(self):
        """Save daily_stats to JSON file."""
        try:
            with open(self.data_file, 'w') as f:
                data = {
                    "active_panels": self.active_panels,
                    "daily_batteries": self.daily_batteries,
                    "daily_work": self.daily_work,
                    "daily_profit": self.daily_profit,
                    "lifetime_profit": self.lifetime_profit,
                    "lifetime_work": self.lifetime_work,
                    "history": self.history,
                    "last_reset_date": self.last_reset_date,
                    "tracking_message_id": self.tracking_message_id
                }
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving stats: {e}")

    def load_stats(self):
        """Load daily_stats from JSON file."""
        if not os.path.exists(self.data_file):
            return

        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                
                # Load active panels
                self.active_panels = data.get("active_panels", [])
                
                self.daily_batteries = {str(k): v for k, v in data.get("daily_batteries", {}).items()}
                
                # Load Work/Profit
                # Migration from old daily_stats to daily_work if needed
                if "daily_stats" in data:
                    self.daily_work = data["daily_stats"]
                    if "placed" in self.daily_work and isinstance(self.daily_work["placed"], int):
                         self.daily_work["placed"] = {} # Hard reset invalid type
                else:
                    self.daily_work = data.get("daily_work", { "placed": {}, "fixes": {} })
                    # Type safety keys
                    self.daily_work["placed"] = {str(k): v for k, v in self.daily_work.get("placed", {}).items()}
                    self.daily_work["fixes"] = {str(k): v for k, v in self.daily_work.get("fixes", {}).items()}

                self.daily_profit = {str(k): v for k, v in data.get("daily_profit", {}).items()}
                self.lifetime_profit = {str(k): v for k, v in data.get("lifetime_profit", {}).items()}
                
                # Lifetime Work
                lw = data.get("lifetime_work", { "placed": {}, "fixes": {} })
                self.lifetime_work = {
                    "placed": {str(k): v for k, v in lw.get("placed", {}).items()},
                    "fixes": {str(k): v for k, v in lw.get("fixes", {}).items()}
                }

                self.history = data.get("history", [])
                self.last_reset_date = data.get("last_reset_date")

                # Load tracking message ID
                self.tracking_message_id = data.get("tracking_message_id")
                        
        except Exception as e:
            print(f"Error loading stats: {e}") 
            import traceback
            traceback.print_exc()


    def process_place(self, user):
        """Logic for placing a panel."""
        tz = get_target_timezone()
        now = datetime.now(tz)
        
        # Create new panel
        liveduration = self.settings.get("panel_liveduration", 60)
        panel = {
            "id": uuid.uuid4().hex,
            "placed_by": user.id,
            "placed_by_name": user.display_name,
            "placed_at_iso": now.isoformat(),
            "remaining_minutes": liveduration,
            "interactions": [] 
        }
        
        # Add Interaction
        panel["interactions"].append({
            "user_id": str(user.id),
            "action": "place",
            "timestamp": now.isoformat()
        })
        
        self.active_panels.append(panel)
        self.check_daily_reset() # Check before modifying stats

        # Update Daily Work (Placed)
        if str(user.id) not in self.daily_work["placed"]:
            self.daily_work["placed"][str(user.id)] = 0
        self.daily_work["placed"][str(user.id)] += 1
        
        self.save_stats()
        return panel

    async def handle_place_interaction(self, interaction: discord.Interaction):
        """Shared handler for place buttons."""
        user = interaction.user
        panel = self.process_place(user)
        
        # Calculate ETA
        tz = get_target_timezone()
        placed_at = datetime.fromisoformat(panel["placed_at_iso"])
        # Assuming liveduration is in minutes
        ready_at = placed_at.replace(minute=(placed_at.minute + panel["remaining_minutes"]) % 60)
        # Handle hour rollover if needed, though simple minute addition for display might be tricky if it spans hours.
        # Better:
        from datetime import timedelta
        ready_time = placed_at + timedelta(minutes=panel["remaining_minutes"])
        
        # Ephemeral Message
        await interaction.response.send_message(
            f"✅ **Panel Placed!** If repaired every hour, it will be done at approx. **{ready_time.strftime('%H:%M')}**.",
            ephemeral=True
        )
        
        # Update the view source if possible (if it was the main tracking view)
        # Note: ReminderView messages don't update themselves usually, but PanelView messages do.
        # We can try to update the main tracking message if it exists.
        await self.update_tracking_message()

    def calculate_panel_state(self, panel):
        """
        Calculate the real-time state of a panel.
        Returns: { 
            "remaining_minutes": int, 
            "total_delay": int, 
            "expiry_iso": str 
        }
        """
        tz = get_target_timezone()
        now = datetime.now(tz)
        placed_at = datetime.fromisoformat(panel["placed_at_iso"])
        
        # Base Duration
        liveduration = self.settings.get("panel_liveduration", 60)
        
        # Calculate Penalties (Delays)
        # Iterate hour by hour from placement to now
        total_delay_minutes = 0
        
        # Start checking from the *next* hour after placement
        # Example: Placed 10:25. 
        # Window 10:xx -> No maintenance needed (just placed).
        # Window 11:xx -> Repair needed between 11:30-11:59.
        
        check_time = placed_at.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        while check_time < now:
            # Define the repair window for this hour (XX:30 - XX:59)
            window_start = check_time.replace(minute=30)
            window_end = check_time.replace(minute=59, second=59)
            
            # If we haven't reached the start of the window yet in real time, break
            if window_start > now:
                break
                
            # Check if this window was missed
            # We look for a 'fix' interaction within this window
            
            # Optimization: If the panel is already "finished" by logic before this window, stop?
            # Actually, per story, if nobody fixes it, it just delays.
            
            # Was it fixed in this window?
            is_fixed = False
            for i in panel.get("interactions", []):
                if i["action"] == "fix":
                    i_time = datetime.fromisoformat(i["timestamp"])
                    if window_start <= i_time <= window_end:
                        is_fixed = True
                        break
            
            if not is_fixed:
                # If checking a past completed window, it's a miss
                if now > window_end:
                     total_delay_minutes += 60
            
            check_time += timedelta(hours=1)
            
        # Finish Time = Placed + Duration + Delay
        finish_time = placed_at + timedelta(minutes=liveduration + total_delay_minutes)
        remaining = (finish_time - now).total_seconds() / 60
        
        return {
            "remaining_minutes": int(remaining),
            "total_delay": total_delay_minutes,
            "expiry_iso": finish_time.isoformat()
        }

    def process_fix(self, user):
        """Standardized logic for fixing panels (Maintain or Collect)."""
        tz = get_target_timezone()
        now = datetime.now(tz)
        
        eligible_count = 0
        collected_count = 0
        
        # Identify eligible panels
        self.check_daily_reset()
        
        # "Fix" logic: 
        # A fix is valid if it's in the XX:30 - XX:59 window OR if the panel is ready for collection.
        # Check simple time window for eligibility:
        is_maintenance_window = (now.minute >= 30)
        
        for panel in self.active_panels:
            state = self.calculate_panel_state(panel)
            remaining = state["remaining_minutes"]
            
            # Conditions to interact:
            # 1. Ready to Collect: remaining <= 0
            # 2. Maintenance: remaining > 0 AND is_maintenance_window (XX:30+)
            
            is_eligible = False
            if remaining <= 0:
                is_eligible = True # Collect
            elif is_maintenance_window:
                is_eligible = True # Maintain
            
            if is_eligible:
                eligible_count += 1
                
                # Check duplication? 
                # If we already fixed in THIS window, do we fix again?
                # Story says: "p3 fixes both panel on 14:34 -> ETAs stay true"
                # Implies we just record it.
                
                # Record Interaction
                panel["interactions"].append({
                    "user_id": str(user.id),
                    "action": "fix",
                    "timestamp": now.isoformat()
                })
                
                # Re-calculate state to see if it pushed us to "Finished" or if it was already finished
                # Actually, if it WAS <= 0, we just collected it.
                if remaining <= 0:
                    collected_count += 1
        
        new_active_panels = []
        for panel in self.active_panels:
            # Re-calc state to verify if it's REALLY done and collected
            # We rely on the collected_count trigger logic above, but we need to remove them from active list
            # The logic above "if remaining <= 0" was based on PRE-interaction state.
            
            # If we just added a fix to a panel that was <= 0, it means we collected it.
            # We need to distinguish "Collected" vs "Just Maintained"
            
            # Simple check: Was it marked eligible because it was finished?
            # Recalculate state to be sure
            state = self.calculate_panel_state(panel)
            
            # Wait, if we just fixed it, it's a new interaction.
            # If it was <= 0, we want to pop it.
            
            # To avoid race conditions or logic errors, let's look at the timestamps
            # If the panel expiration (finish_time) is in the PAST, and we just fixed it (now),
            # clearly we collected it.
            
            finish_dt = datetime.fromisoformat(state["expiry_iso"])
            
            is_collected = False
            if state["remaining_minutes"] <= 0:
                # It is ready. Did we just fix it?
                # Look for a fix timestamp that is > finish_dt?
                # Or just checking if we performed an action in this call is enough?
                # We used "eligible_count" above.
                
                # Let's check if the LAST interaction was a fix by THIS user at THIS time (approx)
                last = panel["interactions"][-1]
                if last["user_id"] == str(user.id) and last["action"] == "fix":
                     # Yes, we just fixed it and it is finished.
                     is_collected = True
            
            if not is_collected:
                new_active_panels.append(panel)
            else:
                # PAYOUT LOGIC (On Collection Only)
                interactions = panel.get("interactions", [])
                total_interactions = len(interactions)
                
                if total_interactions > 0:
                    battery_val = self.hof.mechanics.get("battery_value", 50000)
                    
                    # Count interactions per user
                    user_counts = {}
                    for i in interactions:
                        uid = i["user_id"]
                        user_counts[uid] = user_counts.get(uid, 0) + 1
                        
                    # Distribute
                    for uid, count in user_counts.items():
                        share = int((count / total_interactions) * battery_val)
                        if share > 0:
                             self.daily_profit[uid] = self.daily_profit.get(uid, 0) + share

        self.active_panels = new_active_panels
        
        # Update Battery Counts for Collector
        if collected_count > 0:
             if str(user.id) not in self.daily_batteries:
                self.daily_batteries[str(user.id)] = 0
             self.daily_batteries[str(user.id)] += collected_count

        if eligible_count > 0:
            self.tracking_data["fixed_this_hour"] += 1 
            
            # Update Daily Fixes (Work)
            if str(user.id) not in self.daily_work["fixes"]:
                self.daily_work["fixes"][str(user.id)] = 0
            self.daily_work["fixes"][str(user.id)] += 1
            
            self.save_stats()
            
        return {
            "eligible_count": eligible_count,
            "collected_count": collected_count
        }

    async def handle_fix_interaction(self, interaction: discord.Interaction, is_reminder=False):
        """Shared handler for fix buttons."""
        user = interaction.user
        result = self.process_fix(user)
        eligible_count = result["eligible_count"]
        
        if eligible_count > 0:
             await self.update_tracking_message()
             
             # Group active panels by ETA
             tz = get_target_timezone()
             now = datetime.now(tz)
             
             active_count = len(self.active_panels)
             msg = f"🔧 **Panels Maintained by {user.mention}!**\n"
             
             if active_count > 0:
                 msg += f"Active Panels: **{active_count}**\n"
             else:
                 msg += "All panels collected! 🔋"
                 
             if is_reminder:
                 await interaction.response.send_message(msg)
             else:
                 await interaction.response.send_message(msg, ephemeral=False)
        else:
            await interaction.response.send_message("❌ No panels eligible for maintenance/collection right now.", ephemeral=True)
            
    async def update_tracking_message(self):
        """Helper to update the main persistent message."""
        if self.tracking_message_id:
            # ... (Existing logic mostly same, just updating display)
            try:
                from src.config import TARGET_CHANNEL_ID
                channel = self.bot.get_channel(TARGET_CHANNEL_ID)
                if channel:
                    try:
                        msg = await channel.fetch_message(self.tracking_message_id)
                        embed = msg.embeds[0]
                        embed.description = (
                            f"**Current Status**\n\n"
                            f"☀️ **Active Panels**: {len(self.active_panels)}\n"
                            f"🔧 **Fixed (Hour)**: {self.tracking_data['fixed_this_hour']}\n\n"
                            f"Use buttons below to update."
                        )
                        await msg.edit(embed=embed)
                    except discord.NotFound:
                        self.tracking_message_id = None
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
            
        if str(reaction.emoji) == "✅" and "Panels placed but not fixed!" in reaction.message.content:
            # Legacy Reaction Support
            res = self.process_fix(user)
            if res["eligible_count"] > 0:
                # Removed the "bad" reaction add (🔧)
                # Just update tracking
                await self.update_tracking_message()

    def check_daily_reset(self):
        """Check if we passed 04:00 and need to reset."""
        tz = get_target_timezone()
        now = datetime.now(tz)
        
        if now.hour >= 4:
            target_reset_date = now.date().isoformat()
        else:
            target_reset_date = (now.date() - timedelta(days=1)).isoformat()
            
        if self.last_reset_date != target_reset_date:
            print(f"[Reset] Triggering Daily Reset. Last: {self.last_reset_date}, Target: {target_reset_date}")
            return self.reset_daily_stats(target_reset_date)
        return None

    def reset_daily_stats(self, new_date_str=None):
        """Reset daily stats and save. Returns the archive entry."""
        
        archive_entry = None
        
        # 1. Archive
        if self.daily_work["placed"] or self.daily_work["fixes"] or self.daily_profit:
             archive_entry = {
                 "date": self.last_reset_date or "Unknown",
                 "work": self.daily_work,
                 "profit": self.daily_profit,
                 "batteries": self.daily_batteries
             }
             self.history.append(archive_entry)
        
        # 2. Aggregate Lifetime
        for uid, count in self.daily_work["placed"].items():
            if str(uid) not in self.lifetime_work["placed"]: self.lifetime_work["placed"][str(uid)] = 0
            self.lifetime_work["placed"][str(uid)] += count
            
        for uid, count in self.daily_work["fixes"].items():
            if str(uid) not in self.lifetime_work["fixes"]: self.lifetime_work["fixes"][str(uid)] = 0
            self.lifetime_work["fixes"][str(uid)] += count
            
        for uid, val in self.daily_profit.items():
            if str(uid) not in self.lifetime_profit: self.lifetime_profit[str(uid)] = 0
            self.lifetime_profit[str(uid)] += val

        # 3. Clear Current
        self.daily_work = {
            "placed": {},
            "fixes": {}
        }
        self.daily_profit = {}
        self.daily_batteries = {}
        
        # CRITICAL: CLEAR ACTIVES
        self.active_panels = []
        
        # Update Reset Date
        if new_date_str:
            self.last_reset_date = new_date_str
        else:
             tz = get_target_timezone()
             self.last_reset_date = datetime.now(tz).date().isoformat() # Fallback

        self.save_stats()
        return archive_entry

    def export_stats_file(self):
        """Return the stats file as a discord.File object."""
        if os.path.exists(self.data_file):
            return discord.File(self.data_file, filename="panels_backup.json")
        return None

    @app_commands.command(name='panels_spawn', description="Spawn the panel control dashboard.")
    async def panels_spawn(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Solar Panel Control", 
            description=f"**Current Status**\n\n☀️ **Active Panels**: {len(self.active_panels)}\n🔧 **Fixed (Hour)**: {self.tracking_data['fixed_this_hour']}\n\nUse buttons below to update.", 
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, view=ReminderView(self))
        msg = await interaction.original_response()
        self.tracking_message_id = msg.id
        self.save_stats()


    @app_commands.command(name='panels_collected', description="Reset active panels count to 0 (Debug only).")
    async def panels_collected(self, interaction: discord.Interaction):
        self.active_panels = []
        self.save_stats()
        await interaction.response.send_message("✅ Active panels cleared (Debug).")

    @app_commands.command(name='panels_status', description="Debug traffic and logic.")
    async def panels_status(self, interaction: discord.Interaction):
        tz = get_target_timezone()
        now = datetime.now(tz)
        present, debug_log = check_traffic_debug(interaction.guild)
        
        # New HoF Logic
        leaderboard = self.hof.get_leaderboard(self.daily_work, self.daily_profit, self.daily_batteries)
        
        # --- Value HoF (Realized Profit) ---
        value_hof_lines = []
        for i, (uid, val, details) in enumerate(leaderboard, 1):
             if val > 0:
                value_hof_lines.append(f"{i}. <@{uid}>: **${val}** (Realized Profit)")
        value_hof_str = "\n".join(value_hof_lines) or "None"

        # --- Work HoF (Activity Count) ---
        work_sorted = sorted(leaderboard, key=lambda x: (x[2]['placed'] + x[2]['fixes']), reverse=True)
        work_hof_lines = []
        for i, (uid, _, details) in enumerate(work_sorted, 1):
            total_acts = details['placed'] + details['fixes']
            if total_acts > 0:
                work_hof_lines.append(f"{i}. <@{uid}>: **{total_acts} Acts** (P:{details['placed']} F:{details['fixes']})")
        work_hof_str = "\n".join(work_hof_lines) or "None"
        
        placed_total = sum(d["placed"] for _, _, d in leaderboard)

        # Active Panel Details (Real-Time)
        import math
        panel_lines = []
        for p in self.active_panels:
            pid = p['id'][:6]
            pname = p.get('placed_by_name', 'Unknown')
            
            # Use Helper
            state = self.calculate_panel_state(p)
            rem = state["remaining_minutes"]
            delay = state["total_delay"]
            
            # Interactions Logic
            interactions = p.get('interactions', [])
            fixes_done = len([i for i in interactions if i['action'] == 'fix'])
            
            status_text = f"{rem}m left"
            if delay > 0:
                status_text += f" ({delay}m delay)"
            else:
                status_text += " (On Track)"
                
            panel_lines.append(f"`{pid}` {pname}: {status_text} - {fixes_done} fixes")
        panel_str = "\n".join(panel_lines) or "No active panels."

        status_msg = (
            f"**Status Report**\n"
            f"Time: {now.strftime('%H:%M:%S')}\n"
            f"Traffic Present: {present}\n"
            f"Active Panels: {len(self.active_panels)}\n"
            f"Placed Panels (Daily): {placed_total}\n"
            f"Fixed Panels (Hour): {self.tracking_data['fixed_this_hour']}\n\n"
            f"**☀️ Active Panels Detail**:\n{panel_str}\n\n"
            f"**🏆 Value HoF**:\n{value_hof_str}\n\n"
            f"**🔨 Work HoF**:\n{work_hof_str}\n\n"
            f"**Debug Log**:\n```{debug_log}```"
        )
        await interaction.response.send_message(status_msg, ephemeral=True)

    @app_commands.command(name='panels_hof', description="Show the Daily Hall of Fame ($).")
    async def panels_hof(self, interaction: discord.Interaction):
        leaderboard = self.hof.get_leaderboard(self.daily_work, self.daily_profit, self.daily_batteries)
        
        if not leaderboard:
            await interaction.response.send_message("🏆 **Hall of Fame**: No activity recorded today.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🏆 Daily Performance Hall of Fame", color=0xD4AF37)
        
        description = "**Total Earnings**\n"
        for i, (uid, val, details) in enumerate(leaderboard, 1):
            description += f"**{i}.** <@{uid}> — **${val}**\n"
            
        embed.description = description
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='panels_reset', description="[ADMIN] Reset all daily stats manually.")
    @app_commands.checks.has_permissions(administrator=True)
    async def panels_reset(self, interaction: discord.Interaction):
        self.reset_daily_stats()
        await interaction.response.send_message("✅ Daily stats have been reset.", ephemeral=True)

    @app_commands.command(name='panels_export', description="[ADMIN] Export the current stats JSON.")
    @app_commands.checks.has_permissions(administrator=True)
    async def panels_export(self, interaction: discord.Interaction):
        file = self.export_stats_file()
        if file:
            await interaction.response.send_message("📦 Here is the current `panels.json`:", file=file, ephemeral=True)
        else:
            await interaction.response.send_message("❌ No stats file found.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Panels(bot))
