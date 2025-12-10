import base64
import io
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from config import settings
from services.pipeline_logger import PipelineLogger


class ImageProcessor:
    """Handle product image uploads and processing"""

    # Supported formats
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    MAX_SIZE_MB = 10
    TARGET_SIZE = (1024, 1024)  # Max dimensions for API uploads

    def __init__(self):
        self.storage_path = Path(settings.storage_path)
        self.logger = PipelineLogger()

    def save_product_image(
        self,
        image_data: bytes,
        session_id: str,
        filename: str = "product.jpg"
    ) -> str:
        """
        Save uploaded product image.

        Args:
            image_data: Raw image bytes
            session_id: Session ID for organization
            filename: Original filename

        Returns:
            Path to saved image
        """
        self.logger.set_session(session_id)
        self.logger.info("IMAGE_SAVE", f"Saving product image: {filename}", {
            "filename": filename,
            "data_size_bytes": len(image_data),
            "data_size_mb": round(len(image_data) / (1024 * 1024), 2),
        })

        # Validate extension
        ext = Path(filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            self.logger.error("IMAGE_SAVE", f"Unsupported format: {ext}", data={"extension": ext})
            raise ValueError(f"Unsupported image format: {ext}")

        # Validate size
        size_mb = len(image_data) / (1024 * 1024)
        if size_mb > self.MAX_SIZE_MB:
            self.logger.error("IMAGE_SAVE", f"Image too large: {size_mb:.1f}MB", data={"size_mb": size_mb})
            raise ValueError(f"Image too large: {size_mb:.1f}MB (max {self.MAX_SIZE_MB}MB)")

        # Create output directory
        output_dir = self.storage_path / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Process and optimize image
        image = Image.open(io.BytesIO(image_data))
        original_size = image.size

        self.logger.info("IMAGE_SAVE", f"Original image: {original_size[0]}x{original_size[1]}, mode={image.mode}", {
            "original_width": original_size[0],
            "original_height": original_size[1],
            "mode": image.mode,
        })

        # Convert to RGB if necessary (for JPEG compatibility)
        if image.mode in ("RGBA", "P"):
            self.logger.info("IMAGE_SAVE", f"Converting from {image.mode} to RGB")
            image = image.convert("RGB")

        # Resize if too large
        if image.width > self.TARGET_SIZE[0] or image.height > self.TARGET_SIZE[1]:
            self.logger.info("IMAGE_SAVE", f"Resizing from {image.size} to max {self.TARGET_SIZE}")
            image.thumbnail(self.TARGET_SIZE, Image.Resampling.LANCZOS)

        # Save as optimized JPEG
        output_path = output_dir / "product.jpg"
        image.save(output_path, "JPEG", quality=90, optimize=True)

        final_size = output_path.stat().st_size
        self.logger.success("IMAGE_SAVE", f"Product image saved: {output_path}", {
            "output_path": str(output_path),
            "final_size_bytes": final_size,
            "final_dimensions": f"{image.width}x{image.height}",
        })

        return str(output_path)

    def get_base64(self, image_path: str) -> str:
        """Get base64 encoded image for API requests"""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def get_data_uri(self, image_path: str) -> str:
        """Get data URI for image (for HTML/API embedding)"""
        b64 = self.get_base64(image_path)
        return f"data:image/jpeg;base64,{b64}"

    def get_dimensions(self, image_path: str) -> Tuple[int, int]:
        """Get image dimensions (width, height)"""
        with Image.open(image_path) as img:
            return img.size

    def extract_last_frame(self, video_path: str, output_path: Optional[str] = None, session_id: Optional[str] = None) -> str:
        """
        Extract the last frame from a video using ffmpeg.

        Args:
            video_path: Path to the video file
            output_path: Optional output path. If None, saves next to video.
            session_id: Optional session ID for logging

        Returns:
            Path to the extracted frame image
        """
        if session_id:
            self.logger.set_session(session_id)

        self.logger.info("FRAME_EXTRACT", f"Starting frame extraction from: {video_path}", {
            "video_path": video_path,
            "video_exists": Path(video_path).exists(),
            "output_path_provided": output_path is not None,
        })

        video_path = Path(video_path)
        if not video_path.exists():
            self.logger.error("FRAME_EXTRACT", f"Video file not found: {video_path}")
            raise FileNotFoundError(f"Video not found: {video_path}")

        video_size = video_path.stat().st_size
        self.logger.info("FRAME_EXTRACT", f"Video file found: {video_size} bytes", {
            "video_size_bytes": video_size,
            "video_size_mb": round(video_size / (1024 * 1024), 2),
        })

        # Default output path: same directory, same name with _lastframe.png
        # Using PNG instead of JPEG to avoid MJPEG encoder issues
        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}_lastframe.png"
        else:
            output_path = Path(output_path)

        self.logger.info("FRAME_EXTRACT", f"Output path: {output_path}", {
            "output_path": str(output_path),
            "output_format": output_path.suffix,
        })

        # Use ffmpeg to extract the last frame as PNG (more reliable than JPEG)
        # -sseof -1 seeks to 1 second before end (more reliable than -0.1)
        cmd = [
            "ffmpeg", "-y",
            "-sseof", "-1",
            "-i", str(video_path),
            "-update", "1",
            "-frames:v", "1",
            str(output_path)
        ]

        self.logger.info("FRAME_EXTRACT", f"Running ffmpeg command", {
            "command": " ".join(cmd),
            "sseof_value": "-1",
            "output_format": "PNG",
        })

        result = subprocess.run(cmd, capture_output=True, text=True)

        self.logger.info("FRAME_EXTRACT", f"ffmpeg returned: {result.returncode}", {
            "returncode": result.returncode,
            "stdout_length": len(result.stdout) if result.stdout else 0,
            "stderr_length": len(result.stderr) if result.stderr else 0,
        })

        if result.returncode != 0:
            self.logger.error("FRAME_EXTRACT", f"ffmpeg FAILED with code {result.returncode}", data={
                "returncode": result.returncode,
                "stderr": result.stderr[:2000] if result.stderr else None,
                "stdout": result.stdout[:500] if result.stdout else None,
            })
            raise RuntimeError(f"Failed to extract frame: {result.stderr}")

        if not output_path.exists():
            self.logger.error("FRAME_EXTRACT", f"ffmpeg succeeded but output file missing!", data={
                "expected_output": str(output_path),
                "output_exists": False,
            })
            raise RuntimeError(f"ffmpeg succeeded but output file not created: {output_path}")

        frame_size = output_path.stat().st_size
        self.logger.success("FRAME_EXTRACT", f"Frame extracted successfully: {output_path}", {
            "output_path": str(output_path),
            "frame_size_bytes": frame_size,
            "frame_size_kb": round(frame_size / 1024, 1),
        })

        # Verify the image is valid
        try:
            with Image.open(output_path) as img:
                self.logger.success("FRAME_EXTRACT", f"Frame validated: {img.size[0]}x{img.size[1]} {img.mode}", {
                    "width": img.size[0],
                    "height": img.size[1],
                    "mode": img.mode,
                    "format": img.format,
                })
        except Exception as e:
            self.logger.error("FRAME_EXTRACT", f"Frame validation failed!", error=e)
            raise RuntimeError(f"Extracted frame is invalid: {e}")

        return str(output_path)


# Singleton instance
image_processor = ImageProcessor()
