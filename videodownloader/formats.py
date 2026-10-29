from __future__ import annotations

import os
from typing import Any, Callable


QUALITIES = (
    "Mejor calidad disponible (MP4)",
    "1080p Full HD (MP4)",
    "720p HD (MP4)",
    "480p (MP4)",
    "Solo Audio (M4A/MP3)",
)


def build_options(
    quality: str,
    output_dir: str,
    ffmpeg_path: str | None,
    progress_hook: Callable[[dict], None],
) -> dict[str, Any]:
    """Construye filtros que nunca requieren mezclar pistas sin FFmpeg."""
    options: dict[str, Any] = {
        "outtmpl": os.path.join(output_dir, "%(title)s [%(id)s].%(ext)s"),
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 3,
        "fragment_retries": 3,
        "windowsfilenames": os.name == "nt",
    }

    if ffmpeg_path:
        options["ffmpeg_location"] = ffmpeg_path

    if quality == "Solo Audio (M4A/MP3)":
        if ffmpeg_path:
            options["format"] = "bestaudio/best"
            options["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            options["format"] = (
                "bestaudio[ext=m4a]/bestaudio[ext=webm]/"
                "bestaudio/best[ext=m4a]/best"
            )
        return options

    height_filters = {
        "1080p Full HD (MP4)": "[height<=1080]",
        "720p HD (MP4)": "[height<=720]",
        "480p (MP4)": "[height<=480]",
    }
    height = height_filters.get(quality, "")

    if ffmpeg_path:
        options["format"] = (
            f"bestvideo{height}[ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo{height}+bestaudio/"
            f"best{height}[ext=mp4]/best{height}/best"
        )
        options["merge_output_format"] = "mp4"
    else:
        # 'best' evita seleccionar pistas separadas que no se pueden mezclar.
        options["format"] = (
            f"best{height}[ext=mp4]/best{height}/best[ext=mp4]/best"
        )

    return options
