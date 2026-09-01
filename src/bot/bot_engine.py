"""
Autonomous 24/7 LoL +EV Draft Trading Bot Engine.
Evaluates incoming drafts, executes paper/live fractional Kelly trades, and sends Discord alerts.
"""
try:
    import onnxruntime  # Initialize runtime before other C-extensions on Windows
except Exception:
    pass

import os
import sys
import time
import json
import yaml
import difflib
import logging
import threading
import numpy as np
from typing import Dict, Any, Optional, List, Set, Tuple

# Ensure workspace root is in python path
workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from src.bot.discord_notifier import DiscordNotifier
from src.bot.paper_trader import PaperPortfolio
from src.bot.live_feed_listener import LiveFeedListener
from src.ratings import DynamicRatingEngine
from src.features import AdvancedDraftFeatureExtractor
from src.vision.vision_pipeline import VisionDraftPipeline

logger = logging.getLogger("LoLDraftBot")

TEAM_ALIAS_MAP = {
    "GEN": "Gen.G", "Gen.G Esports": "Gen.G", "GEN.G": "Gen.G",
    "T1": "T1", "SK Telecom T1": "T1", "SKT T1": "T1",
    "HLE": "Hanwha Life Esports", "Hanwha Life": "Hanwha Life Esports",
    "DK": "Dplus KIA", "DWG KIA": "Dplus KIA", "Damwon Gaming": "Dplus KIA",
    "KT": "KT Rolster", "KT Rolster": "KT Rolster",
    "BLG": "Bilibili Gaming", "Bilibili Gaming": "Bilibili Gaming",
    "TES": "Top Esports", "TOP Esports": "Top Esports",
    "JDG": "JD Gaming", "JD Gaming": "JD Gaming",
    "LNG": "LNG Esports", "LNG Esports": "LNG Esports",
    "WBG": "Weibo Gaming", "Weibo Gaming": "Weibo Gaming",
    "G2": "G2 Esports", "G2 Esports": "G2 Esports",
    "FNC": "Fnatic", "Fnatic": "Fnatic",
    "FLY": "FlyQuest", "FlyQuest": "FlyQuest",
    "TL": "Team Liquid", "Team Liquid": "Team Liquid"
}

