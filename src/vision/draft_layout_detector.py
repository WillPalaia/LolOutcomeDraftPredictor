"""
Draft Layout Detector for LoL Esports Broadcast Streams.
Identifies champ select overlays and maps bounding boxes to Blue/Red roles.
"""
import cv2
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from rapidocr_onnxruntime import RapidOCR
from src.vision.champion_matcher import ChampionMatcher

logger = logging.getLogger("DraftLayoutDetector")

ROLES_ORDER = ["top", "jng", "mid", "bot", "sup"]

class DraftLayoutDetector:
    def __init__(self, matcher: Optional[ChampionMatcher] = None):
        self.matcher = matcher or ChampionMatcher()
        self.ocr = RapidOCR()
        logger.info("DraftLayoutDetector initialized with RapidOCR engine.")

    def detect_draft(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Processes a video frame (BGR or RGB) and detects if it is a champion select screen.
        Extracts Blue picks, Red picks, Blue team, Red team if 10 champions are locked.
        """
        if frame is None or frame.size == 0:
            return None

        h, w = frame.shape[:2]
        if w < 300 or h < 200:
            return None

        # Run OCR over the frame
        try:
            results, _ = self.ocr(frame)
        except Exception as e:
            logger.error(f"OCR execution failed: {e}")
            return None

        if not results:
            return None

        # Separate text detections into Left (Blue side), Right (Red side), and Center/Top
        blue_candidates = []
        red_candidates = []
        team_candidates_blue = []
        team_candidates_red = []

        for item in results:
            box, text, score = item[0], item[1], float(item[2])
            if score < 0.40 or not text:
                continue

            # Calculate center coordinate of the bounding box
            xs = [pt[0] for pt in box]
            ys = [pt[1] for pt in box]
            cx = (min(xs) + max(xs)) / 2.0 / w  # normalized x [0..1]
            cy = (min(ys) + max(ys)) / 2.0 / h  # normalized y [0..1]

            # Header Region (cy < 0.18): Contains team codes/names, scores, draft titles
            if cy < 0.18:
                if cx < 0.48:
                    team_candidates_blue.append(text)
                elif cx > 0.52:
                    team_candidates_red.append(text)
                continue

            # Pick Slot Region (cy >= 0.18): Contains champion names and player handles
            champ, conf = self.matcher.match_champion(text)
            if champ and conf >= 0.60:
                if cx < 0.48:
                    blue_candidates.append({"champion": champ, "y": cy, "x": cx, "conf": conf, "raw": text})
                elif cx > 0.52:
                    red_candidates.append({"champion": champ, "y": cy, "x": cx, "conf": conf, "raw": text})

        # De-duplicate multiple detections of the same champion on each side
        blue_unique = self._deduplicate_picks(blue_candidates)
        red_unique = self._deduplicate_picks(red_candidates)

        # Check if we have detected valid draft picks
        # A full draft requires 5 blue and 5 red champions
        if len(blue_unique) >= 4 and len(red_unique) >= 4:
            # Sort top to bottom
            blue_sorted = sorted(blue_unique, key=lambda p: p["y"])
            red_sorted = sorted(red_unique, key=lambda p: p["y"])

            # Map to standard 5 roles
            b_picks = {}
            for i, role in enumerate(ROLES_ORDER):
                if i < len(blue_sorted):
                    b_picks[role] = blue_sorted[i]["champion"]
                else:
                    b_picks[role] = None

            r_picks = {}
            for i, role in enumerate(ROLES_ORDER):
                if i < len(red_sorted):
                    r_picks[role] = red_sorted[i]["champion"]
                else:
                    r_picks[role] = None

            # Resolve team names from headers
            b_team = "Blue Team"
            for t in team_candidates_blue:
                norm = self.matcher.match_team(t)
                if norm and norm not in ["Blue Team", "Blue", "Team"] and len(norm) >= 2:
                    b_team = norm
                    break

            r_team = "Red Team"
            for t in team_candidates_red:
                norm = self.matcher.match_team(t)
                if norm and norm not in ["Red Team", "Red", "Team"] and len(norm) >= 2:
                    r_team = norm
                    break

            return {
                "is_draft": True,
                "is_complete": (len(blue_unique) == 5 and len(red_unique) == 5),
                "blue_team": b_team,
                "red_team": r_team,
                "blue_picks": b_picks,
                "red_picks": r_picks,
                "blue_count": len(blue_unique),
                "red_count": len(red_unique),
                "confidence": (
                    sum(p["conf"] for p in blue_unique) + sum(p["conf"] for p in red_unique)
                ) / max(1, len(blue_unique) + len(red_unique))
            }

        return None

    def _deduplicate_picks(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Removes duplicates from overlapping OCR passes while preserving vertical ordering.
        """
        seen = set()
        unique = []
        # Sort by confidence descending
        sorted_cands = sorted(candidates, key=lambda c: c["conf"], reverse=True)
        for c in sorted_cands:
            champ = c["champion"]
            if champ not in seen:
                seen.add(champ)
                unique.append(c)
            if len(unique) >= 5:
                break
        return unique
