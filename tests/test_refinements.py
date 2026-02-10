
import sys
import os
import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

# Mock discord
sys.modules["discord"] = MagicMock()

ext_mock = MagicMock()
sys.modules["discord.ext"] = ext_mock

commands_mock = MagicMock()
class MockCog:
    def __init__(self, *args, **kwargs): pass

commands_mock.Cog = MockCog
sys.modules["discord.ext.commands"] = commands_mock
ext_mock.commands = commands_mock

tasks_mock = MagicMock()
sys.modules["discord.ext.tasks"] = tasks_mock
ext_mock.tasks = tasks_mock

sys.modules["discord.ui"] = MagicMock()
sys.modules["discord.app_commands"] = MagicMock()

# Setup mocks for helpers BEFORE importing anything from src
traffic_mock = MagicMock()
sys.modules["src.utils.traffic"] = traffic_mock

helpers_mock = MagicMock()
sys.modules["src.utils.helpers"] = helpers_mock

hof_mock = MagicMock()
sys.modules["src.utils.hof"] = hof_mock

perms_mock = MagicMock()
sys.modules["src.utils.permissions"] = perms_mock

# Ensure src.utils has attributes for these mocks so patch() can find them
import importlib
try:
    src_utils = importlib.import_module("src.utils")
    src_utils.traffic = traffic_mock
    src_utils.helpers = helpers_mock
    src_utils.hof = hof_mock
    src_utils.permissions = perms_mock
except ImportError:
    # If src.utils cannot be imported (e.g. missing dependencies), we might need to mock it entirely
    # But we want to avoid that if possible to allow other imports. 
    # If it fails, we fallback to mocking src.utils
    sys.modules["src"] = MagicMock()
    sys.modules["src.utils"] = MagicMock()
    sys.modules["src.utils"].traffic = traffic_mock
    sys.modules["src.utils"].helpers = helpers_mock
    sys.modules["src.utils"].hof = hof_mock
    sys.modules["src.utils"].permissions = perms_mock


# Setup mocks for helpers
from src.utils.helpers import get_target_timezone

# Import the class after mocking
# We need to patch 'src.cogs.knecht.datetime' or similar if used
# But for now let's just test the methods that we can isolate.

from src.cogs.knecht import Knecht

class TestRefinements(unittest.IsolatedAsyncioTestCase):
    async def test_success_message_format(self):
        """Verify the success message is one-line with remaining times."""
        print("\n--- Testing Success Message Format ---")
        
        mock_bot = MagicMock()
        knecht = Knecht(mock_bot)
        
        # Mock active panels with dummy data
        knecht.active_panels = ["p1", "p2"]

        # Mock calculate_panel_state to return stable values
        # We need to simulate the return dict
        knecht.calculate_panel_state = MagicMock(side_effect=[
            {"remaining_minutes": 264, "expiry_iso": "2026-02-08T18:30:00"},
            {"remaining_minutes": 123, "expiry_iso": "2026-02-08T16:00:00"}
        ])

        # Mock interactive parts
        interaction = MagicMock()
        interaction.user.mention = "@User"
        # make send_message async
        interaction.response.send_message = AsyncMock()
        
        # Mock process_fix
        knecht.process_fix = MagicMock(return_value={"eligible_count": 2, "collected_count": 0})
        knecht.update_tracking_message = AsyncMock()

        # Call the method
        await knecht.handle_fix_interaction(interaction, is_reminder=True)

        # Assertions
        interaction.response.send_message.assert_called_once()
        args, _ = interaction.response.send_message.call_args
        msg = args[0]
        
        print(f"Resulting Message: {msg}")
        
        expected = "🔧 **Panels fixed.** Remaining: 264m(18:30), 123m(16:00)"
        if expected in msg:
            print("✅ Message format matches expected output.")
        else:
            print(f"❌ Message format MISMATCH.\nExpected: '{expected}'\nGot:      '{msg}'")
            self.fail("Message format mismatch")

    async def test_reminder_buttons_logic(self):
        """Verify that buttons are only shown at minute 31."""
        print("\n--- Testing Reminder Button Logic ---")
        
        # We need to test the logic block inside check_time. 
        # Since we cannot easily import check_time without running the whole bot or mocking a lot,
        # We will verify the logic by patching datetime in tasks.py and checking the View passed.
        
        # Problem: 'tasks.py' imports 'check_traffic_debug', 'get_target_timezone'.
        # We already mocked checks/utils above.
        
        # To test 'check_time', we need to instantiate check_time loop.
        # But 'tasks.loop' decorator is mocked.
        # So 'check_time' is likely just the function now if we mocked tasks.loop correctly?
        # Typically tasks.loop returns a Loop object, and the function is .coro
        # If we mocked discord.ext.tasks.loop to return a PASS-THROUGH decorator, we can access the function.
        
        pass

