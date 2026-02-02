# Knecht Ahlwardt - Discord Reminder Bot

A specialized Discord bot designed to manage reminders for the "Solar Panel" game mechanic. It ensures panels are fixed on time while respecting server traffic and player availability.

## 🤖 Bot Logic

### The Mechanic
- **Goal**: Maintain solar panels for a 4-hour cycle.
- **Requirement**: Panels must be fixed once every hour (between XX:01 and XX:59).
- **Restart**: At **04:00**, the server restarts, and all panel progress is wiped.

### How It Works
1.  **Tracking Message**: The bot uses a single persistent message to track status via reactions.
2.  **Placing Panels** (☀️): Users click the ☀️ reaction to indicate a panel is placed. The bot tracks the count.
3.  **Fixing Panels** (🔧):
    *   Users click the 🔧 reaction to mark the panels as "Fixed" for the current hour.
    *   **Auto-Reset**: At **XX:30** of the *next* hour, the bot automatically removes user 🔧 reactions, resetting the status to "Not Fixed" for the new cycle.
4.  **Reminders**:
    *   If panels are **not** fixed (no user 🔧 reaction), the bot will Ping the team at:
        *   **XX:31**
        *   **XX:45**
        *   **XX:50**
        *   **XX:55**
    *   **Traffic Awareness**: The bot will **ONLY** ping if there is at least one "Valid Player" online.
        *   *Valid Player*: Has Role "Ahlwardt" + Status is Online/DND/Idle + Playing **ANY** Game (ignoring specific name for now).

## 🛠️ Commands

| Command | Description |
| :--- | :--- |
| `/panels_spawn` | Spawns the main tracking embed. The bot automatically adds ☀️ and 🔧 reactions for one-click use. |
| `/panels_collected` | Use this when panels are finished and collected from the map. Resets the "Placed" count to 0 and clears ☀️ reactions. |
| `/panels_status` | Debug command. Shows current server time and whether "Traffic" (valid players) is currently detected. |

## 🚀 Setup & Hosting

Detailed setup instructions, including how to get Discord IDs and host on Wispbyte, are available in [SETUP.md](./SETUP.md).

### Quick Start (Local)
1.  Install dependencies: `pip install -r requirements.txt`
2.  Configure `.env` (see `.env.example`).
3.  Run: `python main.py`
