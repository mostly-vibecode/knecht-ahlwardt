# Setup Guide for Knecht Ahlwardt Bot

## 1. Wispbyte (or generic Host) Setup
The project files are ready to be uploaded.
1. Upload `main.py`, `requirements.txt`.
2. **Startup Command**: Set to `python main.py`.
3. **Dependencies**: Wispbyte should auto-install from `requirements.txt`.

## 2. Configuration (Environment Variables)

**Crucial Step**: Enable **Developer Mode** in your Discord client.
- **Settings** (Gear Icon) → **Advanced** → Toggle **Developer Mode** ON.

### How to obtain the values:

#### `DISCORD_TOKEN`
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** (top right) → Name it "Knecht Ahlwardt" → Create.
3. In the left sidebar, click **Bot**.
4. Click **Reset Token** (yes, do it).
5. **Copy** the token immediately. This is your `DISCORD_TOKEN`.
   - *Important*: While here, scroll down to **Privileged Gateway Intents** and enable **Presence Intent** and **Server Members Intent**.

#### `TARGET_GUILD_ID`
1. In Discord, look at your Server Icon on the left list.
2. **Right-click** the Server Icon.
3. Click **Copy Server ID** (at the bottom of the menu).

#### `TARGET_CHANNEL_ID`
1. Navigate to the channel where you want the bot to post/ping.
2. **Right-click** the channel name in the channel list.
3. Click **Copy Channel ID**.

#### `TARGET_ROLE_NAME`
1. Go to **Server Settings** → **Roles**.
2. Find the role you want to ping (e.g., "Ahlwardt").
3. **Copy the name exactly** (case-sensitive).

#### `TARGET_GAME_NAME`
- **Currently Ignored**: The bot now checks if the user is playing *any* game (due to inconsistent status reports like Medal, Mod Loaders, etc.).
- You can leave this blank or set it to anything.

#### `TIMEZONE`
- Use a TZ Database Name, like `Europe/Berlin`, `America/New_York`, or `UTC`.

## 3. Inviting the Bot (Crucial!)
Creating the bot in the portal does **not** add it to your server. You must invite it.

1. Go to **Discord Developer Portal** → **OAuth2** → **URL Generator**.
2. **Scopes**: Check ☑️ `bot`.
3. **Bot Permissions**: Check these boxes:
   - `View Channels`
   - `Send Messages`
   - `Embed Links`
   - `Read Message History` (To find the tracking message after restart)
   - `Add Reactions`
   - `Manage Messages` (To remove user reactions)
   - `Mention Everyone` (If you want it to ping roles)
4. **Copy the URL** at the bottom.
5. Paste it in your browser, select your server, and click **Authorize**.

## 4. Usage
1. **Start**: In the channel, type `/panels_spawn`.
   - The bot will post the tracking embed and add ☀️ and 🔧.
2. **Placing**: Users click ☀️.
3. **Fixing**: Users click 🔧.
   - If fixed (🔧 count > 1), the bot stays silent at XX:31.
   - At XX:30 (next hour), the bot removes user 🔧 reactions automatically.
4. **Reseting**: When confirmed finished/collected, type `/panels_collected`.

## 4. Traffic Awareness Check
The bot strictly checks:
- Is member in Role "Ahlwardt"?
- Is member Status NOT Offline?
- Is member Activity Name == `TARGET_GAME_NAME`? (Make sure this matches exactly what Discord shows under "Playing ...")
