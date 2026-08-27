"""
Esports Prediction Market and Bookmaker Odds Simulator.
Models market spread, bookmaker vig / overround, and pre-draft vs post-draft lines.
"""
import numpy as np

class MarketOddsSimulator:
    """
    Generates realistic market odds from baseline team ratings and market dynamics.
    """
    def __init__(self, vig: float = 0.04):
        self.vig = vig  # e.g. 4% bookmaker commission / spread

    def prob_to_decimal_odds(self, prob: float) -> float:
        """Convert true probability to bookmaker decimal odds with applied vig."""
        # Implied prob with half vig added
        implied = prob + (self.vig / 2.0)
        implied = np.clip(implied, 0.02, 0.98)
        return float(1.0 / implied)

    def generate_market_lines(self, baseline_prob: float) -> dict:
        """
        Generate closing pre-draft/post-draft decimal odds for Blue and Red.
        """
        p_blue = np.clip(baseline_prob, 0.05, 0.95)
        p_red = 1.0 - p_blue
        
        # Add vig to both sides
        implied_blue = p_blue + (self.vig / 2.0)
        implied_red = p_red + (self.vig / 2.0)
        
        odds_blue = 1.0 / implied_blue
        odds_red = 1.0 / implied_red
        
        return {
            "market_prob_blue": p_blue,
            "market_prob_red": p_red,
            "odds_blue": round(odds_blue, 3),
            "odds_red": round(odds_red, 3)
        }
