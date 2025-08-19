"""Image utility functions for ShotGrid nodes.
Handles image format conversion and optimization for thumbnail uploads.
"""

import io
import logging
import mimetypes
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def convert_image_for_shotgrid(
    image_bytes: bytes, filename: str, max_size: tuple[int, int] = (800, 600)
) -> tuple[bytes, str]:
    """Convert image to a format supported by ShotGrid and optimize for thumbnail upload.

    Args:
        image_bytes: Raw image bytes
        filename: Original filename (used to determine format)
        max_size: Maximum dimensions for the thumbnail (width, height)

    Returns:
        Tuple of (converted_image_bytes, new_filename)
    """
    try:
        # Open the image
        image = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary (for JPEG/PNG compatibility)
        if image.mode in ("RGBA", "LA", "P"):
            # Create a white background for transparent images
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            background.paste(image, mask=image.split()[-1] if image.mode == "RGBA" else None)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        # Resize if larger than max_size while maintaining aspect ratio
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            logger.info(f"Resized image from {image.size} to fit within {max_size}")

        # Determine output format and filename
        original_ext = Path(filename).suffix.lower()

        # Convert WebP to PNG, keep other formats as-is
        if original_ext == ".webp":
            output_format = "PNG"
            new_filename = str(Path(filename).with_suffix(".png"))
            logger.info(f"Converting WebP to PNG: {filename} -> {new_filename}")
        else:
            # For other formats, convert to JPEG for better compatibility
            output_format = "JPEG"
            new_filename = str(Path(filename).with_suffix(".jpg"))
            logger.info(f"Converting to JPEG: {filename} -> {new_filename}")

        # Save to bytes
        output_buffer = io.BytesIO()
        image.save(output_buffer, format=output_format, quality=85, optimize=True)
        converted_bytes = output_buffer.getvalue()

        logger.info(f"Successfully converted image: {len(image_bytes)} bytes -> {len(converted_bytes)} bytes")
        return converted_bytes, new_filename

    except Exception as e:
        logger.error(f"Failed to convert image {filename}: {e}")
        # Return original bytes and filename if conversion fails
        return image_bytes, filename


def get_mime_type(filename: str) -> str:
    """Get MIME type for a filename, with fallback for converted images.

    Args:
        filename: The filename to get MIME type for

    Returns:
        MIME type string
    """
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        # Fallback based on extension
        ext = Path(filename).suffix.lower()
        if ext == ".png":
            return "image/png"
        if ext == ".jpg" or ext == ".jpeg":
            return "image/jpeg"
        if ext == ".webp":
            return "image/webp"
        return "image/jpeg"  # Default fallback
    return mime_type


def should_convert_image(filename: str) -> bool:
    """Check if an image should be converted (e.g., WebP to PNG).

    Args:
        filename: The filename to check

    Returns:
        True if the image should be converted
    """
    ext = Path(filename).suffix.lower()
    # Convert WebP and other potentially unsupported formats
    return ext in [".webp", ".bmp", ".tiff", ".tga"]
