"""Image persistence: full image + 200px thumbnail."""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

THUMB_MAX = 200
SUPPORTED_FORMATS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


@dataclass(frozen=True)
class SavedImage:
    filename: str   # relative to data_dir/receipts/
    thumbnail: str  # relative to data_dir/receipts/thumbs/


def save_image_and_thumbnail(
    data: bytes, *, content_type: str, data_dir: Path
) -> SavedImage:
    ext = SUPPORTED_FORMATS.get(content_type, "jpg")
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("not an image") from e

    receipts_dir = data_dir / "receipts"
    thumbs_dir = receipts_dir / "thumbs"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    uid = uuid.uuid4().hex
    full_name = f"{uid}.{ext}"
    thumb_name = f"{uid}.jpg"  # thumbnails always JPEG

    full_path = receipts_dir / full_name
    full_path.write_bytes(data)

    with Image.open(full_path) as img:
        # Convert to RGB so we can save as JPEG even for PNG/WebP inputs
        thumb = img.convert("RGB")
        thumb.thumbnail((THUMB_MAX, THUMB_MAX))
        thumb.save(thumbs_dir / thumb_name, "JPEG", quality=85)

    return SavedImage(filename=full_name, thumbnail=thumb_name)
