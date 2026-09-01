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
from src.vision.vision_pipeline import VisionDraftPipeline

def parse_image_draft(image_path: str) -> dict:
    """
    Parses a draft image and returns the structured 10-champion draft payload.
    """
    pipeline = VisionDraftPipeline()
    return pipeline.process_image(image_path)

def parse_screen_draft(monitor_index: int = 1) -> dict:
    """
    Captures primary screen and parses the draft in real-time.
    """
    screenshot_path = capture_screen(monitor_index=monitor_index)
    return parse_image_draft(screenshot_path)

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
    print("Testing Screen Vision Draft Parser...")
    res = parse_screen_draft()
    if res:
        print("Detected draft:", res)
    else:
        print("No active draft detected on screen.")
