"""
Image utility for saving cell output images to temp files.

Saves base64-encoded image data from Jupyter cell outputs to temporary
files and returns file paths for Claude's Read tool to view.
"""

import base64
import hashlib
import os
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

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

# Threshold for grouping images into a folder
IMAGE_GROUP_THRESHOLD = 3


def _ensure_image_dir(path: Optional[str] = None) -> str:
    """Create the image directory if it doesn't exist.

    Args:
        path: Optional specific path to create. Defaults to IMAGE_DIR.

    Returns:
        The path that was created/ensured.
    """
    target = path or IMAGE_DIR
    os.makedirs(target, exist_ok=True)
    return target


def _create_image_folder() -> str:
    """Create a timestamped subfolder for grouping multiple images.

    Returns:
        Path to the created folder (e.g., /tmp/instrmcp_images/batch_20260128_173000/)
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_path = os.path.join(IMAGE_DIR, f"batch_{timestamp}")
    _ensure_image_dir(folder_path)
    return folder_path


def _save_image(
    base64_data: str, mime_type: str, folder: Optional[str] = None
) -> Optional[str]:
    """Save base64-encoded image data to a temp file.

    Uses content hash for filename to deduplicate identical images.

    Args:
        base64_data: Base64-encoded image string
        mime_type: MIME type (e.g., "image/png")
        folder: Optional folder path to save to. Defaults to IMAGE_DIR.

    Returns:
        Absolute file path to saved image, or None on failure.
    """
    try:
        target_dir = folder or IMAGE_DIR
        _ensure_image_dir(target_dir)
        ext = MIME_TO_EXT.get(mime_type, ".bin")

        # Use content hash for deduplication and unique naming
        content_hash = hashlib.md5(base64_data.encode("ascii")).hexdigest()[:12]
        filename = f"cell_output_{content_hash}{ext}"
        filepath = os.path.join(target_dir, filename)

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


def process_output_images(
    data: Dict[str, Any], folder: Optional[str] = None
) -> Dict[str, Any]:
    """Process a single output's data dict, saving images and replacing with paths.

    Args:
        data: Output data dict with MIME type keys
              (e.g., {"image/png": "base64...", "text/plain": "..."})
        folder: Optional folder path to save images to. Defaults to IMAGE_DIR.

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
            # Check if this is a frontend fallback message for oversized images
            if content.startswith("[IMAGE TOO LARGE:"):
                # Pass through the fallback message as-is
                processed[mime_type] = content
                continue

            filepath = _save_image(content, mime_type, folder=folder)
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


def _count_images_in_outputs(outputs: List[Dict[str, Any]]) -> int:
    """Count total number of images across all outputs.

    Args:
        outputs: List of output dicts (with "type", "data", etc.)

    Returns:
        Total count of images found.
    """
    count = 0
    for output in outputs:
        if "data" in output and isinstance(output["data"], dict):
            for mime_type, content in output["data"].items():
                if (
                    mime_type in IMAGE_MIME_TYPES
                    and isinstance(content, str)
                    and len(content) > 0
                ):
                    count += 1
    return count


def process_outputs_list(
    outputs: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], Union[List[str], str]]:
    """Process a list of Jupyter output objects, saving images from each.

    If more than IMAGE_GROUP_THRESHOLD images are present, saves all images to a
    timestamped folder and returns the folder path instead of individual paths.

    Args:
        outputs: List of output dicts (with "type", "data", etc.)

    Returns:
        Tuple of (processed_outputs, image_paths_or_folder) where image_paths_or_folder
        is either a list of individual file paths (if <= 3 images) or a single folder
        path string (if > 3 images).
    """
    # First pass: count images to determine grouping strategy
    image_count = _count_images_in_outputs(outputs)

    # Determine target folder (None for individual saves, or timestamped folder)
    folder: Optional[str] = None
    if image_count > IMAGE_GROUP_THRESHOLD:
        folder = _create_image_folder()

    # Second pass: process outputs with the determined folder
    all_paths: List[str] = []
    processed: List[Dict[str, Any]] = []
    for output in outputs:
        output_copy = dict(output)
        if "data" in output_copy and isinstance(output_copy["data"], dict):
            output_copy["data"] = process_output_images(output_copy["data"], folder)
            all_paths.extend(extract_image_paths(output_copy["data"]))
        processed.append(output_copy)

    # Return folder path if grouped, otherwise return individual paths
    if folder is not None:
        return processed, folder
    return processed, all_paths
