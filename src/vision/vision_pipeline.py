"""
Vision Draft Pipeline Orchestrator for LoL Esports.
Combines Stream Grabber, Layout Detector, and Champion Matcher to autonomously
detect finalized drafts and dispatch +EV betting signals.
"""
import os
import time
import cv2
import numpy as np
import logging
from typing import Dict, Any, Optional, Callable
from src.vision.champion_matcher import ChampionMatcher
from src.vision.draft_layout_detector import DraftLayoutDetector
from src.vision.stream_grabber import StreamGrabber

logger = logging.getLogger("VisionDraftPipeline")

class VisionDraftPipeline:
    def __init__(
        self,
        stream_source: str = "screen",
        monitor_index: int = 1,
        stability_count: int = 2,
        on_draft_locked: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.matcher = ChampionMatcher()
        self.detector = DraftLayoutDetector(matcher=self.matcher)
        self.grabber = StreamGrabber(source=stream_source, monitor_index=monitor_index)
        self.stability_count = max(1, stability_count)
        self.on_draft_locked = on_draft_locked
        
        self.last_candidate_picks: Optional[Dict[str, Any]] = None
        self.consecutive_stable_frames = 0
        self.dispatched_draft_signatures = set()
        self.is_monitoring = False

    def process_image(self, image_input: Any) -> Optional[Dict[str, Any]]:
        """
        Processes a single image (file path or numpy array) and extracts the draft.
        """
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                logger.error(f"Image file not found: {image_input}")
                return None
            frame = cv2.imread(image_input)
        elif isinstance(image_input, np.ndarray):
            frame = image_input
        else:
            logger.error("Invalid image input type.")
            return None

        detection = self.detector.detect_draft(frame)
        return detection

    def _generate_signature(self, draft: Dict[str, Any]) -> str:
        """
        Generates a unique hashable signature for a draft combination to avoid duplicate trades.
        """
        b_picks = [draft["blue_picks"].get(r, "") for r in ["top", "jng", "mid", "bot", "sup"]]
        r_picks = [draft["red_picks"].get(r, "") for r in ["top", "jng", "mid", "bot", "sup"]]
        return f"{draft['blue_team']}_{draft['red_team']}_{'_'.join(b_picks)}_{'_'.join(r_picks)}"

    def check_frame_and_dispatch(self, frame: np.ndarray, league: str = "PRO") -> Optional[Dict[str, Any]]:
        """
        Evaluates a live frame, enforces multi-frame stability, and triggers trade callback.
        """
        detection = self.detector.detect_draft(frame)
        if not detection or not detection.get("is_complete"):
            self.consecutive_stable_frames = 0
            self.last_candidate_picks = None
            return None

        # Check all 10 picks are non-null
        b_picks = detection["blue_picks"]
        r_picks = detection["red_picks"]
        if any(v is None for v in b_picks.values()) or any(v is None for v in r_picks.values()):
            return None

        sig = self._generate_signature(detection)
        if sig in self.dispatched_draft_signatures:
            return None

        # Stability verification
        if self.last_candidate_picks == sig:
            self.consecutive_stable_frames += 1
        else:
            self.last_candidate_picks = sig
            self.consecutive_stable_frames = 1

        logger.info(
            f"Detected complete draft: {detection['blue_team']} vs {detection['red_team']} "
            f"(Stability: {self.consecutive_stable_frames}/{self.stability_count})"
        )

        if self.consecutive_stable_frames >= self.stability_count:
            # Finalized locked draft!
            self.dispatched_draft_signatures.add(sig)
            
            timestamp = int(time.time())
            match_data = {
                "match_id": f"VISION_{detection['blue_team']}_vs_{detection['red_team']}_{timestamp}",
                "league": league,
                "state": "draft_complete",
                "blue_team": detection["blue_team"],
                "red_team": detection["red_team"],
                "blue_picks": b_picks,
                "red_picks": r_picks,
                "confidence": detection["confidence"]
            }

            logger.info(f"🎯 DRAFT CONFIRMED & LOCKED: {match_data['match_id']}")
            logger.info(f"   🔵 Blue ({match_data['blue_team']}): {list(b_picks.values())}")
            logger.info(f"   🔴 Red ({match_data['red_team']}): {list(r_picks.values())}")

            if self.on_draft_locked:
                self.on_draft_locked(match_data)

            return match_data

        return None

    def start_stream_monitoring(
        self,
        league: str = "PRO",
        poll_interval_seconds: float = 2.0,
        max_duration_seconds: Optional[int] = None
    ):
        """
        Continuously captures frames from the stream and monitors for live draft completion.
        """
        if not self.grabber.open():
            logger.error("Could not start stream monitoring grabber.")
            return

        self.is_monitoring = True
        logger.info(f"Started Vision Stream Monitor on '{self.grabber.source}' (Interval: {poll_interval_seconds}s)...")

        start_time = time.time()
        try:
            while self.is_monitoring:
                if max_duration_seconds and (time.time() - start_time) > max_duration_seconds:
                    logger.info("Max monitoring duration reached.")
                    break

                frame = self.grabber.read_frame()
                if frame is not None:
                    self.check_frame_and_dispatch(frame, league=league)

                time.sleep(poll_interval_seconds)
        except KeyboardInterrupt:
            logger.info("Vision Stream Monitor stopped by user.")
        finally:
            self.grabber.close()
            self.is_monitoring = False
