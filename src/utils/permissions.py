import json
import os
import discord
from discord import app_commands

CONFIG_PATH = "config/perms.json"

def load_permissions():
    """Load permissions from JSON config."""
    if not os.path.exists(CONFIG_PATH):
        print(f"[Permissions] Warning: {CONFIG_PATH} not found. Defaulting to empty permissions.")
        return {}
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"[Permissions] Error decoding {CONFIG_PATH}: {e}")
        return {}

def has_role(user: discord.Member, role_name: str) -> bool:
    """Check if a user has a specific role by name."""
    if not isinstance(user, discord.Member):
        return False # Can't check roles for non-members (e.g. DM)
    
    return any(role.name == role_name for role in user.roles)

async def permission_check_logic(interaction: discord.Interaction) -> bool:
    """Core logic for checking permissions."""
    # 1. Load config (Consider caching this if performance becomes an issue, 
    # but for a small JSON file, reading or using a module-level var is fine.
    # simpler to just load it to allow hot-reloading edits to the json)
    # Actually, let's load it once at the start of the check to be safe and up-to-date.
    perms = load_permissions()
    
    command_name = interaction.command.name if interaction.command else None
    
    if not command_name:
        # invocations without a command (shouldn't happen for app_commands checks usually)
        return True 
        
    required_role = perms.get(command_name)
    
    if not required_role:
        # If no role is defined for this command, we assume it's allowed.
        return True
        
    if has_role(interaction.user, required_role):
        return True
        
    # Raise MissingRole with a list of the single required role
    raise app_commands.MissingRole([required_role])

def check_permissions():
    """Discord app_command check decorator."""
    return app_commands.check(permission_check_logic)
