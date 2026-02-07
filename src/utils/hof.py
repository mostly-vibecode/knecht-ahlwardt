import json
import os

class HallOfFame:
    def __init__(self, mechanics_file="config/mechanics.json"):
        self.mechanics_file = mechanics_file
        # Defaults if file missing
        self.mechanics = { 
            "place_value": 10000, 
            "fix_value": 10000 
        } 
        self.load_mechanics()

    def load_mechanics(self):
        """Load value mapping from JSON."""
        if os.path.exists(self.mechanics_file):
            try:
                with open(self.mechanics_file, 'r') as f:
                    self.mechanics = json.load(f)
            except Exception as e:
                print(f"Error loading mechanics: {e}")

    def get_leaderboard(self, daily_work, daily_profit, daily_batteries):
        """
        Return a sorted list of (user_id, total_value, details_dict).
        
        daily_work: { "placed": {uid: count}, "fixes": {uid: count} }
        daily_profit: { uid: amount }
        daily_batteries: { uid: count }
        """
        users = set()
        users.update(daily_work["placed"].keys())
        users.update(daily_work["fixes"].keys())
        users.update(daily_work["containers"].keys())
        users.update(daily_work["hafenevents"].keys())
        users.update(daily_profit.keys())
        users.update(daily_batteries.keys())
        
        leaderboard = []
        for uid in users:
            # Value is now pre-calculated (Realized Profit)
            val = daily_profit.get(uid, 0)
            
            details = {
                "placed": daily_work["placed"].get(uid, 0),
                "fixes": daily_work["fixes"].get(uid, 0),
                "containers": daily_work["containers"].get(uid, 0),
                "hafenevents": daily_work["hafenevents"].get(uid, 0),
                "batteries": daily_batteries.get(uid, 0)
            }
            leaderboard.append((uid, val, details))
            
        # Sort by total value desc
        leaderboard.sort(key=lambda x: x[1], reverse=True)
        return leaderboard
