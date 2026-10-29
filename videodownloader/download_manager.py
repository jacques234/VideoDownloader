from __future__ import annotations

import os
import queue
import threading
from collections.abc import Callable

from .engine import YtDlpEngine
from .models import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    DownloadJob,
    JobSnapshot,
    JobStatus,
)
from .utils import clean_error


class DownloadManager:
    """Cola FIFO atendida por un grupo fijo de trabajadores daemon."""

    def __init__(
        self,
        ffmpeg_path: str | None,
        listener: Callable[[JobSnapshot], None],
        max_workers: int = 10,
    ):
        if not 1 <= max_workers <= 10:
            raise ValueError("max_workers debe estar entre 1 y 10")

        self.max_workers = max_workers
        self._listener = listener
        self._engine = YtDlpEngine(ffmpeg_path)
        self._jobs: dict[str, DownloadJob] = {}
        self._lock = threading.RLock()
        self._queue: queue.Queue[str] = queue.Queue()
        self._shutdown = threading.Event()
        self._workers = []

        for index in range(max_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"download-worker-{index + 1}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

    def add_job(self, url: str, quality: str, output_dir: str) -> JobSnapshot:
        if self._shutdown.is_set():
            raise RuntimeError("El gestor de descargas está cerrado")

        job = DownloadJob(url=url, quality=quality, output_dir=output_dir)
        with self._lock:
            for existing in self._jobs.values():
                same_url = existing.url == url
                same_folder = os.path.normcase(
                    os.path.abspath(existing.output_dir)
                ) == os.path.normcase(os.path.abspath(output_dir))
                unfinished = (
                    existing.status == JobStatus.QUEUED
                    or existing.status in ACTIVE_STATUSES
                )
                if same_url and same_folder and unfinished:
                    raise ValueError("Este video ya está en la cola para esa carpeta")
            self._jobs[job.id] = job
            snapshot = JobSnapshot.from_job(job)

        self._notify(snapshot)
        self._queue.put(job.id)
        return snapshot

    def cancel(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status in TERMINAL_STATUSES:
                return
            job.cancel_event.set()
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
            else:
                job.status = JobStatus.CANCELLING
            snapshot = JobSnapshot.from_job(job)
        self._notify(snapshot)

    def get_snapshot(self, job_id: str) -> JobSnapshot | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return JobSnapshot.from_job(job) if job else None

    @property
    def active_count(self) -> int:
        with self._lock:
            return sum(
                job.status in ACTIVE_STATUSES for job in self._jobs.values()
            )

    @property
    def has_unfinished(self) -> bool:
        with self._lock:
            return any(
                job.status == JobStatus.QUEUED or job.status in ACTIVE_STATUSES
                for job in self._jobs.values()
            )

    def shutdown(self) -> None:
        self._shutdown.set()
        notifications = []
        with self._lock:
            for job in self._jobs.values():
                if job.status in TERMINAL_STATUSES:
                    continue
                job.cancel_event.set()
                job.status = (
                    JobStatus.CANCELLED
                    if job.status == JobStatus.QUEUED
                    else JobStatus.CANCELLING
                )
                notifications.append(JobSnapshot.from_job(job))
        for snapshot in notifications:
            self._notify(snapshot)

    def _worker_loop(self) -> None:
        while not self._shutdown.is_set():
            try:
                job_id = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                with self._lock:
                    job = self._jobs.get(job_id)
                    if not job or job.status != JobStatus.QUEUED:
                        continue
                    job.status = JobStatus.ANALYZING
                    snapshot = JobSnapshot.from_job(job)
                self._notify(snapshot)
                self._run_job(job)
            finally:
                self._queue.task_done()

    def _run_job(self, job: DownloadJob) -> None:
        try:
            self._engine.download(job, self._progress_callback(job.id))
        except Exception as exc:
            with self._lock:
                if job.cancel_event.is_set():
                    job.status = JobStatus.CANCELLED
                else:
                    job.status = JobStatus.ERROR
                    job.error = clean_error(exc)
                job.speed = None
                job.eta = None
                snapshot = JobSnapshot.from_job(job)
        else:
            with self._lock:
                job.status = (
                    JobStatus.CANCELLED
                    if job.cancel_event.is_set()
                    else JobStatus.COMPLETED
                )
                job.progress = 1.0 if job.status == JobStatus.COMPLETED else 0.0
                job.speed = None
                job.eta = None
                snapshot = JobSnapshot.from_job(job)
        self._notify(snapshot)

    def _progress_callback(self, job_id: str):
        def update(status, progress, speed, eta, title):
            with self._lock:
                job = self._jobs.get(job_id)
                if (
                    not job
                    or job.status in TERMINAL_STATUSES
                    or job.cancel_event.is_set()
                ):
                    return
                job.status = status
                job.progress = progress
                job.speed = speed
                job.eta = eta
                job.title = title or job.title
                snapshot = JobSnapshot.from_job(job)
            self._notify(snapshot)

        return update

    def _notify(self, snapshot: JobSnapshot) -> None:
        self._listener(snapshot)
