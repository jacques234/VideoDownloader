from __future__ import annotations

from typing import Callable

import yt_dlp

from .formats import build_options
from .models import DownloadJob, JobStatus


ProgressCallback = Callable[
    [JobStatus, float | None, float | None, int | None, str], None
]


class DownloadCancelled(Exception):
    pass


class YtDlpEngine:
    """Adaptador aislado de yt-dlp; cada trabajo crea su propio YoutubeDL."""

    def __init__(self, ffmpeg_path: str | None):
        self.ffmpeg_path = ffmpeg_path

    def download(self, job: DownloadJob, callback: ProgressCallback) -> None:
        options = build_options(
            job.quality,
            job.output_dir,
            self.ffmpeg_path,
            lambda data: self._progress_hook(job, data, callback),
        )
        self._check_cancelled(job)
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([job.url])
        self._check_cancelled(job)

    @staticmethod
    def _check_cancelled(job: DownloadJob) -> None:
        if job.cancel_event.is_set():
            raise DownloadCancelled

    def _progress_hook(
        self,
        job: DownloadJob,
        data: dict,
        callback: ProgressCallback,
    ) -> None:
        self._check_cancelled(job)
        info = data.get("info_dict") or {}
        title = str(info.get("title") or job.title)

        if data.get("status") == "downloading":
            downloaded = float(data.get("downloaded_bytes") or 0)
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            fraction = min(max(downloaded / total, 0), 1) if total else None
            speed = data.get("speed")
            eta = data.get("eta")
            callback(
                JobStatus.DOWNLOADING,
                fraction,
                float(speed) if speed else None,
                int(eta) if eta is not None else None,
                title,
            )
        elif data.get("status") == "finished":
            callback(JobStatus.PROCESSING, 1.0, None, None, title)
