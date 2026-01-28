"""
Image utility for saving cell output images to temp files.

Saves base64-encoded image data from Jupyter cell outputs to temporary
files and returns file paths for Claude's Read tool to view.
"""

import base64
import hashlib
import os
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Directory for saved images
IMAGE_DIR = "/tmp/instrmcp_images"

# MIME type to file extension mapping
MIME_TO_EXT: Dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpeg",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/tiff": ".tiff",
}

IMAGE_MIME_TYPES = set(MIME_TO_EXT.keys())


def _ensure_image_dir() -> None:
    """Create the image directory if it doesn't exist."""
    os.makedirs(IMAGE_DIR, exist_ok=True)


def _save_image(base64_data: str, mime_type: str) -> Optional[str]:
    """Save base64-encoded image data to a temp file.

    Uses content hash for filename to deduplicate identical images.

    Args:
        base64_data: Base64-encoded image string
        mime_type: MIME type (e.g., "image/png")

    Returns:
        Absolute file path to saved image, or None on failure.
    """
    try:
        _ensure_image_dir()
        ext = MIME_TO_EXT.get(mime_type, ".bin")

        # Use content hash for deduplication and unique naming
        content_hash = hashlib.md5(base64_data.encode("ascii")).hexdigest()[:12]
        filename = f"cell_output_{content_hash}{ext}"
        filepath = os.path.join(IMAGE_DIR, filename)

        # Skip if already saved (dedup)
        if os.path.exists(filepath):
            return filepath

        # Decode and write
        image_bytes = base64.b64decode(base64_data)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        logger.debug(f"Saved image: {filepath} ({len(image_bytes)} bytes)")
        return filepath
    except Exception as e:
        logger.warning(f"Failed to save image ({mime_type}): {e}")
        return None


def process_output_images(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single output's data dict, saving images and replacing with paths.

    Args:
        data: Output data dict with MIME type keys
              (e.g., {"image/png": "base64...", "text/plain": "..."})

    Returns:
        Modified data dict with image content replaced by path info string.
    """
    processed: Dict[str, Any] = {}
    for mime_type, content in data.items():
        if (
            mime_type in IMAGE_MIME_TYPES
            and isinstance(content, str)
            and len(content) > 0
        ):
            filepath = _save_image(content, mime_type)
            if filepath:
                # Compute human-readable size
                estimated_bytes = int(len(content) * 0.75)
                if estimated_bytes >= 1024 * 1024:
                    size_info = f"{estimated_bytes / (1024 * 1024):.2f} MB"
                elif estimated_bytes >= 1024:
                    size_info = f"{estimated_bytes / 1024:.1f} KB"
                else:
                    size_info = f"{estimated_bytes} bytes"

                format_name = mime_type.split("/")[1].upper()
                processed[mime_type] = (
                    f"[{format_name} image, {size_info} - saved to {filepath}]"
                )
            else:
                format_name = mime_type.split("/")[1].upper()
                processed[mime_type] = (
                    f"[{format_name} image - save failed, content omitted]"
                )
        else:
            processed[mime_type] = content
    return processed


def extract_image_paths(data: Dict[str, Any]) -> List[str]:
    """Extract image file paths from a processed output data dict.

    Args:
        data: Output data dict (after process_output_images)

    Returns:
        List of file paths found in the data values.
    """
    paths: List[str] = []
    for mime_type, content in data.items():
        if (
            mime_type in IMAGE_MIME_TYPES
            and isinstance(content, str)
            and "saved to " in content
        ):
            idx = content.find("saved to ")
            if idx >= 0:
                path = content[idx + len("saved to ") :].rstrip("]")
                paths.append(path)
    return paths


def process_outputs_list(
    outputs: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Process a list of Jupyter output objects, saving images from each.

    Args:
        outputs: List of output dicts (with "type", "data", etc.)

    Returns:
        Tuple of (processed_outputs, all_image_paths)
    """
    all_paths: List[str] = []
    processed: List[Dict[str, Any]] = []
    for output in outputs:
        output_copy = dict(output)
        if "data" in output_copy and isinstance(output_copy["data"], dict):
            output_copy["data"] = process_output_images(output_copy["data"])
            all_paths.extend(extract_image_paths(output_copy["data"]))
        processed.append(output_copy)
    return processed, all_paths
