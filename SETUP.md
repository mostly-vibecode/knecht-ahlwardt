# Setup Guide for Knecht Ahlwardt Bot

## 1. Wispbyte (or generic Host) Setup
The project files are ready to be uploaded.
1. Upload `main.py`, `requirements.txt`.
2. **Startup Command**: Set to `python main.py`.
3. **Dependencies**: Wispbyte (or your host) should auto-install from `requirements.txt`.

## 2. Configuration (Environment Variables)

**Crucial Step**: Enable **Developer Mode** in your Discord client.
- **Settings** (Gear Icon) → **Advanced** → Toggle **Developer Mode** ON.

### Required Variables

| Variable | Description |
| :--- | :--- |
| `DISCORD_TOKEN` | The bot's authentication token. |
| `TARGET_GUILD_ID` | The ID of the Discord Server (Guild) where the bot will operate. |
| `TARGET_CHANNEL_ID` | The ID of the specific channel for the dashboard and pings. |
| `TARGET_ROLE_NAME` | The **exact name** of the role to ping (e.g., `Ahlwardt`). |
| `TIMEZONE` | Your local timezone (e.g., `Europe/Berlin`). |

### How to obtain the values:

#### `DISCORD_TOKEN`
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** (top right) → Name it "Knecht Ahlwardt" → Create.
3. In the left sidebar, click **Bot**.
4. Click **Reset Token** (yes, do it).
5. **Copy** the token immediately.
   - *Important*: While here, scroll down to **Privileged Gateway Intents** and enable **Presence Intent** and **Server Members Intent**.

#### IDs (`TARGET_GUILD_ID`, `TARGET_CHANNEL_ID`)
1. Right-click the Server Icon → **Copy Server ID**.
2. Right-click the Channel Name → **Copy Channel ID**.

#### `TARGET_ROLE_NAME`
1. Go to **Server Settings** → **Roles**.
2. Copy the **exact name** of the role (case-sensitive).

## 3. Inviting the Bot
Creating the bot in the portal does **not** add it to your server. You must invite it:

1. Go to **Discord Developer Portal** → **OAuth2** → **URL Generator**.
2. **Scopes**: Check ☑️ `bot`.
3. **Bot Permissions**: Check these boxes:
   - `View Channels`
   - `Send Messages`
   - `Embed Links`
   - `Read Message History`
   - `Add Reactions`
   - `Manage Messages` (To remove user reactions)
   - `Mention Everyone` (To ping roles)
4. **Copy the URL** at the bottom.
5. Paste it in your browser, select your server, and click **Authorize**.

---
**Next Step**: Once the bot is running, see [README.md](./README.md) for commands and operation.
