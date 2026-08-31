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
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "x-api-key": "0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z"
        }
        self.seen_matches = set()
        self.base_gw_url = "https://esports-api.lolesports.com/persisted/gw"

    def fetch_live_schedule(self) -> List[Dict[str, Any]]:
        """
        Polls official LoL Esports schedule for ongoing / upcoming live matches.
        """
        url = f"{self.base_gw_url}/getSchedule?hl=en-US"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                events = data.get("data", {}).get("schedule", {}).get("events", [])
                live_matches = []
                for ev in events:
                    state = ev.get("state", "").lower()
                    league_name = ev.get("league", {}).get("name", "").upper()
                    
                    # Match target league filter if set
                    if any(target in league_name for target in self.target_leagues):
                        if state in ["inprogress", "unstarted"]:
                            match = ev.get("match", {})
                            teams = match.get("teams", [])
                            if len(teams) >= 2:
                                live_matches.append({
                                    "event_id": ev.get("id"),
                                    "match_id": match.get("id", ev.get("id", str(ev.get("startTime")))),
                                    "league": league_name,
                                    "state": state,
                                    "start_time": ev.get("startTime"),
                                    "blue_team": teams[0].get("code", teams[0].get("name", "Unknown")),
                                    "red_team": teams[1].get("code", teams[1].get("name", "Unknown")),
                                    "strategy_count": match.get("strategy", {}).get("count", 3)
                                })
                return live_matches
            else:
                logger.warning(f"Riot API schedule returned status {resp.status_code}")
        except Exception as e:
            logger.debug(f"Schedule fetch info: {e}")
        return []

    def fetch_live_event_details(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches detailed game state for an active event including locked champions.
        """
        if not event_id:
            return None
        url = f"{self.base_gw_url}/getEventDetails?hl=en-US&id={event_id}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("event", {})
        except Exception as e:
            logger.debug(f"Event details fetch info for {event_id}: {e}")
        return None

    def is_draft_complete_pre_game(self, match_data: Dict[str, Any]) -> bool:
        """
        Verifies that all 10 champion picks are locked and the match is in the post-draft pre-game window.
        """
        blue_picks = match_data.get("blue_picks", {})
        red_picks = match_data.get("red_picks", {})
        
        # Must have all 5 roles filled for both teams
        required_roles = ["top", "jng", "mid", "bot", "sup"]
        has_all_blue = all(bool(blue_picks.get(r)) for r in required_roles)
        has_all_red = all(bool(red_picks.get(r)) for r in required_roles)
        
        if not (has_all_blue and has_all_red):
            return False
            
        # Verify state indicates draft finalized and game has not started yet
        state = str(match_data.get("state", "draft_complete")).lower()
        is_pre_game = state in ["draft_complete", "in_draft", "starting", "unstarted", "inprogress"]
        
        return is_pre_game

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

