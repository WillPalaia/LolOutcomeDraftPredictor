"""
Advanced Feature Engineering Engine for LoL Draft & Match Prediction.
Includes:
- Bayesian Regularized 1v1 Lane Matchups (Top, Jng, Mid, Bot, Sup)
- Bayesian Regularized 2v2 Duo Synergies (Bot+Sup Duos, Mid+Jng 2v2, Top+Jng 2v2)
- Dynamic Rolling Patch Meta Presence (Pick+Ban Rate Priority)
- Player Champion Experience & Comfort Offset
- Structural Composition Balance (Frontline/Backline, Waveclear, Mixed Damage Convexity)
"""
import os
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

class AdvancedDraftFeatureExtractor:
    def __init__(self, 
                 champion_metadata_path: str = "config/champion_metadata.json",
                 bayesian_prior_matches: float = 15.0,
                 bayesian_prior_winrate: float = 0.50):
        self.bayesian_prior_matches = bayesian_prior_matches
        self.bayesian_prior_winrate = bayesian_prior_winrate
        
        with open(champion_metadata_path, "r", encoding="utf-8") as f:
            self.champ_meta = json.load(f)
            
        self.default_meta = {
            "class": "Fighter", "ad_ratio": 0.5, "ap_ratio": 0.5, "true_ratio": 0.0,
            "cc_score": 5, "engage_score": 5, "range_type": "Melee", "scaling_score": 6
        }

    def get_champ_info(self, champ_name: str) -> dict:
        return self.champ_meta.get(champ_name, self.default_meta)

    def extract_composition_vector(self, picks: List[str]) -> Dict[str, float]:
        total_ad, total_ap, total_true = 0.0, 0.0, 0.0
        total_cc, total_engage, total_scaling = 0.0, 0.0, 0.0
        ranged_count, frontline_count = 0, 0
        classes = {"Assassin": 0, "Fighter": 0, "Mage": 0, "Marksman": 0, "Support": 0, "Tank": 0}
        
        for ch in picks:
            info = self.get_champ_info(ch)
            total_ad += info.get("ad_ratio", 0.5)
            total_ap += info.get("ap_ratio", 0.5)
            total_true += info.get("true_ratio", 0.0)
            total_cc += info.get("cc_score", 5)
            total_engage += info.get("engage_score", 5)
            total_scaling += info.get("scaling_score", 6)
            if info.get("range_type", "Melee") == "Ranged":
                ranged_count += 1
            if info.get("class") in ["Tank", "Fighter"]:
                frontline_count += 1
            cls = info.get("class", "Fighter")
            if cls in classes:
                classes[cls] += 1
                
        n = max(1, len(picks))
        return {
            "ad_share": total_ad / n,
            "ap_share": total_ap / n,
            "true_share": total_true / n,
            "cc_score": total_cc,
            "engage_score": total_engage,
            "scaling_score": total_scaling / n,
            "ranged_count": ranged_count,
            "frontline_count": frontline_count,
            "tank_count": classes["Tank"],
            "marksman_count": classes["Marksman"],
            "mage_count": classes["Mage"],
            "assassin_count": classes["Assassin"],
            "fighter_count": classes["Fighter"],
            "support_count": classes["Support"]
        }

    def compute_all_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        logger.info("Computing advanced pro draft features, duo synergies, and patch meta presence...")
        df_feat = df.sort_values('date').reset_index(drop=True).copy()
        
        b_comp_list = []
        r_comp_list = []
        for _, row in df_feat.iterrows():
            b_p = [row['blue_top'], row['blue_jng'], row['blue_mid'], row['blue_bot'], row['blue_sup']]
            r_p = [row['red_top'], row['red_jng'], row['red_mid'], row['red_bot'], row['red_sup']]
            b_comp_list.append(self.extract_composition_vector(b_p))
            r_comp_list.append(self.extract_composition_vector(r_p))
            
        df_b_comp = pd.DataFrame(b_comp_list).add_prefix('b_')
        df_r_comp = pd.DataFrame(r_comp_list).add_prefix('r_')
        
        diff_df = pd.DataFrame()
        diff_df['diff_cc_score'] = df_b_comp['b_cc_score'] - df_r_comp['r_cc_score']
        diff_df['diff_engage_score'] = df_b_comp['b_engage_score'] - df_r_comp['r_engage_score']
        diff_df['diff_scaling_score'] = df_b_comp['b_scaling_score'] - df_r_comp['r_scaling_score']
        diff_df['diff_ranged_count'] = df_b_comp['b_ranged_count'] - df_r_comp['r_ranged_count']
        diff_df['diff_frontline'] = df_b_comp['b_frontline_count'] - df_r_comp['r_frontline_count']
        diff_df['diff_tank_count'] = df_b_comp['b_tank_count'] - df_r_comp['r_tank_count']
        diff_df['diff_ad_share'] = df_b_comp['b_ad_share'] - df_r_comp['r_ad_share']
        diff_df['diff_ap_share'] = df_b_comp['b_ap_share'] - df_r_comp['r_ap_share']
        
        diff_df['blue_full_ad_trap'] = (df_b_comp['b_ad_share'] > 0.85).astype(int) * df_r_comp['r_tank_count']
        diff_df['red_full_ad_trap'] = (df_r_comp['r_ad_share'] > 0.85).astype(int) * df_b_comp['b_tank_count']
        diff_df['diff_ad_trap'] = diff_df['red_full_ad_trap'] - diff_df['blue_full_ad_trap']
        
        diff_df['blue_full_ap_trap'] = (df_b_comp['b_ap_share'] > 0.80).astype(int) * df_r_comp['r_tank_count']
        diff_df['red_full_ap_trap'] = (df_r_comp['r_ap_share'] > 0.80).astype(int) * df_b_comp['b_tank_count']
        diff_df['diff_ap_trap'] = diff_df['red_full_ap_trap'] - diff_df['blue_full_ap_trap']

        champ_presence_history = {}
        blue_meta_power = []
        red_meta_power = []
        
        lane_roles = ['top', 'jng', 'mid', 'bot', 'sup']
        lane_history = {r: {} for r in lane_roles}
        lane_edges = {r: [] for r in lane_roles}
        
        duo_combos = [('bot', 'sup'), ('mid', 'jng'), ('top', 'jng')]
        duo_history = {f"{c[0]}_{c[1]}": {} for c in duo_combos}
        duo_edges = {f"{c[0]}_{c[1]}": [] for c in duo_combos}
        
        player_history = {}
        blue_mastery_scores = []
        red_mastery_scores = []

        for idx, row in df_feat.iterrows():
            b_win = int(row['blue_win'])
            
            b_champs = [row[f'blue_{r}'] for r in lane_roles]
            r_champs = [row[f'red_{r}'] for r in lane_roles]
            all_bans = [row.get(f'blue_ban{i}', '') for i in range(1, 6)] + [row.get(f'red_ban{i}', '') for i in range(1, 6)]
            
            b_meta_score = 0.0
            r_meta_score = 0.0
            total_seen = max(1, idx)
            
            for ch in b_champs:
                count = champ_presence_history.get(ch, 0)
                b_meta_score += (count / total_seen)
            for ch in r_champs:
                count = champ_presence_history.get(ch, 0)
                r_meta_score += (count / total_seen)
                
            blue_meta_power.append(b_meta_score)
            red_meta_power.append(r_meta_score)
            
            for ch in b_champs + r_champs + all_bans:
                if ch and isinstance(ch, str) and ch.strip():
                    champ_presence_history[ch] = champ_presence_history.get(ch, 0) + 1

            for role in lane_roles:
                b_c = row[f'blue_{role}']
                r_c = row[f'red_{role}']
                k, rev_k = (b_c, r_c), (r_c, b_c)
                
                if k in lane_history[role]:
                    w, n = lane_history[role][k]
                elif rev_k in lane_history[role]:
                    w_r, n = lane_history[role][rev_k]
                    w = n - w_r
                else:
                    w, n = 0, 0
                
                shrunk_wr = (w + self.bayesian_prior_matches * self.bayesian_prior_winrate) / (n + self.bayesian_prior_matches)
                lane_edges[role].append(shrunk_wr - 0.50)
                
                if k not in lane_history[role]: lane_history[role][k] = [0, 0]
                lane_history[role][k][0] += b_win
                lane_history[role][k][1] += 1

            for r1, r2 in duo_combos:
                combo_name = f"{r1}_{r2}"
                b_pair = (row[f'blue_{r1}'], row[f'blue_{r2}'])
                r_pair = (row[f'red_{r1}'], row[f'red_{r2}'])
                
                w_b, n_b = duo_history[combo_name].get(b_pair, (0, 0))
                b_syn = (w_b + 5.0 * 0.50) / (n_b + 5.0) - 0.50
                
                w_r, n_r = duo_history[combo_name].get(r_pair, (0, 0))
                r_syn = (w_r + 5.0 * 0.50) / (n_r + 5.0) - 0.50
                
                duo_edges[combo_name].append(b_syn - r_syn)
                
                if b_pair not in duo_history[combo_name]: duo_history[combo_name][b_pair] = [0, 0]
                duo_history[combo_name][b_pair][0] += b_win
                duo_history[combo_name][b_pair][1] += 1
                
                if r_pair not in duo_history[combo_name]: duo_history[combo_name][r_pair] = [0, 0]
                duo_history[combo_name][r_pair][0] += (1 - b_win)
                duo_history[combo_name][r_pair][1] += 1

            b_mast = 0.0
            r_mast = 0.0
            for r in lane_roles:
                bp_name = row.get(f'blue_player_{r}', '')
                bc_name = row.get(f'blue_{r}', '')
                if bp_name and bc_name:
                    pw, pn = player_history.get((bp_name, bc_name), (0, 0))
                    b_mast += (pw + 3.0 * 0.50) / (pn + 3.0) - 0.50
                    if (bp_name, bc_name) not in player_history: player_history[(bp_name, bc_name)] = [0, 0]
                    player_history[(bp_name, bc_name)][0] += b_win
                    player_history[(bp_name, bc_name)][1] += 1
                    
                rp_name = row.get(f'red_player_{r}', '')
                rc_name = row.get(f'red_{r}', '')
                if rp_name and rc_name:
                    pw, pn = player_history.get((rp_name, rc_name), (0, 0))
                    r_mast += (pw + 3.0 * 0.50) / (pn + 3.0) - 0.50
                    if (rp_name, rc_name) not in player_history: player_history[(rp_name, rc_name)] = [0, 0]
                    player_history[(rp_name, rc_name)][0] += (1 - b_win)
                    player_history[(rp_name, rc_name)][1] += 1
                    
            blue_mastery_scores.append(b_mast)
            red_mastery_scores.append(r_mast)

        df_advanced = pd.DataFrame()
        df_advanced['diff_meta_power'] = np.array(blue_meta_power) - np.array(red_meta_power)
        df_advanced['diff_player_mastery'] = np.array(blue_mastery_scores) - np.array(red_mastery_scores)
        
        for role in lane_roles:
            df_advanced[f'matchup_edge_{role}'] = lane_edges[role]
        df_advanced['total_lane_edge'] = df_advanced[[f'matchup_edge_{r}' for r in lane_roles]].sum(axis=1)
        
        for r1, r2 in duo_combos:
            combo_name = f"{r1}_{r2}"
            df_advanced[f'duo_synergy_{combo_name}'] = duo_edges[combo_name]
        df_advanced['total_duo_synergy'] = df_advanced[[f'duo_synergy_{c[0]}_{c[1]}' for c in duo_combos]].sum(axis=1)

        result_df = pd.concat([
            df_feat.reset_index(drop=True),
            df_b_comp.reset_index(drop=True),
            df_r_comp.reset_index(drop=True),
            diff_df.reset_index(drop=True),
            df_advanced.reset_index(drop=True)
        ], axis=1)

        feature_cols = [
            'blue_rating_pre', 'red_rating_pre', 'baseline_blue_prob',
            'diff_cc_score', 'diff_engage_score', 'diff_scaling_score', 'diff_ranged_count',
            'diff_frontline', 'diff_tank_count', 'diff_ad_share', 'diff_ap_share',
            'diff_ad_trap', 'diff_ap_trap', 'diff_meta_power', 'diff_player_mastery',
            'total_lane_edge', 'matchup_edge_top', 'matchup_edge_jng', 'matchup_edge_mid', 'matchup_edge_bot', 'matchup_edge_sup',
            'total_duo_synergy', 'duo_synergy_bot_sup', 'duo_synergy_mid_jng', 'duo_synergy_top_jng',
            'b_cc_score', 'b_engage_score', 'b_scaling_score', 'b_ad_share', 'b_ap_share', 'b_frontline_count',
            'r_cc_score', 'r_engage_score', 'r_scaling_score', 'r_ad_share', 'r_ap_share', 'r_frontline_count'
        ]
        
        feature_cols = [c for c in feature_cols if c in result_df.columns]
        logger.info(f"Engineered {len(feature_cols)} advanced features for {len(result_df)} competitive matches!")
        return result_df, feature_cols
