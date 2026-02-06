# Refactoring Plan: Modular AhlwardtBot

The goal is to refactor the monolithic `main.py` into a modular package structure (`src/`) to improve maintainability, extensibility, and testability.

## User Review Required
> [!NOTE]
> This refactor will change how the bot is run. It will move most logic into a `src` package. The entry point will remain `main.py` but will be significantly simplified.

## Proposed Changes

### Directory Structure
```
ahlwardt/
├── main.py             # Entry point (simplified)
├── .env                # Config (stays same)
└── src/
    ├── __init__.py
    ├── config.py       # Configuration loading
    ├── bot.py          # Custom Bot class
    ├── cogs/           # Discord Cogs (Modules)
    │   ├── __init__.py
    │   ├── panels.py   # Panel management commands & UI
    │   └── tasks.py    # specific scheduled tasks
    └── utils/          # Helper modules
        ├── __init__.py
        ├── traffic.py  # Traffic detection logic
        └── helpers.py  # Timezone and misc helpers
```

### Components

#### [NEW] [src/config.py](file:///Users/dna/git/ahlwardt/src/config.py)
- Load environment variables using `python-dotenv`.
- dataclass or simple module level variables for config.

#### [NEW] [src/utils/helpers.py](file:///Users/dna/git/ahlwardt/src/utils/helpers.py)
- Move `get_target_timezone` here.

#### [NEW] [src/utils/traffic.py](file:///Users/dna/git/ahlwardt/src/utils/traffic.py)
- Move `check_traffic_debug` logic here.
- Make it a pure function that takes the `guild` and `TARGET_ROLE_NAME`.

#### [NEW] [src/cogs/panels.py](file:///Users/dna/git/ahlwardt/src/cogs/panels.py)
- Create `Panels` Cog.
- Move `PanelView` class here.
- Move `panels_spawn`, `panels_collected`, `panels_status` commands here.
- Manage state (`tracking_data`) within the Cog instance (not global).

#### [NEW] [src/cogs/tasks.py](file:///Users/dna/git/ahlwardt/src/cogs/tasks.py)
- Create `BackgroundTasks` Cog.
- Move `check_time` loop here.
- Needs access to `Panels` Cog to check/update state, or share a state manager.
    - *Plan*: The `Panels` cog will expose methods/properties for state, or we pass a shared state object. For simplicity, `BackgroundTasks` can access `bot.get_cog('Panels')` to read state.

#### [NEW] [src/bot.py](file:///Users/dna/git/ahlwardt/src/bot.py)
- `AhlwardtBot` class that loads extensions from `src/cogs`.

#### [MODIFY] [main.py](file:///Users/dna/git/ahlwardt/main.py)
- Just imports `AhlwardtBot` and runs it.

## Verification Plan

### Manual Verification
1.  **Startup**: Run `python main.py` and ensure no import errors.
2.  **Commands**: Test `/panels_status` to verify utils and cogs are working.
3.  **State**: Verify `/panels_spawn` creates the view and buttons work.
4.  **Tasks**: Wait for a loop cycle (45s) to ensure no errors in background tasks.
