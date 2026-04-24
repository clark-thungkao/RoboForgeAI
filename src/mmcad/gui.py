from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mmcad.app_service import BuildService
from mmcad.ipc_api import (
    api_get_artifacts,
    api_get_job_details,
    api_get_job_status,
    api_list_jobs,
    api_start_generation,
)


def _default_outdir(spec_path: str) -> str:
    spec = Path(spec_path)
    return str(spec.parent / "build")


def _job_line(job: dict) -> str:
    return f"{job['job_id']} | {job['status']} | {job['spec_path']}"


class MechaGui:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._service = BuildService()
        self._job_id: str | None = None
        self._job_ids: list[str] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self._root.title("MECHA Desktop Scaffold")
        self._root.geometry("960x620")

        frame = ttk.Frame(self._root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Spec path").grid(row=0, column=0, sticky="w")
        self._spec_var = tk.StringVar()
        self._spec_entry = ttk.Entry(frame, textvariable=self._spec_var, width=72)
        self._spec_entry.grid(row=1, column=0, sticky="ew")
        ttk.Button(frame, text="Browse...", command=self._browse_spec).grid(
            row=1, column=1, padx=(8, 0)
        )

        ttk.Label(frame, text="Output directory").grid(row=2, column=0, sticky="w", pady=(12, 0))
        self._outdir_var = tk.StringVar(value="build")
        self._outdir_entry = ttk.Entry(frame, textvariable=self._outdir_var, width=72)
        self._outdir_entry.grid(row=3, column=0, sticky="ew")
        ttk.Button(frame, text="Generate", command=self._start_generation).grid(
            row=3, column=1, padx=(8, 0)
        )

        ttk.Label(frame, text="Job status").grid(row=4, column=0, sticky="w", pady=(12, 0))
        self._status_var = tk.StringVar(value="Idle")
        ttk.Label(frame, textvariable=self._status_var).grid(row=5, column=0, sticky="w")

        ttk.Label(frame, text="Artifacts").grid(row=6, column=0, sticky="w", pady=(12, 0))
        self._artifacts = tk.Listbox(frame, height=12)
        self._artifacts.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(0, 12))

        history_wrap = ttk.LabelFrame(frame, text="Job History", padding=8)
        history_wrap.grid(row=8, column=0, columnspan=2, sticky="nsew")
        self._history = tk.Listbox(history_wrap, height=8)
        self._history.grid(row=0, column=0, sticky="nsew")
        self._history.bind("<<ListboxSelect>>", self._on_job_selected)
        ttk.Button(history_wrap, text="Refresh History", command=self._refresh_history).grid(
            row=1, column=0, sticky="e", pady=(8, 0)
        )

        details_wrap = ttk.LabelFrame(frame, text="Selected Job Details", padding=8)
        details_wrap.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        self._details = tk.Text(details_wrap, height=8, wrap=tk.WORD)
        self._details.grid(row=0, column=0, sticky="nsew")
        self._details.insert("1.0", "Select a job from history to view details.")
        self._details.config(state=tk.DISABLED)

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(7, weight=1)
        frame.rowconfigure(8, weight=1)
        frame.rowconfigure(9, weight=1)
        history_wrap.columnconfigure(0, weight=1)
        history_wrap.rowconfigure(0, weight=1)
        details_wrap.columnconfigure(0, weight=1)
        details_wrap.rowconfigure(0, weight=1)

    def _browse_spec(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select spec file",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")],
        )
        if not selected:
            return
        self._spec_var.set(selected)
        if self._outdir_var.get().strip() == "build":
            self._outdir_var.set(_default_outdir(selected))

    def _start_generation(self) -> None:
        spec_path = self._spec_var.get().strip()
        outdir = self._outdir_var.get().strip()
        if not spec_path:
            messagebox.showerror("Missing spec", "Please choose a spec file.")
            return
        if not outdir:
            messagebox.showerror("Missing output directory", "Please provide an output directory.")
            return

        result = api_start_generation(self._service, spec_path, outdir)
        if not result["ok"]:
            messagebox.showerror("Start failed", result["error"]["message"])
            return

        self._job_id = result["data"]["job_id"]
        self._status_var.set(f"Queued ({self._job_id})")
        self._artifacts.delete(0, tk.END)
        self._refresh_history()
        self._root.after(200, self._poll_status)

    def _poll_status(self) -> None:
        if self._job_id is None:
            return
        status_result = api_get_job_status(self._service, self._job_id)
        if not status_result["ok"]:
            self._status_var.set(f"Status error: {status_result['error']['message']}")
            return
        status = status_result["data"]["status"]
        self._status_var.set(f"{status.capitalize()} ({self._job_id})")
        if status in {"queued", "running"}:
            self._refresh_history()
            self._root.after(400, self._poll_status)
            return
        if status == "succeeded":
            artifact_result = api_get_artifacts(self._service, self._job_id)
            if artifact_result["ok"]:
                for path in artifact_result["data"]["files"]:
                    self._artifacts.insert(tk.END, path)
            else:
                self._artifacts.insert(tk.END, f"Artifact error: {artifact_result['error']['message']}")
        else:
            err = status_result["data"].get("error") or "Generation failed."
            self._artifacts.insert(tk.END, err)
        self._refresh_history()

    def _refresh_history(self) -> None:
        result = api_list_jobs(self._service, limit=20)
        if not result["ok"]:
            self._set_details_text(f"History error: {result['error']['message']}")
            return
        jobs = result["data"]["jobs"]
        self._job_ids = [str(job["job_id"]) for job in jobs]
        self._history.delete(0, tk.END)
        for job in jobs:
            self._history.insert(tk.END, _job_line(job))

    def _on_job_selected(self, _: object) -> None:
        idx = self._history.curselection()
        if not idx:
            return
        job_id = self._job_ids[idx[0]]
        result = api_get_job_details(self._service, job_id)
        if not result["ok"]:
            self._set_details_text(f"Details error: {result['error']['message']}")
            return
        data = result["data"]
        status = data["status"]
        lines = [
            f"Job ID: {status['job_id']}",
            f"Status: {status['status']}",
            f"Spec: {status['spec_path']}",
            f"Outdir: {status['outdir']}",
            f"Created: {status['created_at']}",
        ]
        if status.get("error"):
            lines.append(f"Error: {status['error']}")
        artifacts = data.get("artifacts")
        if artifacts:
            lines.append(f"Artifacts: {len(artifacts['files'])} file(s)")
        self._set_details_text("\n".join(lines))

    def _set_details_text(self, text: str) -> None:
        self._details.config(state=tk.NORMAL)
        self._details.delete("1.0", tk.END)
        self._details.insert("1.0", text)
        self._details.config(state=tk.DISABLED)


def launch() -> None:
    root = tk.Tk()
    MechaGui(root)
    root.mainloop()

