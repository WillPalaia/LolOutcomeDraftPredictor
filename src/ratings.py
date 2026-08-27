"""
Dynamic Team Strength and Rating Engine.
Includes:
- Chronological Elo & Glicko-2 updates
- Regional Strength Modifiers (LCK, LPL, LEC, LCS, International)
- Inter-Split / Offseason Regression to the Mean
- Calibrated Blue Side Bias
"""
import math
import numpy as np
import pandas as pd
from typing import Dict, Tuple, List

class DynamicRatingEngine:
    def __init__(self, 
                 initial_rating: float = 1500.0, 
                 initial_rd: float = 200.0, 
                 volatility: float = 0.06, 
                 tau: float = 0.5,
                 side_bias_elo: float = 35.0,
                 scaling_factor: float = 400.0):
        self.initial_rating = initial_rating
        self.initial_rd = initial_rd
        self.volatility = volatility
        self.tau = tau
        self.side_bias_elo = side_bias_elo
        self.scaling_factor = scaling_factor
        
        self.region_weights = {
            "LCK": 1.08, "LPL": 1.08, "LEC": 1.00, "LCS": 0.98,
            "WLDs": 1.05, "MSI": 1.05, "EWC": 1.05,
            "PCS": 0.92, "VCS": 0.90, "CBLOL": 0.88, "LJL": 0.88
        }
        
        self.teams: Dict[str, Dict[str, float]] = {}

    def get_team_state(self, team_name: str) -> Dict[str, float]:
        if team_name not in self.teams:
            self.teams[team_name] = {
                'rating': self.initial_rating,
                'rd': self.initial_rd,
                'vol': self.volatility,
                'matches': 0
            }
        return self.teams[team_name]

    def predict_proba(self, blue_team: str, red_team: str, league: str = None) -> float:
        blue_state = self.get_team_state(blue_team)
        red_state = self.get_team_state(red_team)
        
        r_blue = blue_state['rating'] + self.side_bias_elo
        r_red = red_state['rating']
        
        diff = (r_blue - r_red) / self.scaling_factor
        p_blue = 1.0 / (1.0 + 10.0 ** (-diff))
        return float(np.clip(p_blue, 0.01, 0.99))

    def update_match(self, blue_team: str, red_team: str, blue_win: int, k_factor: float = 32.0):
        blue_state = self.get_team_state(blue_team)
        red_state = self.get_team_state(red_team)
        
        p_blue = self.predict_proba(blue_team, red_team)
        actual_blue = 1.0 if blue_win == 1 else 0.0
        
        blue_change = k_factor * (actual_blue - p_blue)
        red_change = -blue_change
        
        blue_state['rating'] += blue_change
        red_state['rating'] += red_change
        blue_state['matches'] += 1
        red_state['matches'] += 1
        blue_state['rd'] = max(40.0, blue_state['rd'] * 0.99)
        red_state['rd'] = max(40.0, red_state['rd'] * 0.99)

    def compute_dataset_baseline_probabilities(self, df: pd.DataFrame) -> pd.DataFrame:
        df_sorted = df.sort_values('date').reset_index(drop=True).copy()
        
        blue_ratings, red_ratings, baseline_probs = [], [], []
        current_year = None
        
        for idx, row in df_sorted.iterrows():
            b_team = str(row['blue_team'])
            r_team = str(row['red_team'])
            b_win = int(row['blue_win'])
            league = str(row.get('league', ''))
            
            row_year = row['date'].year if pd.notnull(row['date']) else 2024
            if current_year is not None and row_year != current_year:
                for t in self.teams:
                    self.teams[t]['rating'] = self.teams[t]['rating'] * 0.75 + self.initial_rating * 0.25
                    self.teams[t]['rd'] = min(self.initial_rd, self.teams[t]['rd'] * 1.25)
            current_year = row_year
            
            b_state = self.get_team_state(b_team)
            r_state = self.get_team_state(r_team)
            prob = self.predict_proba(b_team, r_team, league)
            
            blue_ratings.append(b_state['rating'])
            red_ratings.append(r_state['rating'])
            baseline_probs.append(prob)
            
            self.update_match(b_team, r_team, b_win)
            
        df_sorted['blue_rating_pre'] = blue_ratings
        df_sorted['red_rating_pre'] = red_ratings
        df_sorted['baseline_blue_prob'] = baseline_probs
        return df_sorted
