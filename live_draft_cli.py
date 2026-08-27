import os
import sys
import json
import yaml
import difflib
import numpy as np

workspace_root = os.path.dirname(os.path.abspath(__file__))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from src.ratings import DynamicRatingEngine
from src.features import AdvancedDraftFeatureExtractor
from src.backtest.market_simulator import MarketOddsSimulator

class LiveTwitchDraftAssistant:
    def __init__(self, config_path: str = "config/default_config.yaml"):
        if not os.path.isabs(config_path):
            config_path = os.path.join(workspace_root, config_path)
            
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
            
        champ_meta_path = os.path.join(workspace_root, "config/champion_metadata.json")
        with open(champ_meta_path, "r", encoding="utf-8") as f:
            self.champ_meta = json.load(f)
            
        self.all_champs = list(self.champ_meta.keys())
        self.extractor = AdvancedDraftFeatureExtractor(champ_meta_path)
        self.market_sim = MarketOddsSimulator(vig=self.config['backtest']['market_vig'])
        
        self.team_ratings = {
            "GEN": 1720, "Gen.G": 1720, "T1": 1680, "HLE": 1670, "Hanwha Life": 1670, "DK": 1580, "Dplus KIA": 1580, "KT": 1550, "KT Rolster": 1550, "FOX": 1490, "KDF": 1460, "NS": 1440, "DRX": 1430, "BRO": 1400,
            "BLG": 1730, "Bilibili Gaming": 1730, "TES": 1690, "Top Esports": 1690, "JDG": 1640, "LNG": 1620, "WBG": 1610, "Weibo Gaming": 1610, "FPX": 1530, "NIP": 1520, "AL": 1520, "IG": 1480, "EDG": 1460, "RNG": 1450, "OMG": 1430, "TT": 1410, "LGD": 1400, "WE": 1440, "UP": 1390, "RA": 1400,
            "G2": 1620, "G2 Esports": 1620, "FNC": 1550, "Fnatic": 1550, "BDS": 1520, "MDK": 1490, "MAD Lions": 1490, "SK": 1480, "HER": 1470, "Heretics": 1470, "VIT": 1460, "Vitality": 1460, "KC": 1450, "Karmine Corp": 1450, "GX": 1430, "RGE": 1410,
            "FLY": 1560, "FlyQuest": 1560, "TL": 1550, "Team Liquid": 1550, "C9": 1520, "Cloud9": 1520, "100": 1480, "100 Thieves": 1480, "DIG": 1440, "Dignitas": 1440, "SR": 1430, "Shopify": 1430, "IMT": 1400
        }

    def match_champion(self, raw_name: str) -> str:
        raw_name = raw_name.strip()
        if not raw_name:
            return "Aatrox"
        matches = difflib.get_close_matches(raw_name, self.all_champs, n=1, cutoff=0.4)
        if matches:
            return matches[0]
        for ch in self.all_champs:
            if ch.lower() == raw_name.lower():
                return ch
        return raw_name

    def evaluate_live(self, blue_team: str, red_team: str, blue_picks: dict, red_picks: dict, market_price_blue: float = None, market_price_red: float = None, is_polymarket_cents: bool = False):
        r_b = self.team_ratings.get(blue_team, 1500.0) + self.config['ratings']['side_bias_elo']
        r_r = self.team_ratings.get(red_team, 1500.0)
        p_base = float(np.clip(1.0 / (1.0 + 10.0 ** (-(r_b - r_r) / 400.0)), 0.02, 0.98))
        
        b_p_list = [self.match_champion(blue_picks[r]) for r in ['top', 'jng', 'mid', 'bot', 'sup']]
        r_p_list = [self.match_champion(red_picks[r]) for r in ['top', 'jng', 'mid', 'bot', 'sup']]
        
        b_comp = self.extractor.extract_composition_vector(b_p_list)
        r_comp = self.extractor.extract_composition_vector(r_p_list)
        
        diff_cc = b_comp['cc_score'] - r_comp['cc_score']
        diff_eng = b_comp['engage_score'] - r_comp['engage_score']
        diff_sc = b_comp['scaling_score'] - r_comp['scaling_score']
        diff_front = b_comp['frontline_count'] - r_comp['frontline_count']
        
        draft_delta = (diff_cc * 0.010) + (diff_eng * 0.008) + (diff_sc * 0.022) + (diff_front * 0.015)
        if b_comp['ad_share'] > 0.85 and r_comp['tank_count'] >= 2:
            draft_delta -= 0.08
        if r_comp['ad_share'] > 0.85 and b_comp['tank_count'] >= 2:
            draft_delta += 0.08
            
        p_final = float(np.clip(p_base + draft_delta, 0.02, 0.98))
        
        if is_polymarket_cents:
            market_odds_blue = 100.0 / market_price_blue if market_price_blue else (1.0 / (p_base + 0.02))
            market_odds_red = 100.0 / market_price_red if market_price_red else (1.0 / ((1.0 - p_base) + 0.02))
        else:
            market_odds_blue = market_price_blue if market_price_blue else round(1.0 / (p_base + 0.02), 3)
            market_odds_red = market_price_red if market_price_red else round(1.0 / ((1.0 - p_base) + 0.02), 3)
            
        ev_blue = (p_final * market_odds_blue) - 1.0
        ev_red = ((1.0 - p_final) * market_odds_red) - 1.0
        
        sep = "=" * 65
        dash = "-" * 65
        print("")
        print(sep)
        print(f"  [LIVE DRAFT EVALUATION] {blue_team} (Blue) vs {red_team} (Red)")
        print(sep)
        print(f"  Blue Picks: {b_p_list}")
        print(f"  Red Picks:  {r_p_list}")
        print(dash)
        print(f"  [*] Pre-Draft Baseline Win:  Blue: {p_base*100:.1f}%  |  Red: {(1-p_base)*100:.1f}%")
        print(f"  [*] Draft Advantage Delta:   {draft_delta*100:+.2f}% ({'Blue Advantage' if draft_delta > 0 else 'Red Advantage'})")
        print(f"  [*] Calibrated Fair Win:     Blue: {p_final*100:.1f}%  |  Red: {(1-p_final)*100:.1f}%")
        print(f"  [*] Listed Market Odds:      Blue: {market_odds_blue:.2f} (Implied {(1/market_odds_blue)*100:.1f}%) | Red: {market_odds_red:.2f} (Implied {(1/market_odds_red)*100:.1f}%)")
        print(f"  [*] Expected Value (EV):     Blue: {ev_blue*100:+.2f}%  |  Red: {ev_red*100:+.2f}%")
        print(dash)
        
        ev_thresh = self.config['backtest']['ev_threshold']
        if ev_blue >= ev_thresh and ev_blue >= ev_red:
            b = market_odds_blue - 1.0
            kelly_pct = min((p_final * (b + 1) - 1) / b * 0.25, 0.05) * 100.0
            print(f"  >>> ACTION: [RECOMMENDED BET ON BLUE ({blue_team})] <<<")
            print(f"      Positive Edge: +{ev_blue*100:.2f}% | Sizing: {kelly_pct:.1f}% of Bankroll")
        elif ev_red >= ev_thresh:
            b = market_odds_red - 1.0
            kelly_pct = min(((1.0 - p_final) * (b + 1) - 1) / b * 0.25, 0.05) * 100.0
            print(f"  >>> ACTION: [RECOMMENDED BET ON RED ({red_team})] <<<")
            print(f"      Positive Edge: +{ev_red*100:.2f}% | Sizing: {kelly_pct:.1f}% of Bankroll")
        else:
            print("  [=] ACTION: PASS / NO VALUE (Market price matches true draft probability)")
        print(sep)
        print("")

    def run_interactive(self):
        print("\n" + "="*60)
        print("   LOL LIVE TWITCH STREAM DRAFT EVALUATOR & EV ENGINE   ")
        print("="*60)
        print("Enter team abbreviations & champion picks as you watch the stream.")
        print("Type 'exit' anytime to quit.\n")
        
        while True:
            b_team = input("Enter Blue Team (e.g. T1, GEN, BLG, G2, FLY): ").strip()
            if b_team.lower() == 'exit': break
            r_team = input("Enter Red Team (e.g. WBG, TES, FNC, TL): ").strip()
            if r_team.lower() == 'exit': break
            
            print("\n-- Blue Side Picks --")
            b_top = input("  Blue Top: ")
            b_jng = input("  Blue Jungle: ")
            b_mid = input("  Blue Mid: ")
            b_bot = input("  Blue ADC / Bot: ")
            b_sup = input("  Blue Support: ")
            
            print("\n-- Red Side Picks --")
            r_top = input("  Red Top: ")
            r_jng = input("  Red Jungle: ")
            r_mid = input("  Red Mid: ")
            r_bot = input("  Red ADC / Bot: ")
            r_sup = input("  Red Support: ")
            
            price_input = input("\nEnter Market Odds or Polymarket Cents (e.g., '1.95 1.95' or '55c 45c' or press Enter): ").strip()
            price_b, price_r = None, None
            is_poly = False
            if price_input:
                parts = price_input.replace('c', '').split()
                if len(parts) >= 2:
                    try:
                        price_b = float(parts[0])
                        price_r = float(parts[1])
                        if 'c' in price_input: is_poly = True
                    except Exception: pass
                    
            self.evaluate_live(
                blue_team=b_team,
                red_team=r_team,
                blue_picks={'top': b_top, 'jng': b_jng, 'mid': b_mid, 'bot': b_bot, 'sup': b_sup},
                red_picks={'top': r_top, 'jng': r_jng, 'mid': r_mid, 'bot': r_bot, 'sup': r_sup},
                market_price_blue=price_b,
                market_price_red=price_r,
                is_polymarket_cents=is_poly
            )

if __name__ == "__main__":
    assistant = LiveTwitchDraftAssistant()
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        assistant.run_interactive()
    else:
        assistant.evaluate_live(
            blue_team="T1",
            red_team="GEN",
            blue_picks={"top": "Rumble", "jng": "Jarvan IV", "mid": "Orianna", "bot": "Kalista", "sup": "Renata Glasc"},
            red_picks={"top": "K'Sante", "jng": "Maokai", "mid": "Azir", "bot": "Zeri", "sup": "Lulu"},
            market_price_blue=2.10,
            market_price_red=1.75
        )
