import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime
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
        
        self.daily_stats = {
            "placed": {}, # { user_id: count }
            "fixes": {}   # { user_id: count }
        }
        self.tracking_message_id = None
        self.data_file = "data/panels.json"
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        
        self.settings_file = "data/settings.json"
        self.settings = {"panel_liveduration": 60}
        self.load_settings()

        self.hof = HallOfFame("data/mechanics.json")
        self.load_stats()

    async def cog_load(self):
        """Register persistent views on load."""
        self.bot.add_view(ReminderView(self))
        
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
                    "daily_stats": self.daily_stats,
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
                
                # Load batteries (key conversion)
                if "daily_batteries" in data:
                    self.daily_batteries = {str(k): v for k, v in data["daily_batteries"].items()}
                else:
                    self.daily_batteries = {}
                    
                # Load stats
                if "daily_stats" in data:
                    stats = data["daily_stats"]
                    
                    # Migration: Check 'placed' type
                    if "placed" in stats:
                        if isinstance(stats["placed"], int):
                            print(f"[Migration] Converting 'placed' from int ({stats['placed']}) to dict.")
                            stats["placed"] = {} 
                        else:
                            stats["placed"] = {str(k): v for k, v in stats["placed"].items()}
                    else:
                        stats["placed"] = {}

                    if "fixes" in stats:
                        stats["fixes"] = {str(k): v for k, v in stats["fixes"].items()}
                    
                    self.daily_stats = stats
                else:
                    # Legacy support/Fall back
                    if "fixes" in data: # Old format was just daily_stats
                        self.daily_stats = {
                            "placed": {},
                            "fixes": {str(k): v for k, v in data["fixes"].items()}
                        }

                # Load tracking message ID
                self.tracking_message_id = data.get("tracking_message_id")
                        
        except Exception as e:
            print(f"Error loading stats: {e}")


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
            "remaining_minutes": liveduration
        }
        
        self.active_panels.append(panel)
        
        # Update Daily Stats (Placed)
        if str(user.id) not in self.daily_stats["placed"]:
            self.daily_stats["placed"][str(user.id)] = 0
        self.daily_stats["placed"][str(user.id)] += 1
        
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

    def process_fix(self, user):
        """Standardized logic for fixing panels (Button or Reaction)."""
        tz = get_target_timezone()
        now = datetime.now(tz)
        
        eligible_count = 0
        collected_count = 0
        
        # Identify eligible panels
        for panel in self.active_panels:
            placed_dt = datetime.fromisoformat(panel["placed_at_iso"])
            
            is_eligible = False
            if placed_dt.hour != now.hour or placed_dt.date() != now.date():
                is_eligible = True # Previous hour/day
            elif placed_dt.minute < 30 and now.minute >= 30:
                is_eligible = True # Early placement, repair window open
            
            if is_eligible:
                eligible_count += 1
                panel["remaining_minutes"] -= 60
                if panel["remaining_minutes"] <= 0:
                    collected_count += 1
        
        # Remove collected panels
        if collected_count > 0:
            self.active_panels = [p for p in self.active_panels if p["remaining_minutes"] > 0]
            
            # Award Batteries
            if str(user.id) not in self.daily_batteries:
                self.daily_batteries[str(user.id)] = 0
            self.daily_batteries[str(user.id)] += collected_count
            
        if eligible_count > 0:
            self.tracking_data["fixed_this_hour"] += 1 
            
            # Update Daily Fixes (HoF)
            if str(user.id) not in self.daily_stats["fixes"]:
                self.daily_stats["fixes"][str(user.id)] = 0
            self.daily_stats["fixes"][str(user.id)] += 1
            
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
            # Group active panels by ETA
            from datetime import timedelta
            tz = get_target_timezone()
            now = datetime.now(tz)
            
            # Grouping logic
            grouped_counts = {} # { "HH:MM window": count }
            
            for panel in self.active_panels:
                if panel["remaining_minutes"] <= 0:
                     continue
                     
                placed_dt = datetime.fromisoformat(panel["placed_at_iso"])
                
                # Determine Next Fix Window
                # If placed < 30, window is XX:30. If >= 30, window is XX:00.
                # Since we just fixed them (or they are pending for next hour), 
                # we assume next availability is Next Hour.
                
                next_hour = now.hour + 1
                if next_hour > 23:
                    next_hour = 0
                
                if placed_dt.minute < 30:
                    window_str = f"{next_hour:02d}:30"
                else:
                    window_str = f"{next_hour:02d}:00"
                
                if window_str not in grouped_counts:
                    grouped_counts[window_str] = 0
                grouped_counts[window_str] += 1

            # Constructing the message
            active_count = len(self.active_panels)
            
            msg = f"🔧 **Panels Fixed by {user.mention}!**\n"
            
            if grouped_counts:
                msg += f"Remaining Active: **{active_count}**\n"
                msg += "**Upcoming Repairs**:\n"
                # Sort by time?
                sorted_windows = sorted(grouped_counts.keys())
                for win in sorted_windows:
                    msg += f"• **{grouped_counts[win]}** @ {win}\n"
            elif active_count > 0:
                 msg += f"Remaining Active: **{active_count}** (All done for now?)"
            else:
                msg += "All panels collected! 🔋"
            
            if is_reminder:
                await interaction.response.send_message(msg)
            else:
                await interaction.response.send_message(msg, ephemeral=False)
            
            await self.update_tracking_message()
            
        else:
            await interaction.response.send_message("❌ No panels eligible for repair right now.", ephemeral=True)

    async def update_tracking_message(self):
        """Helper to update the main persistent message."""
        if self.tracking_message_id:
            try:
                # We don't know the channel easily unless we store it or fetch it.
                # We can try to fetch it from the guild using config channel ID.
                from src.config import TARGET_CHANNEL_ID
                channel = self.bot.get_channel(TARGET_CHANNEL_ID)
                if channel:
                    try:
                        msg = await channel.fetch_message(self.tracking_message_id)
                    except discord.NotFound:
                        self.tracking_message_id = None
                        self.save_stats()
                        return

                    embed = msg.embeds[0]
                    embed.description = (
                        f"**Current Status**\n\n"
                        f"☀️ **Active Panels**: {len(self.active_panels)}\n"
                        f"🔧 **Fixed (Hour)**: {self.tracking_data['fixed_this_hour']}\n\n"
                        f"Use buttons below to update."
                    )
                    await msg.edit(embed=embed)
            except Exception as e:
                print(f"Failed to update tracking message: {e}")

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

    def reset_daily_stats(self):
        """Reset daily stats and save."""
        self.daily_stats = {
            "placed": {},
            "fixes": {}
        }
        self.daily_batteries = {}
        # NOTE: We do NOT clear active_panels on daily reset, they persist until fixed!
        self.save_stats()

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
        leaderboard = self.hof.get_leaderboard(self.daily_stats, self.daily_batteries)
        
        # Build String
        hof_lines = []
        for i, (uid, val, details) in enumerate(leaderboard, 1):
             hof_lines.append(f"{i}. <@{uid}>: **${val}** (P:{details['placed']} F:{details['fixes']} B:{details['batteries']})")
        hof_str = "\n".join(hof_lines) or "None"
        
        placed_total = sum(d["placed"] for _, _, d in leaderboard)

        status_msg = (
            f"**Status Report**\n"
            f"Time: {now.strftime('%H:%M:%S')}\n"
            f"Traffic Present: {present}\n"
            f"Active Panels: {len(self.active_panels)}\n"
            f"Placed Panels (Daily): {placed_total}\n"
            f"Fixed Panels (Hour): {self.tracking_data['fixed_this_hour']}\n\n"
            f"**🏆 Value HoF**:\n{hof_str}\n\n"
            f"**Debug Log**:\n```{debug_log}```"
        )
        await interaction.response.send_message(status_msg, ephemeral=True)

    @app_commands.command(name='panels_hof', description="Show the Daily Hall of Fame ($).")
    async def panels_hof(self, interaction: discord.Interaction):
        leaderboard = self.hof.get_leaderboard(self.daily_stats, self.daily_batteries)
        
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
