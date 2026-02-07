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
from src.utils.permissions import check_permissions


class KnechtView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None) # Persistent view
        self.cog = cog

    @discord.ui.button(label="Place Panel", style=discord.ButtonStyle.primary, emoji="➕", custom_id="knecht_place_panel")
    async def place_panel_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_place_interaction(interaction)

    @discord.ui.button(label="Fix Panels", style=discord.ButtonStyle.success, emoji="✅", custom_id="knecht_fix_panels")
    async def fix_panels_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_fix_interaction(interaction, is_reminder=True)

    @discord.ui.button(label="Container", style=discord.ButtonStyle.secondary, emoji="📦", custom_id="knecht_container")
    async def container_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_container_interaction(interaction)

    @discord.ui.button(label="Hafenevent", style=discord.ButtonStyle.danger, emoji="⚓", custom_id="knecht_hafenevent")
    async def hafenevent_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_hafenevent_interaction(interaction)


class Knecht(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tracking_data = {
            "fixed_this_hour": 0
        }
        
        self.active_panels = [] # List of panel objects
        
        # New structure for daily work
        self.daily_work = {
            "placed": {},      # { user_id: count }
            "fixes": {},       # { user_id: count }
            "containers": {},  # { user_id: count }
            "hafenevents": {}  # { user_id: count }
        }
        
        self.daily_profit = {}    # { user_id: amount }
        self.daily_batteries = {} # { user_id: count }
        
        self.lifetime_profit = {} # { user_id: amount }
        self.lifetime_work = {
             "placed": {},
             "fixes": {},
             "containers": {},
             "hafenevents": {}
        }
        
        self.history = [] # List of archived daily stats
        self.last_reset_date = None
        self.tracking_message_id = None
        self.data_file = "data/knecht.json"
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        
        self.settings_file = "config/settings.json"
        self.settings = {"panel_liveduration": 60}
        self.load_settings()

        self.hof = HallOfFame("config/mechanics.json")
        self.load_stats()

    async def cog_load(self):
        """Register persistent views on load."""
        self.bot.add_view(KnechtView(self))
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
        # Migration from panels.json if knecht.json doesn't exist?
        # For now, let's just look for knecht.json, but maybe we should copy panels.json content if it exists and knecht doesn't.
        if not os.path.exists(self.data_file):
            if os.path.exists("data/panels.json"):
                print("Migrating data/panels.json to data/knecht.json...")
                try:
                    with open("data/panels.json", 'r') as f:
                        old_data = json.load(f)
                    
                    # Migrate known fields
                    self.active_panels = old_data.get("active_panels", [])
                    self.daily_batteries = {str(k): v for k, v in old_data.get("daily_batteries", {}).items()}
                    self.daily_profit = {str(k): v for k, v in old_data.get("daily_profit", {}).items()}
                    self.lifetime_profit = {str(k): v for k, v in old_data.get("lifetime_profit", {}).items()}
                    self.history = old_data.get("history", [])
                    self.last_reset_date = old_data.get("last_reset_date")
                    self.tracking_message_id = old_data.get("tracking_message_id")
                    
                    dw = old_data.get("daily_work", {})
                    self.daily_work["placed"] = {str(k): v for k, v in dw.get("placed", {}).items()}
                    self.daily_work["fixes"] = {str(k): v for k, v in dw.get("fixes", {}).items()}
                    
                    lw = old_data.get("lifetime_work", {})
                    self.lifetime_work["placed"] = {str(k): v for k, v in lw.get("placed", {}).items()}
                    self.lifetime_work["fixes"] = {str(k): v for k, v in lw.get("fixes", {}).items()}
                    
                    self.save_stats() # Save as knecht.json
                except Exception as e:
                    print(f"Error migrating stats: {e}")
            return

        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                
                self.active_panels = data.get("active_panels", [])
                self.daily_batteries = {str(k): v for k, v in data.get("daily_batteries", {}).items()}
                
                dw = data.get("daily_work", {})
                self.daily_work = {
                    "placed": {str(k): v for k, v in dw.get("placed", {}).items()},
                    "fixes": {str(k): v for k, v in dw.get("fixes", {}).items()},
                    "containers": {str(k): v for k, v in dw.get("containers", {}).items()},
                    "hafenevents": {str(k): v for k, v in dw.get("hafenevents", {}).items()}
                }

                self.daily_profit = {str(k): v for k, v in data.get("daily_profit", {}).items()}
                self.lifetime_profit = {str(k): v for k, v in data.get("lifetime_profit", {}).items()}
                
                lw = data.get("lifetime_work", {})
                self.lifetime_work = {
                    "placed": {str(k): v for k, v in lw.get("placed", {}).items()},
                    "fixes": {str(k): v for k, v in lw.get("fixes", {}).items()},
                    "containers": {str(k): v for k, v in lw.get("containers", {}).items()},
                    "hafenevents": {str(k): v for k, v in lw.get("hafenevents", {}).items()}
                }

                self.history = data.get("history", [])
                self.last_reset_date = data.get("last_reset_date")
                self.tracking_message_id = data.get("tracking_message_id")
                        
        except Exception as e:
            print(f"Error loading stats: {e}") 
            import traceback
            traceback.print_exc()


    # --- Mechanics Handlers ---

    async def handle_container_interaction(self, interaction: discord.Interaction):
        user = interaction.user
        self.check_daily_reset()
        
        value = self.hof.mechanics.get("wertvoller_container", 90000)
        
        # Update Work
        uid = str(user.id)
        self.daily_work["containers"][uid] = self.daily_work["containers"].get(uid, 0) + 1
        
        # Update Profit
        self.daily_profit[uid] = self.daily_profit.get(uid, 0) + value
        
        self.save_stats()
        
        await interaction.response.send_message(f"📦 **Container Logged!** (+${value:,})", ephemeral=True)
        await self.update_tracking_message()

    async def handle_hafenevent_interaction(self, interaction: discord.Interaction):
        user = interaction.user
        self.check_daily_reset()
        
        value = self.hof.mechanics.get("hafendrop", 24000)
        
        # Update Work
        uid = str(user.id)
        self.daily_work["hafenevents"][uid] = self.daily_work["hafenevents"].get(uid, 0) + 1
        
        # Update Profit
        self.daily_profit[uid] = self.daily_profit.get(uid, 0) + value
        
        self.save_stats()
        
        await interaction.response.send_message(f"⚓ **Hafenevent Logged!** (+${value:,})", ephemeral=True)
        await self.update_tracking_message()

    # --- Panel Logic (Legacy/Specific) ---

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
        uid = str(user.id)
        self.daily_work["placed"][uid] = self.daily_work["placed"].get(uid, 0) + 1
        
        self.save_stats()
        return panel

    async def handle_place_interaction(self, interaction: discord.Interaction):
        """Shared handler for place buttons."""
        user = interaction.user
        panel = self.process_place(user)
        
        tz = get_target_timezone()
        placed_at = datetime.fromisoformat(panel["placed_at_iso"])
        from datetime import timedelta
        ready_time = placed_at + timedelta(minutes=panel["remaining_minutes"])
        
        await interaction.response.send_message(
            f"✅ **Panel Placed!** If repaired every hour, it will be done at approx. **{ready_time.strftime('%H:%M')}**.",
            ephemeral=True
        )
        await self.update_tracking_message()

    def calculate_panel_state(self, panel):
        """Calculate the real-time state of a panel."""
        tz = get_target_timezone()
        now = datetime.now(tz)
        placed_at = datetime.fromisoformat(panel["placed_at_iso"])
        
        liveduration = self.settings.get("panel_liveduration", 60)
        total_delay_minutes = 0
        
        check_time = placed_at.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        while check_time < now:
            window_start = check_time.replace(minute=30)
            window_end = check_time.replace(minute=59, second=59)
            
            if window_start > now:
                break
                
            is_fixed = False
            for i in panel.get("interactions", []):
                if i["action"] == "fix":
                    i_time = datetime.fromisoformat(i["timestamp"])
                    if window_start <= i_time <= window_end:
                        is_fixed = True
                        break
            
            if not is_fixed:
                if now > window_end:
                     total_delay_minutes += 60
            
            check_time += timedelta(hours=1)
            
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
        
        self.check_daily_reset()
        
        is_maintenance_window = (now.minute >= 30)
        
        for panel in self.active_panels:
            state = self.calculate_panel_state(panel)
            remaining = state["remaining_minutes"]
            
            is_eligible = False
            if remaining <= 0:
                is_eligible = True # Collect
            elif is_maintenance_window:
                # Check for duplicate fix in this window
                already_fixed = False
                window_start = now.replace(minute=30, second=0, microsecond=0)
                window_end = now.replace(minute=59, second=59, microsecond=999999)
                
                for i in panel.get("interactions", []):
                    if i["action"] == "fix" and i["user_id"] == str(user.id):
                        i_time = datetime.fromisoformat(i["timestamp"])
                        if window_start <= i_time <= window_end:
                            already_fixed = True
                            break
                            
                if not already_fixed:
                    is_eligible = True # Maintain
            
            if is_eligible:
                eligible_count += 1
                
                panel["interactions"].append({
                    "user_id": str(user.id),
                    "action": "fix",
                    "timestamp": now.isoformat()
                })
                
                if remaining <= 0:
                    collected_count += 1
        
        new_active_panels = []
        for panel in self.active_panels:
            state = self.calculate_panel_state(panel)
            finish_dt = datetime.fromisoformat(state["expiry_iso"])
            
            is_collected = False
            if state["remaining_minutes"] <= 0:
                last = panel["interactions"][-1]
                if last["user_id"] == str(user.id) and last["action"] == "fix":
                     is_collected = True
            
            if not is_collected:
                new_active_panels.append(panel)
            else:
                # PAYOUT LOGIC
                interactions = panel.get("interactions", [])
                total_interactions = len(interactions)
                
                if total_interactions > 0:
                    battery_val = self.hof.mechanics.get("battery_value", 50000)
                    user_counts = {}
                    for i in interactions:
                        uid = i["user_id"]
                        user_counts[uid] = user_counts.get(uid, 0) + 1
                        
                    for uid, count in user_counts.items():
                        share = int((count / total_interactions) * battery_val)
                        if share > 0:
                             self.daily_profit[uid] = self.daily_profit.get(uid, 0) + share

        self.active_panels = new_active_panels
        
        if collected_count > 0:
             if str(user.id) not in self.daily_batteries:
                self.daily_batteries[str(user.id)] = 0
             self.daily_batteries[str(user.id)] += collected_count

        if eligible_count > 0:
            self.tracking_data["fixed_this_hour"] += 1 
            uid = str(user.id)
            self.daily_work["fixes"][uid] = self.daily_work["fixes"].get(uid, 0) + 1
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
                            f"📦 **Containers Today**: {sum(self.daily_work['containers'].values())}\n"
                            f"⚓ **Hafenevents Today**: {sum(self.daily_work['hafenevents'].values())}\n\n"
                            f"Use buttons below to update."
                        )
                        await msg.edit(embed=embed)
                    except discord.NotFound:
                        self.tracking_message_id = None
            except Exception:
                pass

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
        has_activity = any([
            self.daily_work["placed"],
            self.daily_work["fixes"],
            self.daily_work["containers"],
            self.daily_work["hafenevents"],
            self.daily_profit
        ])
        
        if has_activity:
             archive_entry = {
                 "date": self.last_reset_date or "Unknown",
                 "work": self.daily_work,
                 "profit": self.daily_profit,
                 "batteries": self.daily_batteries
             }
             self.history.append(archive_entry)
        
        # 2. Aggregate Lifetime
        for category in ["placed", "fixes", "containers", "hafenevents"]:
            for uid, count in self.daily_work[category].items():
                if str(uid) not in self.lifetime_work[category]:
                    self.lifetime_work[category][str(uid)] = 0
                self.lifetime_work[category][str(uid)] += count
            
        for uid, val in self.daily_profit.items():
            if str(uid) not in self.lifetime_profit: self.lifetime_profit[str(uid)] = 0
            self.lifetime_profit[str(uid)] += val

        # 3. Clear Current
        self.daily_work = {
            "placed": {},
            "fixes": {},
            "containers": {},
            "hafenevents": {}
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
            return discord.File(self.data_file, filename="knecht_backup.json")
        return None

    # --- Commands ---

    @app_commands.command(name='knecht_add', description="Show the main Knecht control dashboard.")
    @check_permissions()
    async def knecht_add(self, interaction: discord.Interaction):
        # Update logic to include new mechanics in description
        containers_today = sum(self.daily_work['containers'].values())
        hafenevents_today = sum(self.daily_work['hafenevents'].values())
        
        embed = discord.Embed(
            title="Knecht Control", 
            description=(
                f"**Current Status**\n\n"
                f"☀️ **Active Panels**: {len(self.active_panels)}\n"
                f"🔧 **Fixed (Hour)**: {self.tracking_data['fixed_this_hour']}\n\n"
                f"📦 **Containers Today**: {containers_today}\n"
                f"⚓ **Hafenevents Today**: {hafenevents_today}\n\n"
                f"Use buttons below to update."
            ),
            color=0x00FF00
        )
        
        await interaction.response.send_message(embed=embed, view=KnechtView(self))
        msg = await interaction.original_response()
        self.tracking_message_id = msg.id
        self.save_stats()


    @app_commands.command(name='knecht_clear_panels', description="Reset active panels count to 0 (Debug only).")
    @check_permissions()
    async def knecht_clear_panels(self, interaction: discord.Interaction):
        self.active_panels = []
        self.save_stats()
        await interaction.response.send_message("✅ Active panels cleared (Debug).")

    @app_commands.command(name='knecht_status', description="Debug traffic and logic.")
    @check_permissions()
    async def knecht_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tz = get_target_timezone()
        now = datetime.now(tz)
        present, debug_log = check_traffic_debug(interaction.guild)
        
        leaderboard = self.hof.get_leaderboard(self.daily_work, self.daily_profit, self.daily_batteries)
        
        # --- Value HoF ---
        value_hof_lines = []
        for i, (uid, val, details) in enumerate(leaderboard, 1):
             if val > 0:
                value_hof_lines.append(f"{i}. <@{uid}>: **${val:,}** (Realized Profit)")
        value_hof_str = "\n".join(value_hof_lines) or "None"

        # --- Work HoF (Activity Count) ---
        # Sort by total actions
        work_sorted = sorted(leaderboard, key=lambda x: sum([x[2]['placed'], x[2]['fixes'], x[2]['containers'], x[2]['hafenevents']]), reverse=True)
        work_hof_lines = []
        for i, (uid, _, details) in enumerate(work_sorted, 1):
            total_acts = details['placed'] + details['fixes'] + details['containers'] + details['hafenevents']
            if total_acts > 0:
                work_hof_lines.append(f"{i}. <@{uid}>: **{total_acts} Acts** (P:{details['placed']} F:{details['fixes']} C:{details['containers']} H:{details['hafenevents']})")
        work_hof_str = "\n".join(work_hof_lines) or "None"
        
        placed_total = sum(d["placed"] for _, _, d in leaderboard)

        # Active active_panels
        panel_lines = []
        for p in self.active_panels:
            pid = p['id'][:6]
            pname = p.get('placed_by_name', 'Unknown')
            state = self.calculate_panel_state(p)
            rem = state["remaining_minutes"]
            delay = state["total_delay"]
            interactions = p.get('interactions', [])
            fixes_done = len([i for i in interactions if i['action'] == 'fix'])
            status_text = f"{rem}m left"
            if delay > 0: status_text += f" ({delay}m delay)"
            else: status_text += " (On Track)"
            panel_lines.append(f"`{pid}` {pname}: {status_text} - {fixes_done} fixes")
        panel_str = "\n".join(panel_lines) or "No active panels."

        status_msg = (
            f"**Status Report**\n"
            f"Time: {now.strftime('%H:%M:%S')}\n"
            f"Active Panels: {len(self.active_panels)}\n"
            f"Placed Panels (Daily): {placed_total}\n"
            f"Fixed Panels (Hour): {self.tracking_data['fixed_this_hour']}\n\n"
            f"**☀️ Active Panels Detail**:\n{panel_str}\n\n"
            f"**🏆 Value HoF**:\n{value_hof_str}\n\n"
            f"**🔨 Work HoF**:\n{work_hof_str}\n\n"
        )
        if len(status_msg) > 2000:
            # truncate if too long
            status_msg = status_msg[:1900] + "\n...(truncated)"
            
        await interaction.followup.send(status_msg, ephemeral=True)

    @app_commands.command(name='knecht_hof', description="Show the Daily Hall of Fame ($).")
    @check_permissions()
    async def knecht_hof(self, interaction: discord.Interaction):
        leaderboard = self.hof.get_leaderboard(self.daily_work, self.daily_profit, self.daily_batteries)
        
        if not leaderboard:
            await interaction.response.send_message("🏆 **Hall of Fame**: No activity recorded today.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🏆 Daily Performance Hall of Fame", color=0xD4AF37)
        
        description = "**Total Earnings**\n"
        for i, (uid, val, details) in enumerate(leaderboard, 1):
            description += f"**{i}.** <@{uid}> — **${val:,}**\n"
            
        embed.description = description
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name='knecht_reset', description="[ADMIN] Reset all daily stats manually.")
    @check_permissions()
    async def knecht_reset(self, interaction: discord.Interaction):
        self.reset_daily_stats()
        await interaction.response.send_message("✅ Daily stats have been reset.", ephemeral=True)

    @app_commands.command(name='knecht_export', description="[ADMIN] Export the current stats JSON.")
    @check_permissions()
    async def knecht_export(self, interaction: discord.Interaction):
        file = self.export_stats_file()
        if file:
            await interaction.response.send_message("📦 Here is the current `knecht_backup.json`:", file=file, ephemeral=True)
        else:
            await interaction.response.send_message("❌ No stats file found.", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            if isinstance(error, app_commands.MissingRole):
                await interaction.response.send_message(f"❌ You do not have the required role: **{error.missing_role[0]}**", ephemeral=True)
            else:
                await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        else:
             print(f"App Command Error: {error}")


async def setup(bot):
    await bot.add_cog(Knecht(bot))
