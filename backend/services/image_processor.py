import base64
import io
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

from config import settings


class ImageProcessor:
    """Handle product image uploads and processing"""

    # Supported formats
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    MAX_SIZE_MB = 10
    TARGET_SIZE = (1024, 1024)  # Max dimensions for API uploads

    def __init__(self):
        self.storage_path = Path(settings.storage_path)

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
        # Validate extension
        ext = Path(filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported image format: {ext}")

        # Validate size
        size_mb = len(image_data) / (1024 * 1024)
        if size_mb > self.MAX_SIZE_MB:
            raise ValueError(f"Image too large: {size_mb:.1f}MB (max {self.MAX_SIZE_MB}MB)")

        # Create output directory
        output_dir = self.storage_path / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Process and optimize image
        image = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (for JPEG compatibility)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Resize if too large
        if image.width > self.TARGET_SIZE[0] or image.height > self.TARGET_SIZE[1]:
            image.thumbnail(self.TARGET_SIZE, Image.Resampling.LANCZOS)

        # Save as optimized JPEG
        output_path = output_dir / "product.jpg"
        image.save(output_path, "JPEG", quality=90, optimize=True)

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


# Singleton instance
image_processor = ImageProcessor()