# We implement a custom passthrough for tasks.loop so we can run the test on tasks.py
def mock_loop(**kwargs):
    def decorator(func):
        func.start = MagicMock()
        func.cancel = MagicMock()
        func.before_loop = lambda f: f
        return func
    return decorator

sys.modules["discord.ext.tasks"].loop = mock_loop

# Import BackgroundTasks now
from src.cogs.tasks import BackgroundTasks

class TestTasksLogic(unittest.IsolatedAsyncioTestCase):
    @patch('src.cogs.tasks.datetime')
    @patch('src.cogs.tasks.get_target_timezone')
    @patch('src.cogs.tasks.check_traffic_debug')  # Not directly used? imported from traffic
    @patch('src.utils.traffic.get_valid_players')
    async def test_buttons_at_31(self, mock_get_players, mock_check_debug, mock_get_tz, mock_dt):
        print("\n--- Testing Reminder Buttons (Minute 31 vs 45) ---")
        
        mock_bot = MagicMock()
        tasks_cog = BackgroundTasks(mock_bot)
        mock_channel = MagicMock()
        mock_channel.send = AsyncMock()
        mock_bot.get_channel.return_value = mock_channel
        
        mock_knecht = MagicMock()
        mock_bot.get_cog.return_value = mock_knecht
        mock_knecht.active_panels = [{"placed_at_iso": "dummy", "id": "p1"}]
        mock_knecht.tracking_data = {"fixed_this_hour": 0}
        
        # Mock traffic
        mock_get_players.return_value = [MagicMock(mention="@Player")]
        
        # Mock timezone
        mock_get_tz.return_value = None
        
        # --- SUBTEST 1: Minute 31 (Expect Buttons) ---
        print("Testing Minute 31...")
        mock_now = MagicMock()
        mock_now.minute = 31
        mock_now.strftime.return_value = "12:31"
        mock_now.hour = 12
        mock_now.date.return_value = "today"
        mock_dt.now.return_value = mock_now
        
        # Mock datetime.fromisoformat for panel eligibility check
        # tasks.py:93 placed_dt = datetime.fromisoformat(panel["placed_at_iso"])
        mock_dt.fromisoformat.return_value.hour = 11 # Placed previous hour -> eligible
        
        tasks_cog.last_checked_minute = 30 # Ensure it runs
        
        # Run check_time
        await tasks_cog.check_time() # Bound method, no need to pass self
        # Depending on how we mocked loop, it might be an unbound method or bound.
        # If it's a method on class, calling it nicely?
        # tasks_cog.check_time()
        
        # Verify call to send
        mock_channel.send.assert_called()
        args, kwargs = mock_channel.send.call_args
        sent_view = kwargs.get('view')
        
        if sent_view is not None:
             print(f"✅ View (Buttons) IS present at minute 31. View: {sent_view}")
        else:
             print(f"❌ View (Buttons) is MISSING at minute 31. now.minute={mock_now.minute}")
             print(f"Call args: {args} {kwargs}")
             self.fail("View should be present at 31")
             
        # --- SUBTEST 2: Minute 45 (Expect No Buttons) ---
        print("Testing Minute 45...")
        mock_channel.send.reset_mock()
        mock_now.minute = 45
        tasks_cog.last_checked_minute = 31 # Reset last checked
        
        await tasks_cog.check_time()
        
        mock_channel.send.assert_called()
        args, kwargs = mock_channel.send.call_args
        sent_view = kwargs.get('view')
        
        if sent_view is None:
             print("✅ View (Buttons) IS NONE at minute 45.")
        else:
             print("❌ View (Buttons) IS PRESENT at minute 45 (Should be None).")
             self.fail("View should be None at 45")

if __name__ == '__main__':
    unittest.main()
