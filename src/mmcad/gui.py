from __future__ import annotations

from pathlib import Path
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from mmcad.app_service import BuildService
from mmcad.ipc_api import (
    api_cancel_generation,
    api_clear_finished_jobs,
    api_create_project,
    api_delete_job,
    api_get_artifacts,
    api_get_backend_health,
    api_get_job_details,
    api_get_job_stats,
    api_get_job_status,
    api_load_project,
    api_list_jobs,
    api_retry_job,
    api_save_project,
    api_start_generation,
)


_TEMPLATES = {
    "Bracket Demo": "examples/bracket_demo.yaml",
}


def _default_outdir(spec_path: str) -> str:
    spec = Path(spec_path)
    return str(spec.parent / "build")


def _default_project_path(spec_path: str) -> str:
    spec = Path(spec_path)
    return str(spec.with_suffix(".rfa.json"))


def _path_exists(path: str) -> bool:
    return Path(path).exists()


def _job_line(job: dict) -> str:
    return f"{job['job_id']} | {job['status']} | {job['spec_path']}"


def _job_details_text(status: dict, artifacts: dict | None) -> str:
    lines = [
        f"Job ID: {status['job_id']}",
        f"Status: {status['status']}",
        f"Spec: {status['spec_path']}",
        f"Outdir: {status['outdir']}",
        f"Created: {status['created_at']}",
    ]
    if status.get("error"):
        lines.append(f"Error: {status['error']}")
    if artifacts:
        lines.append(f"Artifacts: {len(artifacts['files'])} file(s)")
    return "\n".join(lines)


def _summary_text(health: dict, stats: dict) -> str:
    by_status = stats["by_status"]
    return (
        f"Backend: {health['status']} | "
        f"Total: {stats['total']} | "
        f"Active: {health['active_jobs']} | "
        f"Succeeded: {by_status['succeeded']} | "
        f"Failed: {by_status['failed']} | "
        f"Cancelled: {by_status['cancelled']}"
    )


def _action_enabled_states(selected_status: str | None) -> dict[str, bool]:
    if selected_status is None:
        return {"retry": False, "cancel": False, "delete": False}
    return {
        "retry": selected_status in {"succeeded", "failed", "cancelled"},
        "cancel": selected_status in {"queued", "running"},
        "delete": selected_status in {"succeeded", "failed", "cancelled"},
    }


def _artifact_folder(path: str) -> str:
    return str(Path(path).parent)


def _filter_jobs(jobs: list[dict], status_filter: str, query: str) -> list[dict]:
    filtered = jobs
    if status_filter != "all":
        filtered = [job for job in filtered if str(job["status"]) == status_filter]
    q = query.strip().lower()
    if q:
        filtered = [
            job
            for job in filtered
            if q in str(job["job_id"]).lower() or q in str(job["spec_path"]).lower()
        ]
    return filtered


