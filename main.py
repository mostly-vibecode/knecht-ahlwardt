import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
TARGET_GUILD_ID = int(os.getenv('TARGET_GUILD_ID', 0))
TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID', 0))
TARGET_ROLE_NAME = os.getenv('TARGET_ROLE_NAME', 'Ahlwardt')
# TARGET_GAME_NAME ignored now
TIMEZONE_STR = os.getenv('TIMEZONE', 'Europe/Berlin')

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

# Global State
tracking_data = {
    "placed": 0,
    "fixed_this_hour": 0
}

def get_target_timezone():
    try:
        return pytz.timezone(TIMEZONE_STR)
    except pytz.UnknownTimeZoneError:
        return pytz.UTC

class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent view

    @discord.ui.button(label="Place Panel", style=discord.ButtonStyle.primary, emoji="☀️", custom_id="panel_place")
    async def place_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        tracking_data["placed"] += 1
        await self.update_message(interaction)
    
    @discord.ui.button(label="Fix Panel", style=discord.ButtonStyle.success, emoji="🔧", custom_id="panel_fix")
    async def fix_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        tracking_data["fixed_this_hour"] += 1
        await self.update_message(interaction)

    async def update_message(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        # Update description or fields with new counts
        embed.description = (
            f"**Current Status**\n\n"
            f"☀️ **Placed**: {tracking_data['placed']}\n"
            f"🔧 **Fixed (Hour)**: {tracking_data['fixed_this_hour']}\n\n"
            f"Use buttons below to update."
        )
        await interaction.response.edit_message(embed=embed)

class AhlwardtBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/', intents=intents)

    async def setup_hook(self):
        # Register persistent view
        self.add_view(PanelView())
        
        # Sync commands
        if TARGET_GUILD_ID:
            guild = discord.Object(id=TARGET_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Synced commands to guild {TARGET_GUILD_ID}")

bot = AhlwardtBot()

# State
tracking_message_id = None
last_checked_minute = -1

def check_traffic_debug(guild):
    """
    Returns (bool_present, debug_log_string)
    """
    role = discord.utils.get(guild.roles, name=TARGET_ROLE_NAME)
    if not role:
        return False, f"❌ Role '{TARGET_ROLE_NAME}' not found in server."

    logs = []
    found_valid = False
    
    # Check all members with role
    members_with_role = [m for m in guild.members if role in m.roles]
    logs.append(f"Members with role '{TARGET_ROLE_NAME}': {len(members_with_role)}")
    
    for member in members_with_role:
        member_log = f"- {member.display_name}: Status={member.status}"
        
        if member.status == discord.Status.offline:
            member_log += " (Skipped: Offline)"
            logs.append(member_log)
            continue
            
        if not member.activities:
            member_log += " (Skipped: No Activity)"
            logs.append(member_log)
            continue
            
        activities_str = ", ".join([f"{type(a).__name__}({a.name})" for a in member.activities])
        member_log += f" Activities=[{activities_str}]"
        
        # Check for ANY Game or Custom Activity (if user counts that)
        # Broadening check: Game, Streaming, or even CustomActivity if it looks like a game?
        # User said "Custom game status", which usually means `discord.Game` created via "Add it!"
        # But let's accept `discord.Game` OR just presence of activity for now to be safe?
        # Let's stick to `discord.Game` but log it clearly.
        
        is_playing = False
        for activity in member.activities:
            if isinstance(activity, discord.Game):
                is_playing = True
                break
            # Also check if it's a CustomActivity that might be used as a game status? 
            # Usually CustomActivity is the status message.
        
        if is_playing:
            found_valid = True
            member_log += " ✅ MATCH!"
        else:
            member_log += " ❌ No Game Activity"
            
        logs.append(member_log)
    
    return found_valid, "\n".join(logs)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    if not check_time.is_running():
        check_time.start()

@bot.tree.command(name='panels_spawn', description="Spawn the tracking dashboard (Buttons).")
async def panels_spawn(interaction: discord.Interaction):
    global tracking_message_id
    
    embed = discord.Embed(
        title="Solar Panel Manager", 
        description=f"**Current Status**\n\n☀️ **Placed**: {tracking_data['placed']}\n🔧 **Fixed (Hour)**: {tracking_data['fixed_this_hour']}\n\nUse buttons below to update.", 
        color=0xFFA500
    )
    
    await interaction.response.send_message(embed=embed, view=PanelView())
    msg = await interaction.original_response()
    tracking_message_id = msg.id

@bot.tree.command(name='panels_collected', description="Reset 'Placed' count to 0.")
async def panels_collected(interaction: discord.Interaction):
    global tracking_data
    tracking_data["placed"] = 0
    # Ideally update the message text too if possible, but the next button click will fix it.
    await interaction.response.send_message("✅ Panels collected. Count reset to 0.")

@bot.tree.command(name='panels_status', description="Debug traffic and logic.")
async def panels_status(interaction: discord.Interaction):
    tz = get_target_timezone()
    now = datetime.now(tz)
    present, debug_log = check_traffic_debug(interaction.guild)
    
    status_msg = f"**Status Report**\nTime: {now.strftime('%H:%M:%S')}\nTraffic Present: {present}\n\n**Debug Log**:\n```{debug_log}```"
    await interaction.response.send_message(status_msg, ephemeral=True) # Ephemeral so only user sees debug spam

@tasks.loop(seconds=45)
async def check_time():
    global last_checked_minute
    
    target_channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not target_channel:
        return

    tz = get_target_timezone()
    now = datetime.now(tz)
    
    if now.minute == last_checked_minute:
        return
    last_checked_minute = now.minute

    # Logic Implementation
    
    # 04:00 - Hard Reset
    if now.hour == 4 and now.minute == 0:
        tracking_data["placed"] = 0
        tracking_data["fixed_this_hour"] = 0
        await target_channel.send("ℹ️ Server Restart: Panel tracking reset.")
        return

    # XX:30 - Reset "Fixed" status for hour
    if now.minute == 30:
        if tracking_data["fixed_this_hour"] > 0:
            tracking_data["fixed_this_hour"] = 0
            # We silently reset the counter. 
            # (Optional) We could update the embed if we tracked the message object, 
            # but fetching it every time might be overkill. 
            # The next button click will show 0.
        return

    # Reminders: XX:31, XX:45, XX:50, XX:55
    if now.minute in [31, 45, 50, 55]:
        # Check Traffic
        traffic_present, _ = check_traffic_debug(target_channel.guild)
        if not traffic_present:
            return

        # Check Logic
        # "If a panel is not fixed..."
        # If any panels are placed (placed > 0), we need at least some fixes?
        # Or just checking if ANY fix happened?
        # Simple Logic: If Placed > 0 AND Fixed_This_Hour == 0 -> PING
        
        if tracking_data["placed"] > 0 and tracking_data["fixed_this_hour"] == 0:
            role = discord.utils.get(target_channel.guild.roles, name=TARGET_ROLE_NAME)
            mention = role.mention if role else "@here"
            await target_channel.send(f"⚠️ {mention} Panels placed but not fixed! (Time: {now.strftime('%H:%M')})")

@check_time.before_loop
async def before_check_time():
    await bot.wait_until_ready()

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: DISCORD_TOKEN not found in .env")
