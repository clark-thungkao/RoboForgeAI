from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mmcad.app_service import BuildService
from mmcad.ipc_api import api_get_artifacts, api_get_job_status, api_start_generation


def _default_outdir(spec_path: str) -> str:
    spec = Path(spec_path)
    return str(spec.parent / "build")


class MechaGui:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._service = BuildService()
        self._job_id: str | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        self._root.title("MECHA Desktop Scaffold")
        self._root.geometry("760x500")

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
        self._artifacts.grid(row=7, column=0, columnspan=2, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(7, weight=1)

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


def launch() -> None:
    root = tk.Tk()
    MechaGui(root)
    root.mainloop()

