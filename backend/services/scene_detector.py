import os
from pathlib import Path
from typing import List
from dataclasses import dataclass

from scenedetect import detect, ContentDetector, split_video_ffmpeg
from scenedetect.scene_manager import save_images

from config import settings


@dataclass
class Scene:
    """Represents a detected scene/segment"""
    index: int
    start_time: float  # seconds
    end_time: float    # seconds
    duration: float    # seconds
    frame_path: str    # path to representative frame


class SceneDetector:
    """Detect and split video into scenes using PySceneDetect"""

    def __init__(self, threshold: float = 27.0):
        """
        Args:
            threshold: Detection sensitivity (lower = more scenes)
        """
        self.threshold = threshold
        self.temp_path = Path(settings.temp_path)

    def detect_scenes(self, video_path: str, session_id: str) -> List[Scene]:
        """
        Detect scene changes in video.

        Args:
            video_path: Path to video file
            session_id: Session ID for output organization

        Returns:
            List of Scene objects with timestamps and frame paths
        """
        output_dir = self.temp_path / session_id / "scenes"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Detect scenes
        scene_list = detect(video_path, ContentDetector(threshold=self.threshold))

        # If no scenes detected, treat whole video as one scene
        if not scene_list:
            from scenedetect import open_video
            video = open_video(video_path)
            duration = video.duration.get_seconds()
            del video  # VideoStreamCv2 doesn't have release(), just delete it

            # Extract single frame from middle
            frame_path = str(output_dir / "scene_001.jpg")
            self._extract_frame(video_path, duration / 2, frame_path)

            return [Scene(
                index=0,
                start_time=0.0,
                end_time=duration,
                duration=duration,
                frame_path=frame_path
            )]

        # Extract representative frames for each scene
        scenes = []
        for i, (start, end) in enumerate(scene_list):
            start_sec = start.get_seconds()
            end_sec = end.get_seconds()
            mid_time = (start_sec + end_sec) / 2

            frame_path = str(output_dir / f"scene_{i+1:03d}.jpg")
            self._extract_frame(video_path, mid_time, frame_path)

            scenes.append(Scene(
                index=i,
                start_time=start_sec,
                end_time=end_sec,
                duration=end_sec - start_sec,
                frame_path=frame_path
            ))

        return scenes

    def split_video(self, video_path: str, session_id: str) -> List[str]:
        """
        Split video into separate segment files.

        Returns:
            List of paths to segment video files
        """
        output_dir = self.temp_path / session_id / "segments"
        output_dir.mkdir(parents=True, exist_ok=True)

        scene_list = detect(video_path, ContentDetector(threshold=self.threshold))

        if not scene_list:
            # No scenes detected, return original video
            return [video_path]

        # Split video at scene boundaries
        split_video_ffmpeg(
            video_path,
            scene_list,
            output_dir=str(output_dir),
            output_file_template="$SCENE_NUMBER.mp4"
        )

        # Collect output paths
        segment_paths = sorted(output_dir.glob("*.mp4"))
        return [str(p) for p in segment_paths]

    def _extract_frame(self, video_path: str, timestamp: float, output_path: str):
        """Extract a single frame from video at given timestamp"""
        import cv2
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        success, frame = cap.read()
        if success:
            cv2.imwrite(output_path, frame)
        cap.release()


# Singleton instance
scene_detector = SceneDetector()
