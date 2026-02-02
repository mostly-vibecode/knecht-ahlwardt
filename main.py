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
TARGET_GAME_NAME = os.getenv('TARGET_GAME_NAME', 'The Game')
TIMEZONE_STR = os.getenv('TIMEZONE', 'Europe/Berlin')

# Emojis
EMOJI_PLACE = "☀️"
EMOJI_FIX = "🔧"

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

class AhlwardtBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='/', intents=intents)

    async def setup_hook(self):
        # Sync commands to the specific guild for instant updates
        if TARGET_GUILD_ID:
            guild = discord.Object(id=TARGET_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Synced commands to guild {TARGET_GUILD_ID}")
        else:
            print("Warning: TARGET_GUILD_ID not set. Commands may take up to 1 hour to appear globally.")

bot = AhlwardtBot()

# State
tracking_message_id = None
last_checked_minute = -1
panels_placed_count = 0

def get_target_timezone():
    try:
        return pytz.timezone(TIMEZONE_STR)
    except pytz.UnknownTimeZoneError:
        return pytz.UTC

def is_traffic_present(guild):
    """
    Checks if there is at least one member who:
    1. Has the target role.
    2. Is not offline.
    3. Is playing ANY game (discord.Game).
    """
    role = discord.utils.get(guild.roles, name=TARGET_ROLE_NAME)
    if not role:
        print(f"Role {TARGET_ROLE_NAME} not found.")
        return False

    for member in guild.members:
        if role in member.roles:
            # Check Status
            if member.status == discord.Status.offline:
                continue
            
            # Check Activity
            if not member.activities:
                continue
            
            is_playing = False
            for activity in member.activities:
                # User requested "any game name" for now to handle various status displays (Medal, Mod loaders, etc.)
                if isinstance(activity, discord.Game):
                    is_playing = True
                    break
            
            if is_playing:
                return True
                
    return False

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    if not check_time.is_running():
        check_time.start()

@bot.tree.command(name='panels_spawn', description="Creates the persistent tracking message.")
async def panels_spawn(interaction: discord.Interaction):
    global tracking_message_id
    embed = discord.Embed(title="Solar Panel Manager", description="React to manage panels.\n\n☀️ : Panels Placed\n🔧 : Panels Fixed (Current Hour)", color=0xFFA500)
    
    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    tracking_message_id = msg.id
    
    # Bot pre-reacts for usability
    await msg.add_reaction(EMOJI_PLACE)
    await msg.add_reaction(EMOJI_FIX)
    
    # Follow-up message (hidden/ephemeral or just regular)
    await interaction.followup.send("Tracking started. Monitoring reactions...", ephemeral=True)

@bot.tree.command(name='panels_collected', description="Resets the panel count (e.g., after collecting finished panels).")
async def panels_collected(interaction: discord.Interaction):
    global tracking_message_id, panels_placed_count
    
    if tracking_message_id:
        try:
            channel = interaction.channel
            msg = await channel.fetch_message(tracking_message_id)
            reaction = discord.utils.get(msg.reactions, emoji=EMOJI_PLACE)
            if reaction:
                async for user in reaction.users():
                    if user != bot.user:
                        await msg.remove_reaction(EMOJI_PLACE, user)
        except Exception as e:
            print(f"Error resetting reactions: {e}")

    panels_placed_count = 0
    await interaction.response.send_message("Panels marked as collected. Count reset.")

@bot.tree.command(name='panels_status', description="Debug status report.")
async def panels_status(interaction: discord.Interaction):
    tz = get_target_timezone()
    now = datetime.now(tz)
    traffic = is_traffic_present(interaction.guild)
    
    status_msg = f"**Status Report**\nTime: {now.strftime('%H:%M:%S')}\nTraffic Present: {traffic}"
    await interaction.response.send_message(status_msg)

@tasks.loop(seconds=45) # Check slightly faster than a minute
async def check_time():
    global last_checked_minute, tracking_message_id
    
    if tracking_message_id is None:
        return

    tz = get_target_timezone()
    now = datetime.now(tz)
    
    if now.minute == last_checked_minute:
        return
    last_checked_minute = now.minute

    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        return

    try:
        msg = await channel.fetch_message(tracking_message_id)
    except discord.NotFound:
        print("Tracking message not found.")
        tracking_message_id = None
        return

    # Logic Implementation... (same as before)
    # 04:00 - Server Restart / Wiper
    if now.hour == 4 and now.minute == 0:
        reaction = discord.utils.get(msg.reactions, emoji=EMOJI_PLACE)
        if reaction:
            async for user in reaction.users():
                if user != bot.user:
                    await msg.remove_reaction(EMOJI_PLACE, user)
        reaction_fix = discord.utils.get(msg.reactions, emoji=EMOJI_FIX)
        if reaction_fix:
            async for user in reaction_fix.users():
                if user != bot.user:
                    await msg.remove_reaction(EMOJI_FIX, user)
        
        await channel.send("ℹ️ Server Restart: Panel tracking reset.")
        return

    # XX:30 - Reset "Fixed" status
    if now.minute == 30:
        reaction = discord.utils.get(msg.reactions, emoji=EMOJI_FIX)
        if reaction:
            async for user in reaction.users():
                if user != bot.user:
                    await msg.remove_reaction(EMOJI_FIX, user)
        return

    # Reminders: XX:31, XX:45, XX:50, XX:55
    if now.minute in [31, 45, 50, 55]:
        if not is_traffic_present(channel.guild):
            return

        reaction = discord.utils.get(msg.reactions, emoji=EMOJI_FIX)
        if reaction and reaction.count > 1:
            return # Already fixed

        role = discord.utils.get(channel.guild.roles, name=TARGET_ROLE_NAME)
        mention = role.mention if role else "@here"
        
        await channel.send(f"⚠️ {mention} The solar panels need fixing! (Time: {now.strftime('%H:%M')})")

@check_time.before_loop
async def before_check_time():
    await bot.wait_until_ready()

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Error: DISCORD_TOKEN not found in .env")
