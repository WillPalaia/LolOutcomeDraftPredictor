"""
Interactive Real-Time Inference & Draft Evaluator CLI.
Allows evaluating live match drafts and finding +EV prediction market positions.
"""
import os
import sys
import json
import yaml
import numpy as np
import pandas as pd
from src.ratings import DynamicRatingEngine
from src.features import DraftFeatureExtractor
from src.models.tree_models import CatBoostDraftModel
from src.models.calibrator import ProbabilityCalibrator
from src.backtest.market_simulator import MarketOddsSimulator

class DraftPredictor:
    def __init__(self, 
                 model_path: str = "data/cache/catboost_model.cbm",
                 config_path: str = "config/default_config.yaml"):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        self.feature_extractor = DraftFeatureExtractor("config/champion_metadata.json")
        self.model = CatBoostDraftModel()
        if os.path.exists(model_path):
            self.model.load(model_path)
            self.model_loaded = True
        else:
            self.model_loaded = False
            
        self.market_sim = MarketOddsSimulator(vig=self.config['backtest']['market_vig'])

    def evaluate_draft(self, 
                       blue_team: str, 
                       red_team: str, 
                       blue_picks: dict, 
                       red_picks: dict,
                       blue_rating: float = 1550.0,
                       red_rating: float = 1500.0,
                       market_odds_blue: float = None,
                       market_odds_red: float = None) -> dict:
        """
        Evaluate full draft match.
        blue_picks = {'top': 'Aatrox', 'jng': 'Maokai', 'mid': 'Orianna', 'bot': 'Kalista', 'sup': 'Senna'}
        """
        # 1. Baseline team probability
        side_bias = self.config['ratings']['side_bias_elo']
        diff = (blue_rating + side_bias - red_rating) / 400.0
        p_baseline = 1.0 / (1.0 + 10.0 ** (-diff))
        
        # 2. Extract draft composition features
        b_picks_list = [blue_picks['top'], blue_picks['jng'], blue_picks['mid'], blue_picks['bot'], blue_picks['sup']]
        r_picks_list = [red_picks['top'], red_picks['jng'], red_picks['mid'], red_picks['bot'], red_picks['sup']]
        
        b_comp = self.feature_extractor.extract_composition_vector(b_picks_list)
        r_comp = self.feature_extractor.extract_composition_vector(r_picks_list)
        
        # Differential metrics
        diff_cc = b_comp['cc_score'] - r_comp['cc_score']
        diff_engage = b_comp['engage_score'] - r_comp['engage_score']
        diff_scaling = b_comp['scaling_score'] - r_comp['scaling_score']
        diff_ad = b_comp['ad_share'] - r_comp['ad_share']
        diff_ap = b_comp['ap_share'] - r_comp['ap_share']
        
        # Draft advantage estimate
        draft_delta = (
            (diff_cc * 0.012) +
            (diff_engage * 0.010) +
            (diff_scaling * 0.025) -
            (max(0, b_comp['ad_share'] - 0.85) * r_comp['tank_count'] * 0.08) +
            (max(0, r_comp['ad_share'] - 0.85) * b_comp['tank_count'] * 0.08)
        )
        
        # Combine baseline + draft delta
        p_final = float(np.clip(p_baseline + draft_delta, 0.02, 0.98))
        
        # Default market odds if not supplied
        if market_odds_blue is None or market_odds_red is None:
            market_lines = self.market_sim.generate_market_lines(p_baseline)
            market_odds_blue = market_lines['odds_blue']
            market_odds_red = market_lines['odds_red']
            
        ev_blue = (p_final * market_odds_blue) - 1.0
        ev_red = ((1.0 - p_final) * market_odds_red) - 1.0
        
        # Bet recommendation
        ev_thresh = self.config['backtest']['ev_threshold']
        if ev_blue >= ev_thresh and ev_blue >= ev_red:
            rec = f"BET BLUE ({blue_team})"
            best_ev = ev_blue
            best_side = "Blue"
        elif ev_red >= ev_thresh:
            rec = f"BET RED ({red_team})"
            best_ev = ev_red
            best_side = "Red"
        else:
            rec = "PASS / NO VALUE"
            best_ev = max(ev_blue, ev_red)
            best_side = "None"

        return {
            "teams": {"blue": blue_team, "red": red_team},
            "baseline_win_prob_blue": round(p_baseline * 100, 2),
            "baseline_win_prob_red": round((1.0 - p_baseline) * 100, 2),
            "draft_edge_blue_pct": round(draft_delta * 100, 2),
            "final_model_prob_blue": round(p_final * 100, 2),
            "final_model_prob_red": round((1.0 - p_final) * 100, 2),
            "market_odds": {"blue": market_odds_blue, "red": market_odds_red},
            "expected_value": {"blue_ev_pct": round(ev_blue * 100, 2), "red_ev_pct": round(ev_red * 100, 2)},
            "recommendation": rec,
            "composition_metrics": {
                "blue_cc": b_comp['cc_score'], "red_cc": r_comp['cc_score'],
                "blue_engage": b_comp['engage_score'], "red_engage": r_comp['engage_score'],
                "blue_scaling": round(b_comp['scaling_score'], 1), "red_scaling": round(r_comp['scaling_score'], 1),
                "blue_ad_share": round(b_comp['ad_share'], 2), "red_ad_share": round(r_comp['ad_share'], 2)
            }
        }

if __name__ == "__main__":
    predictor = DraftPredictor()
    res = predictor.evaluate_draft(
        blue_team="T1",
        red_team="Gen.G",
        blue_picks={"top": "Rumble", "jng": "Jarvan IV", "mid": "Orianna", "bot": "Kalista", "sup": "Renata Glasc"},
        red_picks={"top": "K'Sante", "jng": "Maokai", "mid": "Azir", "bot": "Zeri", "sup": "Lulu"},
        blue_rating=1620,
        red_rating=1640,
        market_odds_blue=2.10,
        market_odds_red=1.75
    )
    print(json.dumps(res, indent=2))
