"""
Live Match Feed Listener & Poller.
Monitors competitive LoL leagues for live matches and draft events.
Supports Riot/LoL Esports public endpoints, simulation feeds, and custom triggers.
"""
import time
import requests
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("LiveFeedListener")

class LiveFeedListener:
    def __init__(self, target_leagues: Optional[List[str]] = None):
        self.target_leagues = target_leagues or ["LCK", "LPL", "LEC", "LCS", "MSI", "WORLDS", "WLDs", "EWC"]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "x-api-key": "0TvQnueqKa5omxqerXx9a"
        }
        self.seen_matches = set()

    def fetch_live_schedule(self) -> List[Dict[str, Any]]:
        """
        Polls official LoL Esports schedule for ongoing / upcoming live matches.
        """
        url = "https://esports-api.lolesports.com/persisted/val/getSchedule?hl=en-US"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                events = data.get("data", {}).get("schedule", {}).get("events", [])
                live_matches = []
                for ev in events:
                    state = ev.get("state", "").lower()
                    league_name = ev.get("league", {}).get("name", "").upper()
                    
                    if state in ["inprogress", "unstarted"]:
                        match = ev.get("match", {})
                        teams = match.get("teams", [])
                        if len(teams) >= 2:
                            live_matches.append({
                                "match_id": ev.get("id", str(ev.get("startTime"))),
                                "league": league_name,
                                "state": state,
                                "start_time": ev.get("startTime"),
                                "blue_team": teams[0].get("code", teams[0].get("name", "Unknown")),
                                "red_team": teams[1].get("code", teams[1].get("name", "Unknown")),
                                "strategy_count": match.get("strategy", {}).get("count", 3)
                            })
                return live_matches
        except Exception as e:
            logger.debug(f"Schedule fetch info: {e}")
        return []

    def generate_mock_live_match(self, blue_team: str = "T1", red_team: str = "Gen.G", league: str = "LCK") -> Dict[str, Any]:
        """
        Generates a realistic live match payload for testing and dry runs.
        """
        return {
            "match_id": f"LIVE_{int(time.time())}",
            "league": league,
            "state": "draft_complete",
            "blue_team": blue_team,
            "red_team": red_team,
            "blue_picks": {
                "top": "Rumble",
                "jng": "Jarvan IV",
                "mid": "Orianna",
                "bot": "Kalista",
                "sup": "Renata Glasc"
            },
            "red_picks": {
                "top": "K'Sante",
                "jng": "Maokai",
                "mid": "Azir",
                "bot": "Zeri",
                "sup": "Lulu"
            },
            "market_odds_blue": 2.10,
            "market_odds_red": 1.75
        }
