import os
import sys
import json
import yaml
import numpy as np

workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from src.screen_capture import capture_screen
from live_draft_cli import LiveTwitchDraftAssistant

def evaluate_parsed_draft(
    blue_team: str,
    red_team: str,
    blue_picks: dict,
    red_picks: dict,
    market_price_blue: float = None,
    market_price_red: float = None,
    is_polymarket_cents: bool = False
):
    """
    Evaluates a visually parsed draft against prediction market prices.
    """
    assistant = LiveTwitchDraftAssistant()
    assistant.evaluate_live(
        blue_team=blue_team,
        red_team=red_team,
        blue_picks=blue_picks,
        red_picks=red_picks,
        market_price_blue=market_price_blue,
        market_price_red=market_price_red,
        is_polymarket_cents=is_polymarket_cents
    )

if __name__ == "__main__":
    # Test evaluation
    print("Vision Draft Evaluation Module Loaded.")
