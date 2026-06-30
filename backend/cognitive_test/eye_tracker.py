"""MediaPipe FaceMesh iris landmark eye tracker.

Tracks gaze using iris landmark indices defined in Section 8.1 of PROJECT_KNOWLEDGE.md.
Used by the cognitive test session to measure gaze stability and saccade count.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# MediaPipe FaceMesh iris landmark indices (Section 8.1)
LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]

# Eye corner landmarks used for normalization
LEFT_EYE_CORNERS = [33, 133]
RIGHT_EYE_CORNERS = [362, 263]

SACCADE_THRESHOLD_PX = 30  # gaze movement (px) qualifying as a saccade


@dataclass
class GazePoint:
    x: float  # normalized 0–1 relative to frame width
    y: float  # normalized 0–1 relative to frame height
    timestamp: float = field(default_factory=time.time)


class EyeTracker:
    """Real-time iris landmark eye tracker using MediaPipe FaceMesh.

    Usage:
        tracker = EyeTracker()
        tracker.start()
        while running:
            gaze = tracker.get_gaze()  # returns GazePoint or None
        tracker.stop()
    """

    def __init__(self, camera_index: int = 0, target_fps: int = 30):
        self.camera_index = camera_index
        self.target_fps = target_fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._face_mesh = None
        self._running = False
        self._gaze_history: list[GazePoint] = []
        self._saccade_count = 0
        self._prev_gaze: Optional[GazePoint] = None

    def start(self) -> None:
        try:
            import mediapipe as mp
            self._face_mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,  # required for iris landmarks 468+
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except ImportError:
            logger.warning("MediaPipe not installed — eye tracking will be simulated")
            self._face_mesh = None

        self._cap = cv2.VideoCapture(self.camera_index)
        self._cap.set(cv2.CAP_PROP_FPS, self.target_fps)
        self._running = True
        self._gaze_history.clear()
        self._saccade_count = 0
        self._prev_gaze = None
        logger.info("EyeTracker started")

    def stop(self) -> None:
        self._running = False
        if self._cap:
            self._cap.release()
        if self._face_mesh:
            self._face_mesh.close()
        logger.info("EyeTracker stopped")

    def get_gaze(self) -> Optional[GazePoint]:
        """Read one frame and extract the gaze point. Returns None if unavailable."""
        if not self._running or self._cap is None:
            return None

        ret, frame = self._cap.read()
        if not ret:
            return None

        gaze = self._process_frame(frame)
        if gaze is not None:
            self._track_saccade(gaze)
            self._gaze_history.append(gaze)
        return gaze

    def get_current_frame(self) -> Optional[np.ndarray]:
        """Return the latest BGR frame (for streaming to frontend)."""
        if self._cap is None:
            return None
        ret, frame = self._cap.read()
        return frame if ret else None

    def _process_frame(self, frame: np.ndarray) -> Optional[GazePoint]:
        if self._face_mesh is None:
            return self._simulate_gaze()

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        results = self._face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            return None

        landmarks = results.multi_face_landmarks[0].landmark

        # Average iris center from left + right iris landmarks
        try:
            left_cx = np.mean([landmarks[i].x for i in LEFT_IRIS])
            left_cy = np.mean([landmarks[i].y for i in LEFT_IRIS])
            right_cx = np.mean([landmarks[i].x for i in RIGHT_IRIS])
            right_cy = np.mean([landmarks[i].y for i in RIGHT_IRIS])
            cx = (left_cx + right_cx) / 2.0
            cy = (left_cy + right_cy) / 2.0
            return GazePoint(x=float(cx), y=float(cy))
        except (IndexError, AttributeError):
            return None

    def _simulate_gaze(self) -> GazePoint:
        """Return a synthetic stable gaze point for dev/testing without a webcam."""
        import random
        return GazePoint(
            x=0.5 + random.gauss(0, 0.02),
            y=0.5 + random.gauss(0, 0.02),
        )

    def _track_saccade(self, gaze: GazePoint) -> None:
        if self._prev_gaze is None:
            self._prev_gaze = gaze
            return
        dx = (gaze.x - self._prev_gaze.x) * 640  # approximate pixel distance
        dy = (gaze.y - self._prev_gaze.y) * 480
        dist = (dx**2 + dy**2) ** 0.5
        if dist > SACCADE_THRESHOLD_PX:
            self._saccade_count += 1
        self._prev_gaze = gaze

    def compute_gaze_stability(self, stimulus_roi: tuple[float, float, float, float]) -> float:
        """Compute fraction of recorded gaze points that fall within the stimulus ROI.

        Args:
            stimulus_roi: (x_min, y_min, x_max, y_max) in normalized [0,1] coords.

        Returns:
            Stability score in [0, 1].
        """
        if not self._gaze_history:
            return 0.0
        x0, y0, x1, y1 = stimulus_roi
        on_target = sum(
            1 for g in self._gaze_history
            if x0 <= g.x <= x1 and y0 <= g.y <= y1
        )
        return on_target / len(self._gaze_history)

    @property
    def saccade_count(self) -> int:
        return self._saccade_count

    def reset_history(self) -> None:
        """Clear gaze history between stimuli."""
        self._gaze_history.clear()
