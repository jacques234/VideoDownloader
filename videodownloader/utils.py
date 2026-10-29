from __future__ import annotations

import re
from urllib.parse import urlparse


def is_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme in {"http", "https"} and (
            host == "youtu.be"
            or host == "youtube.com"
            or host.endswith(".youtube.com")
            or host == "youtube-nocookie.com"
            or host.endswith(".youtube-nocookie.com")
        )
    except ValueError:
        return False


def format_speed(value: float) -> str:
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if value < 1024 or unit == "GB/s":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB/s"


def clean_error(exc: Exception) -> str:
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(exc)).strip()
    return (text or exc.__class__.__name__)[:900]
