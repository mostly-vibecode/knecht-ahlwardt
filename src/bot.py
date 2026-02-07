import discord
from discord.ext import commands
from src.config import TARGET_GUILD_ID

class AhlwardtBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        super().__init__(command_prefix='/', intents=intents)

    async def setup_hook(self):
        # Load extensions
        start_extensions = ['src.cogs.panels', 'src.cogs.tasks']
        for extension in start_extensions:
            await self.load_extension(extension)

        # Sync commands
        if TARGET_GUILD_ID:
            guild = discord.Object(id=TARGET_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Synced commands to guild {TARGET_GUILD_ID}")

    async def on_ready(self):
        import uuid
        session_id = str(uuid.uuid4())[:8]
        print(f'Logged in as {self.user.name} (Session ID: {session_id})')
        print(f'WARNING: If you see multiple Session IDs in logs, run only ONE instance!')
