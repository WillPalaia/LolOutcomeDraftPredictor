"""
Autonomous 24/7 LoL +EV Draft Trading Bot Engine.
Evaluates incoming drafts, executes paper/live fractional Kelly trades, and sends Discord alerts.
"""
import os
import sys
import time
import json
import yaml
import difflib
import logging
import numpy as np

# Ensure workspace root is in python path
workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from src.bot.discord_notifier import DiscordNotifier
from src.bot.paper_trader import PaperPortfolio
from src.bot.live_feed_listener import LiveFeedListener
from src.ratings import DynamicRatingEngine
from src.features import AdvancedDraftFeatureExtractor

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
        logger.info("DraftBotEngine initialized successfully.")

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
            elif m.get("state") == "inprogress":
                logger.info(f"Live match monitored: {m['blue_team']} vs {m['red_team']} ({m['league']})")

    def run_daemon(self, poll_interval_seconds: int = 30):
        logger.info(f"Starting 24/7 Autonomous Draft Bot Daemon (Interval: {poll_interval_seconds}s)...")
        logger.info("Discord notifications configured for BET PLACEMENT ONLY (No startup/status spam).")
        while True:
            try:
                self.run_poll_cycle()
            except Exception as e:
                logger.error(f"Error during poll cycle: {e}")
            time.sleep(poll_interval_seconds)

