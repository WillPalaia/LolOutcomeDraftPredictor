"""
Unit and Integration Tests for Computer Vision Draft Ingestion Pipeline.
"""
import os
import sys
import unittest
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

# Add project root to sys.path
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

from src.vision.champion_matcher import ChampionMatcher
from src.vision.draft_layout_detector import DraftLayoutDetector
from src.vision.vision_pipeline import VisionDraftPipeline
from src.bot.bot_engine import DraftBotEngine

def create_synthetic_broadcast_draft_image(
    output_path: str,
    blue_team: str = "T1",
    red_team: str = "GEN",
    blue_picks: list = None,
    red_picks: list = None
) -> str:
    """
    Renders a realistic 1920x1080 synthetic esports draft overlay for testing.
    """
    blue_picks = blue_picks or ["Rumble", "Jarvan IV", "Orianna", "Kalista", "Renata Glasc"]
    red_picks = red_picks or ["K'Sante", "Maokai", "Azir", "Zeri", "Lulu"]

    img = Image.new("RGB", (1920, 1080), color=(15, 20, 30))
    draw = ImageDraw.Draw(img)

    # Blue header (Left)
    draw.rectangle([50, 40, 400, 120], fill=(20, 40, 80), outline=(0, 150, 255), width=3)
    draw.text((80, 60), f"BLUE SIDE: {blue_team}", fill=(255, 255, 255))

    # Red header (Right)
    draw.rectangle([1520, 40, 1870, 120], fill=(80, 30, 30), outline=(255, 80, 80), width=3)
    draw.text((1550, 60), f"RED SIDE: {red_team}", fill=(255, 255, 255))

    # Blue pick slots (Left side stacked vertically)
    y_start = 180
    y_spacing = 160
    for i, champ in enumerate(blue_picks):
        y = y_start + i * y_spacing
        draw.rectangle([50, y, 400, y + 130], fill=(15, 30, 50), outline=(0, 200, 255), width=2)
        draw.text((80, y + 50), champ.upper(), fill=(255, 255, 255))

    # Red pick slots (Right side stacked vertically)
    for i, champ in enumerate(red_picks):
        y = y_start + i * y_spacing
        draw.rectangle([1520, y, 1870, y + 130], fill=(50, 20, 20), outline=(255, 100, 100), width=2)
        draw.text((1550, y + 50), champ.upper(), fill=(255, 255, 255))

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path)
    return output_path

class TestVisionDraftPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.join(workspace_root, "data", "test_frames")
        os.makedirs(cls.test_dir, exist_ok=True)
        cls.sample_img_path = os.path.join(cls.test_dir, "test_draft_t1_geng.png")
        create_synthetic_broadcast_draft_image(
            cls.sample_img_path,
            blue_team="T1",
            red_team="GEN",
            blue_picks=["Rumble", "Jarvan IV", "Orianna", "Kalista", "Renata Glasc"],
            red_picks=["K'Sante", "Maokai", "Azir", "Zeri", "Lulu"]
        )

    def test_champion_matcher_exact_and_fuzzy(self):
        matcher = ChampionMatcher()
        
        # Exact
        champ, score = matcher.match_champion("RUMBLE")
        self.assertEqual(champ, "Rumble")
        self.assertGreaterEqual(score, 0.9)

        # Aliases & common shorthands
        champ, score = matcher.match_champion("J4")
        self.assertEqual(champ, "Jarvan IV")
        
        champ, score = matcher.match_champion("KSANTE")
        self.assertEqual(champ, "K'Sante")

        champ, score = matcher.match_champion("RENATA")
        self.assertEqual(champ, "Renata Glasc")

        # Teams
        self.assertEqual(matcher.match_team("T1"), "T1")
        self.assertEqual(matcher.match_team("GEN"), "Gen.G")
        self.assertEqual(matcher.match_team("BLG"), "Bilibili Gaming")

    def test_draft_layout_detection(self):
        detector = DraftLayoutDetector()
        img = cv2.imread(self.sample_img_path)
        self.assertIsNotNone(img, "Failed to load test draft image.")

        result = detector.detect_draft(img)
        self.assertIsNotNone(result, "Detector failed to detect draft from synthetic image.")
        self.assertTrue(result["is_complete"])
        self.assertEqual(result["blue_team"], "T1")
        self.assertEqual(result["red_team"], "Gen.G")

        # Verify all 5 blue and 5 red picks detected
        b_picks = result["blue_picks"]
        r_picks = result["red_picks"]
        self.assertEqual(b_picks["top"], "Rumble")
        self.assertEqual(b_picks["jng"], "Jarvan IV")
        self.assertEqual(b_picks["mid"], "Orianna")
        self.assertEqual(b_picks["bot"], "Kalista")
        self.assertEqual(b_picks["sup"], "Renata Glasc")

        self.assertEqual(r_picks["top"], "K'Sante")
        self.assertEqual(r_picks["jng"], "Maokai")
        self.assertEqual(r_picks["mid"], "Azir")
        self.assertEqual(r_picks["bot"], "Zeri")
        self.assertEqual(r_picks["sup"], "Lulu")

    def test_end_to_end_vision_evaluation_in_engine(self):
        engine = DraftBotEngine()
        match_data = engine.evaluate_vision_image(self.sample_img_path, league="LCK")
        self.assertIsNotNone(match_data)
        self.assertEqual(match_data["blue_team"], "T1")
        self.assertEqual(match_data["red_team"], "Gen.G")
        self.assertEqual(match_data["state"], "draft_complete")

if __name__ == "__main__":
    unittest.main()
