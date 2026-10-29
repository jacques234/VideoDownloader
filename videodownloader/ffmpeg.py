from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def find_ffmpeg() -> str | None:
    """Busca FFmpeg junto al programa, en el proyecto o en el PATH."""
    executable = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    project_dir = Path(__file__).resolve().parent.parent
    roots = [project_dir]

    if getattr(sys, "frozen", False):
        roots.append(Path(sys.executable).resolve().parent)
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            roots.append(Path(bundle_dir))

    for root in dict.fromkeys(roots):
        for candidate in (
            root / "ffmpeg" / "bin" / executable,
            root / "ffmpeg" / executable,
            root / "bin" / executable,
            root / executable,
        ):
            if candidate.is_file():
                return str(candidate)

    return shutil.which("ffmpeg")
