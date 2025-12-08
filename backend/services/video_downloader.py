import os
import yt_dlp
from pathlib import Path
from typing import Optional

from config import settings


class VideoDownloader:
    """TikTok video downloader using yt-dlp"""

    def __init__(self):
        self.temp_path = Path(settings.temp_path)
        self.temp_path.mkdir(parents=True, exist_ok=True)

    def download(self, url: str, session_id: str) -> dict:
        """
        Download TikTok video.

        Args:
            url: TikTok video URL
            session_id: Unique session identifier

        Returns:
            dict with video_path, duration, width, height, title
        """
        output_dir = self.temp_path / session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(output_dir / "original.%(ext)s")

        ydl_opts = {
            "format": "best[ext=mp4]/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Find downloaded file
            video_path = None
            for ext in ["mp4", "webm", "mkv"]:
                potential_path = output_dir / f"original.{ext}"
                if potential_path.exists():
                    video_path = str(potential_path)
                    break

            if not video_path:
                raise FileNotFoundError("Video download failed - file not found")

            return {
                "video_path": video_path,
                "duration": info.get("duration", 0),
                "width": info.get("width", 0),
                "height": info.get("height", 0),
                "title": info.get("title", ""),
                "description": info.get("description", ""),
            }

    def cleanup(self, session_id: str):
        """Remove temporary files for a session"""
        import shutil
        session_dir = self.temp_path / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)


# Singleton instance
video_downloader = VideoDownloader()
