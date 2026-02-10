# Knecht Ahlwardt - Operation Manual

Knecht Ahlwardt is a specialized Discord bot designed to manage the "Solar Panel" game mechanic reminders, track server traffic to prevent spam pings, and maintain a daily Hall of Fame.

---

## 🎮 The Mechanics

### 1. Solar Panel Cycle
-   **Goal**: Maintain solar panels for a 4-hour cycle.
-   **Requirement**: Panels must be fixed once every hour (between XX:01 and XX:59).
-   **Repair Window**:
    -   Panels placed in the first half of the hour (XX:00 - XX:29) are eligible for repair at **XX:30**.
    -   Panels placed in the second half must wait until the next hour.
-   **Collection**: After 4 successful fixes (approx. 4 hours), the panel is "Finished" and can be collected for profit.

### 2. Other Activities
The bot also tracks other high-value activities for the daily leaderboard:
-   **Containers (📦)**: Found in the game world, worth significant cash.
-   **Hafenevents (⚓)**: Special harbor events, worth high value drops.

### 3. Daily Reset
At **04:00 AM**, the server restarts. The bot automatically:
-   Wipes all panel progress.
-   Resets the daily leaderboard.
-   Posts a "Daily Report" summary to the channel.

---

## 🕹️ Dashboard & Usage

The primary interaction happens through a persistent **Control Dashboard** (spawned via `/knecht_add`).

### Buttons
| Button | Action | Description |
| :--- | :--- | :--- |
| **Place Panel** (➕) | **Start Timer** | Registers a new panel. The bot will track its 4-hour lifespan. |
| **Fix Panels** (✅) | **Maintain/Collect** | Marks *eligible* panels as fixed for the current hour. If a panel is finished, it is automatically collected. |
| **Container** (📦) | **Log Profit** | Logs a container find. Adds value to your daily total. |
| **Hafenevent** (⚓) | **Log Profit** | Logs a hafenevent completion. Accrues value to your daily total. |

### Traffic Awareness 🚦
To prevent spam, the bot **ONLY** sends reminder pings if "Valid Players" are online.
A **Valid Player** is:
1.  Online, Idle, or DND (Not Offline).
2.  Has the **Role** specified in config (e.g., "Ahlwardt").
3.  Is playing the **Target Game** (e.g., RAGE Multiplayer) - *Configurable*.

---

## 🛠️ Commands

### General
| Command | Description |
| :--- | :--- |
| `/knecht_add` | Spawns the main **Control Dashboard**. Use this if the message gets deleted or lost. |
| `/knecht_status` | **Debug View**. Shows: <br>• Current traffic status (who is online).<br>• Detailed status of every active panel (Time left, Delays).<br>• Full debug logs. |
| `/knecht_hof` | Displays the **Daily Hall of Fame** (Leaderboard) showing top earners and most active players. |

### Admin / Management
| Command | Description |
| :--- | :--- |
| `/knecht_clear [query]` | **Undo/Remove Data**. <br>• `all_p`: Clear all panels.<br>• `all_c`: Clear all containers (reverts profit).<br>• `all_h`: Clear all hafenevents (reverts profit).<br>• `[ID]`: Remove a specific panel or event by its ID (found in `/knecht_status` or logs). |
| `/knecht_reset` | **Force Daily Reset**. Manually triggers the 04:00 AM reset logic. Useful for testing or correcting a missed reset. |
| `/knecht_export` | **Backup Data**. Uploads the current `knecht.json` database file to the chat. |

---

## 🚀 Setup & Hosting
For installation, configuration, and hosting instructions, please refer to [SETUP.md](./SETUP.md).
