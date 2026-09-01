"""
Live Video Stream & Screen Frame Grabber for LoL Esports.
Supports YouTube Live, Twitch, Screen/Window Capture, and Local Video Feeds.
"""
import os
import time
import subprocess
import cv2
import numpy as np
import logging
from typing import Optional, Generator, Tuple

logger = logging.getLogger("StreamGrabber")

try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False

try:
    import streamlink
    STREAMLINK_AVAILABLE = True
except ImportError:
    STREAMLINK_AVAILABLE = False


class StreamGrabber:
    def __init__(self, source: str = "screen", monitor_index: int = 1):
        """
        source can be:
        - "screen" (Monitor capture)
        - A YouTube URL / channel (e.g. "https://www.youtube.com/@LCKglobal/live")
        - A Twitch URL / channel (e.g. "https://www.twitch.tv/lck" or "twitch:lck")
        - A direct video file or HLS/m3u8 URL (e.g. "sample_draft.mp4")
        """
        self.source = source
        self.monitor_index = monitor_index
        self.cap: Optional[cv2.VideoCapture] = None
        self.sct = None
        if MSS_AVAILABLE:
            self.sct = mss.mss()
        self.resolved_url: Optional[str] = None
        self.is_running = False

    def resolve_stream_url(self, source_url: str) -> Optional[str]:
        """
        Resolves YouTube or Twitch live broadcast into a direct m3u8/HLS stream URL.
        """
        if "youtube.com" in source_url or "youtu.be" in source_url:
            if not YTDLP_AVAILABLE:
                logger.error("yt-dlp not available to resolve YouTube stream.")
                return None
            try:
                ydl_opts = {
                    "format": "best[height<=1080]/best",
                    "quiet": True,
                    "no_warnings": True
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(source_url, download=False)
                    url = info.get("url")
                    logger.info(f"Resolved YouTube stream URL for {source_url}")
                    return url
            except Exception as e:
                logger.error(f"Failed to resolve YouTube live URL: {e}")
                return None

        elif "twitch.tv" in source_url or source_url.startswith("twitch:"):
            if not STREAMLINK_AVAILABLE:
                logger.error("streamlink not available to resolve Twitch stream.")
                return None
            try:
                clean_url = source_url if source_url.startswith("http") else f"https://www.twitch.tv/{source_url.split(':')[-1]}"
                streams = streamlink.streams(clean_url)
                if "best" in streams:
                    url = streams["best"].url
                    logger.info(f"Resolved Twitch stream URL for {clean_url}")
                    return url
                elif "720p" in streams:
                    return streams["720p"].url
                elif streams:
                    first_key = next(iter(streams))
                    return streams[first_key].url
            except Exception as e:
                logger.error(f"Failed to resolve Twitch stream: {e}")
                return None

        return source_url

    def open(self) -> bool:
        """
        Initializes video capture or screen grabber.
        """
        if self.source == "screen":
            if not MSS_AVAILABLE:
                logger.error("mss library not installed for screen capture.")
                return False
            logger.info(f"Initialized screen capture on monitor {self.monitor_index}.")
            self.is_running = True
            return True

        # Video stream or file
        direct_url = self.resolve_stream_url(self.source)
        if not direct_url:
            logger.error(f"Could not open stream source: {self.source}")
            return False

        self.resolved_url = direct_url
        self.cap = cv2.VideoCapture(direct_url)
        if not self.cap.isOpened():
            logger.error(f"Failed to open OpenCV VideoCapture for {self.source}")
            return False

        logger.info(f"Opened VideoCapture stream for {self.source}")
        self.is_running = True
        return True

    def read_frame(self) -> Optional[np.ndarray]:
        """
        Reads a single BGR frame from the active stream or screen.
        """
        if self.source == "screen":
            if not self.sct:
                return None
            try:
                monitors = self.sct.monitors
                m_idx = self.monitor_index if self.monitor_index < len(monitors) else 0
                sct_img = self.sct.grab(monitors[m_idx])
                # Convert to numpy array (BGRA -> BGR)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                return frame
            except Exception as e:
                logger.error(f"Screen grab failed: {e}")
                return None

        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return frame
            else:
                logger.warning("VideoCapture frame read returned false. Reconnecting...")
                self._reconnect()
                return None

        return None

    def _reconnect(self):
        if self.cap:
            self.cap.release()
        time.sleep(2)
        if self.resolved_url:
            self.cap = cv2.VideoCapture(self.resolved_url)

    def close(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        if self.sct:
            self.sct.close()
            self.sct = None
        logger.info("StreamGrabber closed.")