class DraftBotEngine:
    def __init__(self, config_path: str = "config/bot_config.yaml"):
        if not os.path.isabs(config_path):
            config_path = os.path.join(workspace_root, config_path)
            
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

        champ_meta_path = os.path.join(workspace_root, "config/champion_metadata.json")
        with open(champ_meta_path, "r", encoding="utf-8") as f:
            self.champ_meta = json.load(f)

        self.all_champs = list(self.champ_meta.keys())
        self.extractor = AdvancedDraftFeatureExtractor(champ_meta_path)
        
        # Load components
        self.notifier = DiscordNotifier(webhook_url=os.getenv("DISCORD_WEBHOOK_URL") or self.config.get("discord_webhook_url"))
        self.portfolio = PaperPortfolio(
            db_path=os.path.join(workspace_root, self.config.get("db_path", "data/bot/paper_portfolio.db")),
            initial_bankroll=self.config.get("initial_bankroll", 10000.0)
        )
        self.listener = LiveFeedListener(target_leagues=self.config.get("target_leagues", ["LCK", "LPL", "LEC", "LCS"]))
        
        # Load trained residual model if available
        self.model = None
        model_path = os.path.join(workspace_root, "data/cache/residual_draft_model.joblib")
        if os.path.exists(model_path):
            try:
                from src.models.tree_models import ResidualDraftModel
                self.model = ResidualDraftModel()
                self.model.load(model_path)
                logger.info(f"Loaded trained CatBoost model from {model_path}")
            except Exception as e:
                logger.warning(f"Could not load serialized model: {e}")

        # Base team ratings
        self.team_ratings = {
            "Gen.G": 1720, "T1": 1680, "Hanwha Life Esports": 1670, "Dplus KIA": 1580, "KT Rolster": 1550,
            "Bilibili Gaming": 1730, "Top Esports": 1690, "JD Gaming": 1640, "LNG Esports": 1620, "Weibo Gaming": 1610,
            "G2 Esports": 1620, "Fnatic": 1550, "BDS": 1520, "MAD Lions": 1490,
            "FlyQuest": 1560, "Team Liquid": 1550, "Cloud9": 1520, "100 Thieves": 1480
        }
        
        self.processed_drafts = set()
        
        # Initialize Computer Vision Stream Ingestion Pipeline
        self.vision_config = self.config.get("vision", {})
        self.vision_pipeline = VisionDraftPipeline(
            stream_source=self.vision_config.get("default_source", "screen"),
            monitor_index=self.vision_config.get("monitor_index", 1),
            stability_count=self.vision_config.get("stability_count", 2),
            on_draft_locked=self.on_vision_draft_locked
        )
        
        # Autonomous 24/7 Stream Discovery Workers
        self.active_stream_monitors: Dict[str, threading.Thread] = {}
        self.active_stream_stops: Dict[str, threading.Event] = {}
        logger.info("DraftBotEngine initialized successfully with Autonomous Vision Stream Ingestion.")

    def on_vision_draft_locked(self, match_data: dict):
        """
        Callback triggered when Vision Pipeline detects and confirms a 10-champion finalized draft.
        """
        logger.info(f"⚡ [VISION EVENT] Processing visually locked draft: {match_data['match_id']}")
        self.process_match(match_data, is_dry_run=self.config.get("dry_run", True))

    def normalize_team(self, name: str) -> str:
        if not name: return "Unknown"
        s = name.strip()
        return TEAM_ALIAS_MAP.get(s, s)

    def match_champion(self, raw_name: str) -> str:
        if not raw_name: return "Aatrox"
        matches = difflib.get_close_matches(raw_name.strip(), self.all_champs, n=1, cutoff=0.4)
        return matches[0] if matches else raw_name.strip()

    def evaluate_draft(self, match_data: dict) -> dict:
        match_id = match_data["match_id"]
        league = match_data.get("league", "PRO")
        b_team = self.normalize_team(match_data["blue_team"])
        r_team = self.normalize_team(match_data["red_team"])
        patch_str = str(match_data.get("patch", "14.18"))
        
        r_b = self.team_ratings.get(b_team, 1500.0) + self.config.get("side_bias_elo", 35.0)
        r_r = self.team_ratings.get(r_team, 1500.0)
        p_base = float(np.clip(1.0 / (1.0 + 10.0 ** (-(r_b - r_r) / 400.0)), 0.03, 0.97))
        
        b_picks = {r: self.match_champion(match_data["blue_picks"][r]) for r in ["top", "jng", "mid", "bot", "sup"]}
        r_picks = {r: self.match_champion(match_data["red_picks"][r]) for r in ["top", "jng", "mid", "bot", "sup"]}
        
        b_comp = self.extractor.extract_composition_vector(list(b_picks.values()))
        r_comp = self.extractor.extract_composition_vector(list(r_picks.values()))
        
        diff_cc = b_comp['cc_score'] - r_comp['cc_score']
        diff_eng = b_comp['engage_score'] - r_comp['engage_score']
        diff_sc = b_comp['scaling_score'] - r_comp['scaling_score']
        diff_front = b_comp['frontline_count'] - r_comp['frontline_count']
        
        draft_delta = (diff_cc * 0.008) + (diff_eng * 0.006) + (diff_sc * 0.015) + (diff_front * 0.012)
        if b_comp['ad_share'] > 0.85 and r_comp['tank_count'] >= 2: draft_delta -= 0.06
        if r_comp['ad_share'] > 0.85 and b_comp['tank_count'] >= 2: draft_delta += 0.06
        
        draft_delta = float(np.clip(draft_delta, -0.08, 0.08))
        p_final = float(np.clip(p_base + draft_delta, 0.03, 0.97))
        
        o_b = float(match_data.get("market_odds_blue", round(1.0 / (p_base + 0.02), 2)))
        o_r = float(match_data.get("market_odds_red", round(1.0 / ((1.0 - p_base) + 0.02), 2)))
        
        ev_b = (p_final * o_b) - 1.0
        ev_r = ((1.0 - p_final) * o_r) - 1.0
        
        return {
            "match_id": match_id,
            "league": league,
            "patch": patch_str,
            "blue_team": b_team,
            "red_team": r_team,
            "blue_picks": b_picks,
            "red_picks": r_picks,
            "p_base_blue": p_base,
            "draft_delta": draft_delta,
            "p_final_blue": p_final,
            "market_odds_blue": o_b,
            "market_odds_red": o_r,
            "ev_blue": ev_b,
            "ev_red": ev_r
        }

    def process_match(self, match_data: dict, is_dry_run: bool = True):
        match_id = match_data["match_id"]
        if match_id in self.processed_drafts:
            return
            
        res = self.evaluate_draft(match_data)
        self.processed_drafts.add(match_id)
        
        ev_thresh = self.config.get("ev_threshold", 0.025)
        kelly_frac = self.config.get("kelly_fraction", 0.20)
        max_bet_frac = self.config.get("max_bet_fraction", 0.035)
        
        rec_side = None
        target_ev = 0.0
        target_odds = 1.0
        target_prob = 0.5
        
        if res["ev_blue"] >= ev_thresh and res["ev_blue"] >= res["ev_red"]:
            rec_side = "Blue"
            target_ev = res["ev_blue"]
            target_odds = res["market_odds_blue"]
            target_prob = res["p_final_blue"]
        elif res["ev_red"] >= ev_thresh:
            rec_side = "Red"
            target_ev = res["ev_red"]
            target_odds = res["market_odds_red"]
            target_prob = 1.0 - res["p_final_blue"]
            
        if rec_side:
            # Check Circuit Breaker
            if not self.portfolio.check_daily_circuit_breaker(self.config.get("max_daily_drawdown_pct", 10.0)):
                logger.warning(f"Trade skipped for match {match_id}: Daily circuit breaker active.")
                return
                
            summary = self.portfolio.get_portfolio_summary()
            current_bankroll = summary["bankroll"]
            
            b = target_odds - 1.0
            f_star = min((target_prob * (b + 1.0) - 1.0) / b * kelly_frac, max_bet_frac)
            stake = round(f_star * current_bankroll, 2)
            
            if stake > 0:
                self.portfolio.record_trade(
                    match_id=match_id,
                    league=res["league"],
                    blue_team=res["blue_team"],
                    red_team=res["red_team"],
                    side_bet=rec_side,
                    odds=target_odds,
                    model_prob=target_prob,
                    ev=target_ev,
                    stake=stake
                )
                
                # Send Discord Notification ONLY when an actual bet is placed
                self.notifier.send_trade_signal(
                    match_id=match_id,
                    league=res["league"],
                    blue_team=res["blue_team"],
                    red_team=res["red_team"],
                    blue_picks=res["blue_picks"],
                    red_picks=res["red_picks"],
                    p_base_blue=res["p_base_blue"],
                    draft_delta=res["draft_delta"],
                    p_final_blue=res["p_final_blue"],
                    market_odds_blue=res["market_odds_blue"],
                    market_odds_red=res["market_odds_red"],
                    ev_blue=res["ev_blue"],
                    ev_red=res["ev_red"],
                    recommended_side=rec_side,
                    stake_usd=stake,
                    bankroll=current_bankroll,
                    is_dry_run=is_dry_run
                )
                logger.info(f"🚨 [BET PLACED] Wagered ${stake:,.2f} on {res['blue_team'] if rec_side == 'Blue' else res['red_team']} vs {res['red_team'] if rec_side == 'Blue' else res['blue_team']} @ {target_odds:.2f} (EV: +{target_ev*100:.2f}%)")
        else:
            logger.info(f"Match {match_id} ({res['blue_team']} vs {res['red_team']}): PASS / No +EV edge (EV Blue: {res['ev_blue']*100:+.2f}%, EV Red: {res['ev_red']*100:+.2f}%). Webhook kept silent.")

    def run_poll_cycle(self):
        logger.info("Polling live schedules & matches...")
        matches = self.listener.fetch_live_schedule()
        
        # If an API error occurred during schedule fetch, dispatch Discord error alert (throttled)
        if self.listener.last_error:
            err = self.listener.last_error
            status = err.get("status_code", 0)
            err_text = f"HTTP {status}: {err.get('text', 'Network/Endpoint error')[:200]}"
            self.notifier.send_error_alert(
                error_title=f"Riot Gateway API Error ({status})",
                error_details=f"Live feed poller failed to retrieve match schedule from `{err.get('url')}`.\n**Details:** `{err_text}`",
                error_type=f"RIOT_API_{status}" if status > 0 else "RIOT_API_NETWORK",
                cooldown_seconds=1800 # Alert at most once every 30 minutes for this error
            )
            return

        logger.info(f"Found {len(matches)} scheduled/ongoing matches.")
        for m in matches:
            match_id = m.get("match_id")
            if match_id in self.processed_drafts:
                continue
                
            # If match has picks and draft is complete before game start, evaluate & place bet
            if "blue_picks" in m and "red_picks" in m:
                if self.listener.is_draft_complete_pre_game(m):
                    logger.info(f"🎯 Draft finalized for {m['blue_team']} vs {m['red_team']} ({m['league']}). Evaluating trade opportunity...")
                    self.process_match(m, is_dry_run=self.config.get("dry_run", True))
            elif m.get("state") in ["inprogress", "unstarted"] and self.vision_config.get("enabled", True):
                # Automatic Live Stream Discovery & Vision Ingestion
                league = m.get("league", "")
                stream_url = self.resolve_stream_source_for_league(league)
                if stream_url:
                    self._ensure_stream_monitor_running(league, stream_url, m)

    def resolve_stream_source_for_league(self, league_name: str) -> Optional[str]:
        """
        Automatically resolves the official live broadcast URL for a target league.
        """
        if not league_name:
            return None
            
        l_upper = league_name.upper()
        yt_map = self.vision_config.get("youtube_channels", {})
        tw_map = self.vision_config.get("twitch_channels", {})
        
        # 1. Direct configured mapping
        for k, v in yt_map.items():
            if k.upper() in l_upper or l_upper in k.upper():
                return v
        for k, v in tw_map.items():
            if k.upper() in l_upper or l_upper in k.upper():
                return v

        # 2. Canonical League Fallbacks
        if "LCK" in l_upper:
            return "https://www.youtube.com/@LCKglobal/live"
        elif "LPL" in l_upper:
            return "https://www.youtube.com/@LPLEnglish/live"
        elif "LEC" in l_upper:
            return "https://www.youtube.com/@LEC/live"
        elif "LCS" in l_upper:
            return "https://www.youtube.com/@LCS/live"
        elif any(w in l_upper for w in ["WORLD", "WLD", "MSI", "EWC"]):
            return "https://www.youtube.com/@lolesports/live"
            
        return None

    def _ensure_stream_monitor_running(self, league: str, stream_url: str, match_info: dict):
        """
        Spawns a background thread to autonomously monitor the live stream for draft finalization.
        """
        if league in self.active_stream_monitors and self.active_stream_monitors[league].is_alive():
            return  # Already actively monitoring this stream

        logger.info(f"📡 [AUTO-DISCOVERY] Found active/upcoming {league} match ({match_info.get('blue_team')} vs {match_info.get('red_team')})!")
        logger.info(f"   📺 Attaching autonomous Vision Stream Monitor to: {stream_url}")
        
        stop_event = threading.Event()
        self.active_stream_stops[league] = stop_event
        
        def monitor_worker():
            pipeline = VisionDraftPipeline(
                stream_source=stream_url,
                stability_count=self.vision_config.get("stability_count", 2),
                on_draft_locked=self.on_vision_draft_locked
            )
            if not pipeline.grabber.open():
                logger.warning(f"Could not connect to live stream for {league} ({stream_url}). Will retry next cycle.")
                return
                
            interval = self.vision_config.get("poll_interval_seconds", 2.5)
            logger.info(f"👁️ Vision Monitor scanning {league} broadcast stream autonomously...")
            try:
                while not stop_event.is_set():
                    frame = pipeline.grabber.read_frame()
                    if frame is not None:
                        pipeline.check_frame_and_dispatch(frame, league=league)
                    time.sleep(interval)
            except Exception as e:
                logger.error(f"Error in Vision Monitor worker for {league}: {e}")
            finally:
                pipeline.grabber.close()
                logger.info(f"Vision Monitor stopped for {league}.")

        t = threading.Thread(target=monitor_worker, daemon=True, name=f"VisionMonitor_{league}")
        t.start()
        self.active_stream_monitors[league] = t

    def evaluate_vision_image(self, image_input: Any, league: str = "PRO") -> Optional[Dict[str, Any]]:
        """
        Takes an image path, screenshot, or video frame and runs the vision pipeline.
        If a valid 10-champion draft is parsed, evaluates EV and places trade.
        """
        logger.info("Evaluating image with Vision Draft Pipeline...")
        detection = self.vision_pipeline.process_image(image_input)
        if detection and detection.get("is_complete"):
            match_data = {
                "match_id": f"VISION_IMG_{detection['blue_team']}_vs_{detection['red_team']}_{int(time.time())}",
                "league": league,
                "state": "draft_complete",
                "blue_team": detection["blue_team"],
                "red_team": detection["red_team"],
                "blue_picks": detection["blue_picks"],
                "red_picks": detection["red_picks"]
            }
            logger.info(f"✅ Vision parsed complete draft: {detection['blue_team']} vs {detection['red_team']}")
            self.process_match(match_data, is_dry_run=self.config.get("dry_run", True))
            return match_data
        else:
            logger.warning("Vision pipeline could not detect a complete 10-champion draft in the provided image.")
            return None

    def run_vision_stream_daemon(
        self,
        source: Optional[str] = None,
        league: str = "PRO",
        poll_interval: Optional[float] = None
    ):
        """
        Launches continuous autonomous vision monitoring over a live stream or screen.
        """
        stream_src = source or self.vision_config.get("default_source", "screen")
        interval = poll_interval or self.vision_config.get("poll_interval_seconds", 2.5)
        
        logger.info(f"Starting Autonomous Vision Stream Daemon on '{stream_src}' for {league}...")
        self.vision_pipeline.grabber.source = stream_src
        self.vision_pipeline.start_stream_monitoring(
            league=league,
            poll_interval_seconds=interval
        )


