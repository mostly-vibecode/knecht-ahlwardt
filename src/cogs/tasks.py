import discord
from discord.ext import commands, tasks
from datetime import datetime
from src.utils.helpers import get_target_timezone
from src.utils.traffic import check_traffic_debug
from src.config import TARGET_CHANNEL_ID, TARGET_ROLE_NAME, BACKUP_CHANNEL_ID

class BackgroundTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_checked_minute = -1

    async def cog_load(self):
        self.check_time.start()

    async def cog_unload(self):
        self.check_time.cancel()

    @tasks.loop(seconds=45)
    async def check_time(self):
        target_channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        if not target_channel:
            return

        tz = get_target_timezone()
        now = datetime.now(tz)
        
        if now.minute == self.last_checked_minute:
            return
        self.last_checked_minute = now.minute

        # Get Panels cog for state
        panels_cog = self.bot.get_cog("Panels")
        if not panels_cog:
            print("Warning: Panels cog not found. Skipping logic involving state.")
            return
        
        # Logic Implementation
        
        # 04:00 - Hard Reset
        if now.hour == 4 and now.minute == 0:
            # Weekly Backups
            if now.weekday() == 0: # Monday
                backup_channel = self.bot.get_channel(BACKUP_CHANNEL_ID)
                if backup_channel:
                    file = panels_cog.export_stats_file()
                    if file:
                        await backup_channel.send(f"📦 **Weekly Backup** ({now.strftime('%Y-%m-%d')})", file=file)
                else:
                    print(f"Warning: Backup channel {BACKUP_CHANNEL_ID} not found.")

            # Daily Stats Report
            # Daily Stats Report
            leaderboard = panels_cog.get_leaderboard()
            
            hof_lines = []
            for i, (uid, val, details) in enumerate(leaderboard, 1):
                 hof_lines.append(f"{i}. <@{uid}>: **${val}** (P:{details['placed']} F:{details['fixes']} B:{details['batteries']})")
            hof_str = "\n".join(hof_lines) or "None"

            placed_daily = sum(panels_cog.daily_stats["placed"].values())

            summary = (
                f"ℹ️ **Daily Report & Server Restart**\n"
                f"☀️ Panels Placed: {placed_daily}\n"
                f"🏆 **Performance HoF**:\n{hof_str}\n"
            )
            await target_channel.send(summary)

            # Reset Stats
            panels_cog.tracking_data["fixed_this_hour"] = 0
            panels_cog.reset_daily_stats()
            return

        # XX:30 - Reset "Fixed" status for hour
        if now.minute == 30:
            if panels_cog.tracking_data["fixed_this_hour"] > 0:
                panels_cog.tracking_data["fixed_this_hour"] = 0
            return

        # Reminders: XX:31, XX:45, XX:50, XX:55
        if now.minute in [31, 45, 50, 55]:
            # Check Traffic
            from src.utils.traffic import get_valid_players
            valid_players = get_valid_players(target_channel.guild)
            
            if not valid_players:
                return

            # Check Logic
            # Check Logic
            # Count eligible panels
            eligible_count = 0
            for panel in panels_cog.active_panels:
                placed_dt = datetime.fromisoformat(panel["placed_at_iso"])
                is_eligible = False
                if placed_dt.hour != now.hour or placed_dt.date() != now.date():
                    is_eligible = True
                elif placed_dt.minute < 30 and now.minute >= 30:
                    is_eligible = True
                
                if is_eligible:
                    eligible_count += 1
            
            if eligible_count > 0 and panels_cog.tracking_data["fixed_this_hour"] == 0:
                mentions = [m.mention for m in valid_players]
                mention_str = ", ".join(mentions)
                msg = await target_channel.send(f"⚠️ {mention_str} Panels placed but not fixed! (Time: {now.strftime('%H:%M')})")
                await msg.add_reaction("✅")

    @check_time.before_loop
    async def before_check_time(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(BackgroundTasks(bot))
