import discord
from src.config import TARGET_ROLE_NAME

def check_traffic_debug(guild: discord.Guild):
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
        
        is_playing = False
        for activity in member.activities:
            # Check for Game or keywords
            if isinstance(activity, discord.Game) or "RAGE Multiplayer" in activity.name or "GTA" in activity.name:
                is_playing = True
                break
        
        if is_playing:
            found_valid = True
            member_log += " ✅ MATCH!"
        else:
            member_log += " ❌ No Game Activity"
            
        logs.append(member_log)
    
    return bool(get_valid_players(guild)), "\n".join(logs)

def get_valid_players(guild: discord.Guild):
    """
    Returns a list of Valid Players (discord.Member).
    Valid Player: Has Role + Online/DND/Idle + Playing RAGE or Game
    """
    role = discord.utils.get(guild.roles, name=TARGET_ROLE_NAME)
    if not role:
        return []

    valid_players = []
    members_with_role = [m for m in guild.members if role in m.roles]
    
    for member in members_with_role:
        if member.status == discord.Status.offline:
            continue
            
        if not member.activities:
            continue
            
        is_playing = False
        for activity in member.activities:
            if isinstance(activity, discord.Game) or "RAGE Multiplayer" in activity.name or "Medal" in activity.name:
                is_playing = True
                break
        
        if is_playing:
            valid_players.append(member)
            
    return valid_players
