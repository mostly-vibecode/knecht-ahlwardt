import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')
TARGET_GUILD_ID = int(os.getenv('TARGET_GUILD_ID', 0))
TARGET_CHANNEL_ID = int(os.getenv('TARGET_CHANNEL_ID', 0))
BACKUP_CHANNEL_ID = int(os.getenv('BACKUP_CHANNEL_ID', 0))
TARGET_ROLE_NAME = os.getenv('TARGET_ROLE_NAME', 'Ahlwardt')
TIMEZONE_STR = os.getenv('TIMEZONE', 'Europe/Berlin')
