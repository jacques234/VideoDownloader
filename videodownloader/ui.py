from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .download_manager import DownloadManager
from .ffmpeg import find_ffmpeg
from .formats import QUALITIES
from .models import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    JobSnapshot,
    JobStatus,
)
from .utils import format_speed, is_youtube_url


class DownloadRow(ctk.CTkFrame):
    def __init__(self, master, snapshot: JobSnapshot, cancel_command):
        super().__init__(master, corner_radius=10)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=0)

        self.title_label = ctk.CTkLabel(
            self,
            text=snapshot.url,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.title_label.grid(
            row=0, column=0, padx=(14, 8), pady=(12, 4), sticky="w"
        )

        self.status_label = ctk.CTkLabel(self, text=snapshot.status.value)
        self.status_label.grid(row=0, column=1, padx=8, pady=(12, 4), sticky="e")

        self.cancel_button = ctk.CTkButton(
            self,
            text="Cancelar",
            width=82,
            height=26,
            fg_color="gray45",
            hover_color="gray35",
            command=cancel_command,
        )
        self.cancel_button.grid(row=0, column=2, padx=(4, 14), pady=(12, 4))

        self.progress_bar = ctk.CTkProgressBar(self, height=9)
        self.progress_bar.grid(
            row=1, column=0, columnspan=2, padx=(14, 8), pady=4, sticky="ew"
        )
        self.progress_bar.set(0)

        self.percent_label = ctk.CTkLabel(self, text="0%", width=70, anchor="e")
        self.percent_label.grid(row=1, column=2, padx=(4, 14), pady=4, sticky="e")

        self.detail_label = ctk.CTkLabel(
            self,
            text=snapshot.quality,
            text_color="gray60",
            anchor="w",
            wraplength=790,
        )
        self.detail_label.grid(
            row=2, column=0, columnspan=3, padx=14, pady=(2, 12), sticky="ew"
        )

    def update_snapshot(self, snapshot: JobSnapshot) -> None:
        self.title_label.configure(text=snapshot.title or snapshot.url)
        progress = snapshot.progress
        self.progress_bar.set(progress if progress is not None else 0)

        if progress is None:
            percent_text = "—"
        else:
            percent_text = f"{progress * 100:.1f}%"
        self.percent_label.configure(text=percent_text)

        if snapshot.status == JobStatus.DOWNLOADING and progress is not None:
            status_text = f"Descargando {progress * 100:.1f}%"
        else:
            status_text = snapshot.status.value
        self.status_label.configure(text=status_text)

        if snapshot.status == JobStatus.ERROR:
            detail = snapshot.error or "No se pudo completar la descarga"
        elif snapshot.status == JobStatus.COMPLETED:
            detail = f"Guardado en: {snapshot.output_dir}"
        else:
            details = []
            if snapshot.speed:
                details.append(format_speed(snapshot.speed))
            if snapshot.eta is not None:
                details.append(f"quedan {snapshot.eta} s")
            details.append(snapshot.quality)
            detail = " · ".join(details)
        self.detail_label.configure(text=detail)

        self.cancel_button.configure(
            state="disabled" if snapshot.status in TERMINAL_STATUSES else "normal"
        )


class VideoDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("VideoDownloader - YouTube")
        self.geometry("1000x760")
        self.resizable(False, False)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.ffmpeg_path = find_ffmpeg()
        self.output_dir = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.quality = tk.StringVar(value=QUALITIES[0])
        self.rows: dict[str, DownloadRow] = {}
        self.snapshots: dict[str, JobSnapshot] = {}
        self.reported_errors: set[str] = set()
        self.closing = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        container = ctk.CTkFrame(self, corner_radius=16)
        container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(
            container,
            text="Gestor de descargas de YouTube",
            font=ctk.CTkFont(size=25, weight="bold"),
        ).grid(row=0, column=0, padx=24, pady=(22, 2), sticky="w")
        ctk.CTkLabel(
            container,
            text="Añade varios enlaces: hasta 10 descargas simultáneas.",
            text_color="gray60",
        ).grid(row=1, column=0, padx=24, pady=(0, 14), sticky="w")

        form = ctk.CTkFrame(container, fg_color="transparent")
        form.grid(row=2, column=0, padx=24, sticky="ew")
        form.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(form, text="Enlace de YouTube").grid(
            row=0, column=0, pady=(0, 4), sticky="w"
        )
        self.url_entry = ctk.CTkEntry(
            form,
            height=38,
            placeholder_text="https://www.youtube.com/watch?v=...",
        )
        self.url_entry.grid(row=1, column=0, pady=(0, 10), sticky="ew")
        self.url_entry.bind("<Return>", lambda _event: self.add_download())

        ctk.CTkLabel(form, text="Calidad y formato").grid(
            row=2, column=0, pady=(0, 4), sticky="w"
        )
        self.quality_menu = ctk.CTkOptionMenu(
            form, values=list(QUALITIES), variable=self.quality, height=36
        )
        self.quality_menu.grid(row=3, column=0, pady=(0, 10), sticky="ew")

        ctk.CTkLabel(form, text="Carpeta de destino").grid(
            row=4, column=0, pady=(0, 4), sticky="w"
        )
        folder_frame = ctk.CTkFrame(form, fg_color="transparent")
        folder_frame.grid(row=5, column=0, sticky="ew")
        folder_frame.grid_columnconfigure(0, weight=1)

        self.folder_entry = ctk.CTkEntry(
            folder_frame,
            textvariable=self.output_dir,
            state="readonly",
            height=36,
        )
        self.folder_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkButton(
            folder_frame,
            text="Cambiar carpeta",
            width=140,
            command=self.choose_folder,
        ).grid(row=0, column=1)

        action_frame = ctk.CTkFrame(form, fg_color="transparent")
        action_frame.grid(row=6, column=0, pady=(12, 14), sticky="ew")
        action_frame.grid_columnconfigure(0, weight=1)

        ffmpeg_text = (
            "FFmpeg integrado y disponible"
            if self.ffmpeg_path
            else "FFmpeg no detectado: se usarán formatos compatibles"
        )
        ctk.CTkLabel(
            action_frame, text=ffmpeg_text, text_color="gray60"
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            action_frame,
            text="Añadir descarga",
            width=170,
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.add_download,
        ).grid(row=0, column=1, sticky="e")

        list_header = ctk.CTkFrame(container, fg_color="transparent")
        list_header.grid(row=3, column=0, padx=24, pady=(0, 6), sticky="ew")
        list_header.grid_columnconfigure(0, weight=1)

        self.summary_label = ctk.CTkLabel(
            list_header,
            text="Activas: 0/10 · En espera: 0",
            font=ctk.CTkFont(weight="bold"),
        )
        self.summary_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            list_header,
            text="Limpiar finalizadas",
            width=140,
            height=28,
            fg_color="gray45",
            hover_color="gray35",
            command=self.clear_finished,
        ).grid(row=0, column=1, sticky="e")

        self.job_list = ctk.CTkScrollableFrame(container, corner_radius=10)
        self.job_list.grid(
            row=4, column=0, padx=24, pady=(0, 20), sticky="nsew"
        )
        self.job_list.grid_columnconfigure(0, weight=1)

        self.manager = DownloadManager(
            ffmpeg_path=self.ffmpeg_path,
            listener=self.on_job_event,
            max_workers=10,
        )

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.url_entry.focus_set)

    def choose_folder(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="Selecciona la carpeta de destino",
            initialdir=self.output_dir.get(),
            mustexist=True,
        )
        if selected:
            self.output_dir.set(selected)

    def add_download(self) -> None:
        url = self.url_entry.get().strip()
        if not is_youtube_url(url):
            messagebox.showwarning(
                "Enlace no válido",
                "Introduce un enlace válido de YouTube (http o https).",
                parent=self,
            )
            self.url_entry.focus_set()
            return

        destination = Path(self.output_dir.get()).expanduser()
        try:
            destination.mkdir(parents=True, exist_ok=True)
            snapshot = self.manager.add_job(
                url, self.quality.get(), str(destination)
            )
        except (OSError, ValueError) as exc:
            messagebox.showerror("No se pudo añadir", str(exc), parent=self)
            return

        row = DownloadRow(
            self.job_list,
            snapshot,
            cancel_command=lambda: self.manager.cancel(snapshot.id),
        )
        row.grid(
            row=len(self.rows), column=0, padx=4, pady=5, sticky="ew"
        )
        self.rows[snapshot.id] = row
        self.snapshots[snapshot.id] = snapshot
        self.url_entry.delete(0, "end")
        self.update_summary()
        self.url_entry.focus_set()

    def on_job_event(self, snapshot: JobSnapshot) -> None:
        try:
            self.after(0, self.apply_snapshot, snapshot)
        except (tk.TclError, RuntimeError):
            pass

    def apply_snapshot(self, snapshot: JobSnapshot) -> None:
        if self.closing:
            return
        row = self.rows.get(snapshot.id)
        if row:
            row.update_snapshot(snapshot)
        self.snapshots[snapshot.id] = snapshot
        self.update_summary()

        if (
            snapshot.status == JobStatus.ERROR
            and snapshot.id not in self.reported_errors
        ):
            self.reported_errors.add(snapshot.id)
            messagebox.showerror(
                "Error de descarga",
                f"{snapshot.title or snapshot.url}\n\n"
                "Comprueba el enlace, tu conexión y los permisos de la carpeta.\n"
                f"Detalle: {snapshot.error}",
                parent=self,
            )

    def update_summary(self) -> None:
        active = sum(
            snapshot.status in ACTIVE_STATUSES
            for snapshot in self.snapshots.values()
        )
        queued = sum(
            snapshot.status == JobStatus.QUEUED
            for snapshot in self.snapshots.values()
        )
        self.summary_label.configure(
            text=f"Activas: {active}/10 · En espera: {queued}"
        )

    def clear_finished(self) -> None:
        for job_id, snapshot in list(self.snapshots.items()):
            if snapshot.status not in TERMINAL_STATUSES:
                continue
            row = self.rows.pop(job_id, None)
            if row:
                row.destroy()
            self.snapshots.pop(job_id, None)
            self.reported_errors.discard(job_id)

        for index, row in enumerate(self.rows.values()):
            row.grid_configure(row=index)

    def on_close(self) -> None:
        if self.manager.has_unfinished and not messagebox.askyesno(
            "Descargas en curso",
            "Si cierras ahora, las descargas se interrumpirán. ¿Deseas salir?",
            parent=self,
        ):
            return
        self.closing = True
        self.manager.shutdown()
        self.destroy()
