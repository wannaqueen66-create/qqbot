import base64
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image


def image_file_to_data_url(
    path: str | Path,
    max_px: int = 1024,
    quality: int = 85,
    force_format: str = "JPEG",
) -> str:
    """Convert local image to a compact data URL.

    - Resize so the longest side <= max_px
    - Re-encode as JPEG by default (smaller)

    Returns: data:image/jpeg;base64,...
    """
    p = Path(path)
    img = Image.open(p)
    img = img.convert("RGB")

    w, h = img.size
    scale = min(1.0, float(max_px) / float(max(w, h)))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)))

    buf = BytesIO()
    img.save(buf, format=force_format, quality=quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    mime = "image/jpeg" if force_format.upper() == "JPEG" else "image/png"
    return f"data:{mime};base64,{b64}"


def strip_data_url_prefix(data_url: str) -> str:
    """Return base64 part for OneBot base64:// send."""
    if "," in data_url:
        return data_url.split(",", 1)[1]
    return data_url
