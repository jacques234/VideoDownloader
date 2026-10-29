from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class JobStatus(str, Enum):
    QUEUED = "En espera"
    ANALYZING = "Analizando..."
    DOWNLOADING = "Descargando"
    PROCESSING = "Procesando..."
    COMPLETED = "¡Completado!"
    ERROR = "Error"
    CANCELLING = "Cancelando..."
    CANCELLED = "Cancelado"


ACTIVE_STATUSES = {
    JobStatus.ANALYZING,
    JobStatus.DOWNLOADING,
    JobStatus.PROCESSING,
    JobStatus.CANCELLING,
}

TERMINAL_STATUSES = {
    JobStatus.COMPLETED,
    JobStatus.ERROR,
    JobStatus.CANCELLED,
}


@dataclass(slots=True)
class DownloadJob:
    url: str
    quality: str
    output_dir: str
    id: str = field(default_factory=lambda: uuid4().hex)
    title: str = ""
    status: JobStatus = JobStatus.QUEUED
    progress: float | None = 0.0
    speed: float | None = None
    eta: int | None = None
    error: str | None = None
    cancel_event: threading.Event = field(
        default_factory=threading.Event, repr=False
    )


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    id: str
    url: str
    quality: str
    output_dir: str
    title: str
    status: JobStatus
    progress: float | None
    speed: float | None
    eta: int | None
    error: str | None

    @classmethod
    def from_job(cls, job: DownloadJob) -> "JobSnapshot":
        return cls(
            id=job.id,
            url=job.url,
            quality=job.quality,
            output_dir=job.output_dir,
            title=job.title,
            status=job.status,
            progress=job.progress,
            speed=job.speed,
            eta=job.eta,
            error=job.error,
        )