class MechaGui:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        self._service = BuildService()
        self._job_id: str | None = None
        self._job_ids: list[str] = []
        self._jobs_by_id: dict[str, dict] = {}
        self._build_ui()
        self._root.after(100, self._refresh_dashboard)

    def _build_ui(self) -> None:
        self._root.title("MECHA Desktop")
        self._root.geometry("960x620")

        frame = ttk.Frame(self._root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Spec file (YAML)").grid(row=0, column=0, sticky="w")
        self._spec_var = tk.StringVar()
        self._spec_entry = ttk.Entry(frame, textvariable=self._spec_var, width=72)
        self._spec_entry.grid(row=1, column=0, sticky="ew")
        spec_actions = ttk.Frame(frame)
        spec_actions.grid(row=1, column=1, padx=(8, 0), sticky="e")
        ttk.Button(spec_actions, text="Browse...", command=self._browse_spec).grid(row=0, column=0)
        ttk.Button(spec_actions, text="Open Spec Folder", command=self._open_spec_folder).grid(
            row=0, column=1, padx=(8, 0)
        )

        quick_wrap = ttk.LabelFrame(frame, text="Template Quick Start", padding=8)
        quick_wrap.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        col = 0
        for label, spec_path in _TEMPLATES.items():
            ttk.Button(
                quick_wrap,
                text=label,
                command=lambda p=spec_path: self._apply_template(p),
            ).grid(row=0, column=col, padx=(0 if col == 0 else 8, 0))
            col += 1

        ttk.Label(frame, text="Output directory").grid(row=3, column=0, sticky="w", pady=(12, 0))
        self._outdir_var = tk.StringVar(value="build")
        self._outdir_entry = ttk.Entry(frame, textvariable=self._outdir_var, width=72)
        self._outdir_entry.grid(row=4, column=0, sticky="ew")
        row_actions = ttk.Frame(frame)
        row_actions.grid(row=4, column=1, padx=(8, 0), sticky="e")
        ttk.Button(row_actions, text="Generate", command=self._start_generation).grid(row=0, column=0)
        ttk.Button(row_actions, text="Open Output Folder", command=self._open_output_folder).grid(
            row=0, column=1, padx=(8, 0)
        )
        ttk.Button(row_actions, text="Save Project", command=self._save_project).grid(
            row=0, column=2, padx=(8, 0)
        )
        ttk.Button(row_actions, text="Load Project", command=self._load_project).grid(
            row=0, column=3, padx=(8, 0)
        )

        ttk.Label(frame, text="Current job status").grid(row=5, column=0, sticky="w", pady=(12, 0))
        self._status_var = tk.StringVar(value="Idle")
        ttk.Label(frame, textvariable=self._status_var).grid(row=6, column=0, sticky="w")
        self._summary_var = tk.StringVar(value="Backend: checking...")
        ttk.Label(frame, textvariable=self._summary_var).grid(row=6, column=1, sticky="e")
        self._message_var = tk.StringVar(value="Ready.")
        ttk.Label(frame, textvariable=self._message_var).grid(row=7, column=0, columnspan=2, sticky="w")

        ttk.Label(frame, text="Generated artifacts").grid(row=8, column=0, sticky="w", pady=(12, 0))
        self._artifacts = tk.Listbox(frame, height=12)
        self._artifacts.grid(row=9, column=0, columnspan=2, sticky="nsew", pady=(0, 12))
        self._artifacts.insert(tk.END, "No artifacts yet. Generate a job to populate this list.")
        artifact_actions = ttk.Frame(frame)
        artifact_actions.grid(row=10, column=0, columnspan=2, sticky="e", pady=(0, 8))
        ttk.Button(artifact_actions, text="Open Selected Artifact", command=self._open_selected_artifact).grid(
            row=0, column=0
        )
        ttk.Button(artifact_actions, text="Open Artifact Folder", command=self._open_artifact_folder).grid(
            row=0, column=1, padx=(8, 0)
        )

        history_wrap = ttk.LabelFrame(frame, text="Job History", padding=8)
        history_wrap.grid(row=11, column=0, columnspan=2, sticky="nsew")
        filter_bar = ttk.Frame(history_wrap)
        filter_bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(filter_bar, text="Status").grid(row=0, column=0, sticky="w")
        self._history_status_var = tk.StringVar(value="all")
        status_combo = ttk.Combobox(
            filter_bar,
            textvariable=self._history_status_var,
            values=["all", "queued", "running", "succeeded", "failed", "cancelled"],
            state="readonly",
            width=12,
        )
        status_combo.grid(row=0, column=1, padx=(8, 12))
        status_combo.bind("<<ComboboxSelected>>", self._on_history_filter_changed)
        ttk.Label(filter_bar, text="Search").grid(row=0, column=2, sticky="w")
        self._history_query_var = tk.StringVar()
        search_entry = ttk.Entry(filter_bar, textvariable=self._history_query_var, width=28)
        search_entry.grid(row=0, column=3, padx=(8, 0))
        search_entry.bind("<KeyRelease>", self._on_history_filter_changed)

        self._history = tk.Listbox(history_wrap, height=8)
        self._history.grid(row=1, column=0, sticky="nsew")
        self._history.bind("<<ListboxSelect>>", self._on_job_selected)
        actions = ttk.Frame(history_wrap)
        actions.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="Refresh", command=self._refresh_history).grid(row=0, column=0)
        self._retry_btn = ttk.Button(actions, text="Retry", command=self._retry_selected_job)
        self._retry_btn.grid(
            row=0, column=1, padx=(8, 0)
        )
        self._cancel_btn = ttk.Button(actions, text="Cancel", command=self._cancel_selected_job)
        self._cancel_btn.grid(
            row=0, column=2, padx=(8, 0)
        )
        self._delete_btn = ttk.Button(actions, text="Delete", command=self._delete_selected_job)
        self._delete_btn.grid(
            row=0, column=3, padx=(8, 0)
        )
        self._clear_btn = ttk.Button(actions, text="Clear Finished", command=self._clear_finished_jobs)
        self._clear_btn.grid(
            row=0, column=4, padx=(8, 0)
        )

        details_wrap = ttk.LabelFrame(frame, text="Selected Job Details", padding=8)
        details_wrap.grid(row=12, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        self._details = tk.Text(details_wrap, height=8, wrap=tk.WORD)
        self._details.grid(row=0, column=0, sticky="nsew")
        self._details.insert("1.0", "Select a job from history to view details.")
        self._details.config(state=tk.DISABLED)

        help_wrap = ttk.LabelFrame(frame, text="Quick Help", padding=8)
        help_wrap.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(
            help_wrap,
            text=(
                "1) Pick a spec or click a template. "
                "2) Choose output directory. "
                "3) Click Generate. "
                "4) Review history/details and open artifacts."
            ),
            wraplength=900,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="w")

        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(9, weight=1)
        frame.rowconfigure(11, weight=1)
        frame.rowconfigure(12, weight=1)
        history_wrap.columnconfigure(0, weight=1)
        history_wrap.rowconfigure(1, weight=1)
        details_wrap.columnconfigure(0, weight=1)
        details_wrap.rowconfigure(0, weight=1)
        help_wrap.columnconfigure(0, weight=1)
        self._update_action_buttons(None)

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

    def _apply_template(self, spec_path: str) -> None:
        self._spec_var.set(spec_path)
        self._outdir_var.set(_default_outdir(spec_path))
        self._message_var.set(f"Loaded template: {spec_path}")

    def _start_generation(self) -> None:
        spec_path = self._spec_var.get().strip()
        outdir = self._outdir_var.get().strip()
        if not spec_path:
            messagebox.showerror("Missing spec", "Please choose a spec file.")
            return
        if not _path_exists(spec_path):
            messagebox.showerror("Invalid spec path", "Spec file does not exist.")
            self._message_var.set("Start failed: spec file does not exist.")
            return
        if not outdir:
            messagebox.showerror("Missing output directory", "Please provide an output directory.")
            return

        result = api_start_generation(self._service, spec_path, outdir)
        if not result["ok"]:
            messagebox.showerror("Start failed", result["error"]["message"])
            self._message_var.set(f"Start failed: {result['error']['message']}")
            return

        self._job_id = result["data"]["job_id"]
        self._status_var.set(f"Queued ({self._job_id})")
        self._message_var.set("Generation started.")
        self._artifacts.delete(0, tk.END)
        self._artifacts.insert(tk.END, "Waiting for job completion...")
        self._refresh_history()
        self._root.after(200, self._poll_status)

    def _save_project(self) -> None:
        spec_path = self._spec_var.get().strip()
        outdir = self._outdir_var.get().strip()
        if not spec_path:
            messagebox.showerror("Missing spec", "Please choose a spec file before saving.")
            return
        if not outdir:
            messagebox.showerror("Missing output directory", "Please provide an output directory.")
            return
        project_result = api_create_project(name=Path(spec_path).stem, spec_path=spec_path, outdir=outdir)
        if not project_result["ok"]:
            messagebox.showerror("Save failed", project_result["error"]["message"])
            self._message_var.set(f"Save failed: {project_result['error']['message']}")
            return
        default_path = _default_project_path(spec_path)
        target = filedialog.asksaveasfilename(
            title="Save project file",
            defaultextension=".rfa.json",
            initialfile=Path(default_path).name,
            initialdir=str(Path(default_path).parent),
            filetypes=[
                ("RoboForge project", "*.rfa.json"),
                ("JSON files", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not target:
            return
        save_result = api_save_project(target, project_result["data"]["project"])
        if not save_result["ok"]:
            messagebox.showerror("Save failed", save_result["error"]["message"])
            self._message_var.set(f"Save failed: {save_result['error']['message']}")
            return
        self._message_var.set(f"Project saved to {target}")

    def _load_project(self) -> None:
        target = filedialog.askopenfilename(
            title="Load project file",
            filetypes=[
                ("RoboForge project", "*.rfa.json"),
                ("JSON files", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not target:
            return
        load_result = api_load_project(target)
        if not load_result["ok"]:
            messagebox.showerror("Load failed", load_result["error"]["message"])
            self._message_var.set(f"Load failed: {load_result['error']['message']}")
            return
        project = load_result["data"]["project"]
        self._spec_var.set(str(project["inputs"]["spec_path"]))
        self._outdir_var.set(str(project["generation_profile"]["outdir"]))
        self._message_var.set(f"Project loaded from {target}")

    def _open_spec_folder(self) -> None:
        spec_path = self._spec_var.get().strip()
        if not spec_path:
            messagebox.showinfo("No spec selected", "Choose or load a spec first.")
            return
        target = str(Path(spec_path).parent)
        try:
            subprocess.run(["cmd", "/c", "start", "", target], check=False)
        except Exception as err:  # pragma: no cover - OS integration
            messagebox.showerror("Open folder failed", str(err))
            self._message_var.set(f"Open folder failed: {err}")
            return
        self._message_var.set(f"Opened spec folder: {target}")

    def _open_output_folder(self) -> None:
        outdir = self._outdir_var.get().strip()
        if not outdir:
            messagebox.showinfo("No output directory", "Set an output directory first.")
            return
        target = str(Path(outdir))
        try:
            subprocess.run(["cmd", "/c", "start", "", target], check=False)
        except Exception as err:  # pragma: no cover - OS integration
            messagebox.showerror("Open folder failed", str(err))
            self._message_var.set(f"Open folder failed: {err}")
            return
        self._message_var.set(f"Opened output folder: {target}")

    def _poll_status(self) -> None:
        if self._job_id is None:
            return
        status_result = api_get_job_status(self._service, self._job_id)
        if not status_result["ok"]:
            self._status_var.set(f"Status error: {status_result['error']['message']}")
            self._message_var.set(f"Status error: {status_result['error']['message']}")
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
                self._artifacts.delete(0, tk.END)
                for path in artifact_result["data"]["files"]:
                    self._artifacts.insert(tk.END, path)
                self._message_var.set("Generation succeeded.")
            else:
                self._artifacts.insert(tk.END, f"Artifact error: {artifact_result['error']['message']}")
                self._message_var.set(f"Artifact error: {artifact_result['error']['message']}")
        else:
            err = status_result["data"].get("error") or "Generation failed."
            self._artifacts.delete(0, tk.END)
            self._artifacts.insert(tk.END, err)
            self._message_var.set(err)
        self._refresh_history()

    def _refresh_history(self) -> None:
        result = api_list_jobs(self._service, limit=20)
        if not result["ok"]:
            self._set_details_text(f"History error: {result['error']['message']}")
            self._message_var.set(f"History error: {result['error']['message']}")
            return
        jobs = result["data"]["jobs"]
        jobs = _filter_jobs(jobs, self._history_status_var.get(), self._history_query_var.get())
        self._jobs_by_id = {str(job["job_id"]): job for job in jobs}
        self._job_ids = [str(job["job_id"]) for job in jobs]
        self._history.delete(0, tk.END)
        if not jobs:
            self._history.insert(tk.END, "No jobs yet.")
        else:
            for job in jobs:
                self._history.insert(tk.END, _job_line(job))
        self._update_action_buttons(None)
        if jobs:
            self._message_var.set(f"Showing {len(jobs)} job(s) after filter.")

    def _on_history_filter_changed(self, _: object) -> None:
        self._refresh_history()

    def _on_job_selected(self, _: object) -> None:
        idx = self._history.curselection()
        if not idx:
            return
        if not self._job_ids:
            return
        job_id = self._job_ids[idx[0]]
        result = api_get_job_details(self._service, job_id)
        if not result["ok"]:
            self._set_details_text(f"Details error: {result['error']['message']}")
            self._message_var.set(f"Details error: {result['error']['message']}")
            return
        data = result["data"]
        self._set_details_text(_job_details_text(data["status"], data.get("artifacts")))
        self._update_action_buttons(data["status"]["status"])

    def _selected_job_id(self) -> str | None:
        idx = self._history.curselection()
        if not idx:
            messagebox.showinfo("No selection", "Please select a job from history first.")
            return None
        return self._job_ids[idx[0]]

    def _retry_selected_job(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        result = api_retry_job(self._service, job_id)
        if not result["ok"]:
            messagebox.showerror("Retry failed", result["error"]["message"])
            self._message_var.set(f"Retry failed: {result['error']['message']}")
            return
        self._job_id = result["data"]["job_id"]
        self._status_var.set(f"Retried as {self._job_id}")
        self._message_var.set(f"Retried {job_id} as {self._job_id}")
        self._refresh_history()
        self._root.after(200, self._poll_status)

    def _cancel_selected_job(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        result = api_cancel_generation(self._service, job_id)
        if not result["ok"]:
            messagebox.showerror("Cancel failed", result["error"]["message"])
            self._message_var.set(f"Cancel failed: {result['error']['message']}")
            return
        self._status_var.set(f"Cancel requested for {job_id}")
        self._message_var.set(f"Cancel requested for {job_id}")
        self._refresh_history()

    def _delete_selected_job(self) -> None:
        job_id = self._selected_job_id()
        if job_id is None:
            return
        result = api_delete_job(self._service, job_id)
        if not result["ok"]:
            messagebox.showerror("Delete failed", result["error"]["message"])
            self._message_var.set(f"Delete failed: {result['error']['message']}")
            return
        self._status_var.set(f"Deleted {job_id}")
        self._message_var.set(f"Deleted {job_id}")
        self._set_details_text("Select a job from history to view details.")
        self._refresh_history()

    def _clear_finished_jobs(self) -> None:
        result = api_clear_finished_jobs(self._service)
        if not result["ok"]:
            messagebox.showerror("Clear failed", result["error"]["message"])
            self._message_var.set(f"Clear failed: {result['error']['message']}")
            return
        removed = result["data"]["removed_count"]
        self._status_var.set(f"Cleared {removed} finished job(s)")
        self._message_var.set(f"Cleared {removed} finished job(s)")
        self._set_details_text("Select a job from history to view details.")
        self._refresh_history()

    def _set_details_text(self, text: str) -> None:
        self._details.config(state=tk.NORMAL)
        self._details.delete("1.0", tk.END)
        self._details.insert("1.0", text)
        self._details.config(state=tk.DISABLED)

    def _open_selected_artifact(self) -> None:
        idx = self._artifacts.curselection()
        if not idx:
            messagebox.showinfo("No artifact selected", "Please select an artifact first.")
            return
        target = self._artifacts.get(idx[0])
        try:
            subprocess.run(["cmd", "/c", "start", "", str(target)], check=False)
        except Exception as err:  # pragma: no cover - OS integration
            messagebox.showerror("Open failed", str(err))
            self._message_var.set(f"Open failed: {err}")
            return
        self._message_var.set(f"Opened artifact: {target}")

    def _open_artifact_folder(self) -> None:
        idx = self._artifacts.curselection()
        if not idx:
            messagebox.showinfo("No artifact selected", "Please select an artifact first.")
            return
        target = _artifact_folder(self._artifacts.get(idx[0]))
        try:
            subprocess.run(["cmd", "/c", "start", "", str(target)], check=False)
        except Exception as err:  # pragma: no cover - OS integration
            messagebox.showerror("Open folder failed", str(err))
            self._message_var.set(f"Open folder failed: {err}")
            return
        self._message_var.set(f"Opened artifact folder: {target}")

    def _refresh_dashboard(self) -> None:
        health_result = api_get_backend_health(self._service)
        stats_result = api_get_job_stats(self._service)
        if health_result["ok"] and stats_result["ok"]:
            self._summary_var.set(_summary_text(health_result["data"], stats_result["data"]))
        else:
            self._summary_var.set("Backend summary unavailable")
        self._root.after(1500, self._refresh_dashboard)

    def _update_action_buttons(self, selected_status: str | None) -> None:
        states = _action_enabled_states(selected_status)
        self._retry_btn.config(state=(tk.NORMAL if states["retry"] else tk.DISABLED))
        self._cancel_btn.config(state=(tk.NORMAL if states["cancel"] else tk.DISABLED))
        self._delete_btn.config(state=(tk.NORMAL if states["delete"] else tk.DISABLED))


def launch() -> None:
    root = tk.Tk()
    MechaGui(root)
    root.mainloop()


if __name__ == "__main__":
    launch()

