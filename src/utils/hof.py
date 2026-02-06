import json
import os

class HallOfFame:
    def __init__(self, mechanics_file="data/mechanics.json"):
        self.mechanics_file = mechanics_file
        self.mechanics = { "panels": {"place": 100, "fix": 50}, "batteries": {"collect": 200} } # Defaults
        self.load_mechanics()

    def load_mechanics(self):
        """Load value mapping from JSON."""
        if os.path.exists(self.mechanics_file):
            try:
                with open(self.mechanics_file, 'r') as f:
                    self.mechanics = json.load(f)
            except Exception as e:
                print(f"Error loading mechanics: {e}")

    def get_user_value(self, user_id, daily_stats, daily_batteries):
        """Calculate total value ($) for a user."""
        total = 0
        user_id = str(user_id)
        
        # Panels Placed
        places = daily_stats["placed"].get(user_id, 0)
        total += places * self.mechanics.get("panels", {}).get("place", 0)
        
        # Panels Fixed
        fixes = daily_stats["fixes"].get(user_id, 0)
        total += fixes * self.mechanics.get("panels", {}).get("fix", 0)
        
        # Batteries Collected
        batteries = daily_batteries.get(user_id, 0)
        total += batteries * self.mechanics.get("batteries", {}).get("collect", 0)
        
        return total

    def get_leaderboard(self, daily_stats, daily_batteries):
        """Return a sorted list of (user_id, total_value, details_dict)."""
        users = set()
        users.update(daily_stats["placed"].keys())
        users.update(daily_stats["fixes"].keys())
        users.update(daily_batteries.keys())
        
        leaderboard = []
        for uid in users:
            val = self.get_user_value(uid, daily_stats, daily_batteries)
            details = {
                "placed": daily_stats["placed"].get(uid, 0),
                "fixes": daily_stats["fixes"].get(uid, 0),
                "batteries": daily_batteries.get(uid, 0)
            }
            leaderboard.append((uid, val, details))
            
        # Sort by total value desc
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        return leaderboard
