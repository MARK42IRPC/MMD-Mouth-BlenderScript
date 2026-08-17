"""Discovery and process management for the optional Vosk worker.

Blender must not import Vosk directly.  This module is deliberately free of
Blender imports so it can be tested with the system Python and reused by the
Blender integration layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, Mapping

from ..constants import WORKER_PROTOCOL_VERSION


class WorkerRuntimeError(RuntimeError):
    """Raised when a worker cannot be resolved or started."""


@dataclass(frozen=True)
class WorkerResolution:
    """A validated command prefix for one worker runtime."""

    kind: str
    command_prefix: tuple[str, ...]
    executable_path: str
    working_directory: str
    display_name: str
    available: bool = True
    reason: str = ""
    protocol_version: int = WORKER_PROTOCOL_VERSION

    def command(self, *arguments: str) -> list[str]:
        return [*self.command_prefix, *arguments]

    def environment(self, addon_root: Path) -> Dict[str, str]:
        """Return an environment with the source checkout importable."""

        environment = os.environ.copy()
        if self.kind == "PYTHON":
            current = environment.get("PYTHONPATH", "")
            import_root = (
                addon_root.parent
                if (addon_root / "__init__.py").is_file()
                else addon_root
            )
            root = str(import_root)
            environment["PYTHONPATH"] = (
                root if not current else root + os.pathsep + current
            )
        return environment


@dataclass
class WorkerTask:
    """A one-shot worker process and its owned cache files."""

    task_id: str
    process: subprocess.Popen[Any]
    job_path: Path
    output_path: Path
    resolution: WorkerResolution
    started_at: float
    stderr_path: Path
    stderr_file: Any = field(default=None, repr=False)


@dataclass(frozen=True)
class WorkerPollResult:
    state: str
    payload: Dict[str, Any] | None = None
    error: str = ""
    returncode: int | None = None


def _as_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser()


def _existing_file(value: str | os.PathLike[str]) -> Path | None:
    path = _as_path(value)
    try:
        if path.is_file():
            return path.resolve()
    except OSError:
        return None
    return None


def _directory_worker_candidates(root: Path) -> list[Path]:
    names = (
        "mmd_mouth_worker.exe",
        "mmd-mouth-worker.exe",
        "mmd_mouth_worker",
        "mmd-mouth-worker",
    )
    return [root / name for name in names]


def _packaged_worker_candidates(addon_root: Path) -> list[Path]:
    directories = (
        addon_root / "runtime" / "windows",
        addon_root / "runtime" / "worker",
        addon_root / "runtime" / "mmd_mouth_worker",
        addon_root / "runtime",
        addon_root / "bin",
    )
    candidates: list[Path] = []
    for directory in directories:
        candidates.extend(_directory_worker_candidates(directory))
    return candidates


def _python_candidates(addon_root: Path) -> list[Path]:
    if os.name == "nt":
        names = (
            Path(".venv-worker") / "Scripts" / "python.exe",
            Path(".venv-worker") / "python.exe",
        )
    else:
        names = (Path(".venv-worker") / "bin" / "python",)
    return [addon_root / name for name in names]


def _unavailable(mode: str, reason: str) -> WorkerResolution:
    return WorkerResolution(
        kind=mode,
        command_prefix=(),
        executable_path="",
        working_directory="",
        display_name="Unavailable",
        available=False,
        reason=reason,
    )


def _packaged_resolution(path: Path, addon_root: Path) -> WorkerResolution:
    return WorkerResolution(
        kind="PACKAGED",
        command_prefix=(str(path),),
        executable_path=str(path),
        working_directory=str(addon_root),
        display_name="Bundled Vosk worker",
    )


def _python_resolution(path: Path, addon_root: Path) -> WorkerResolution:
    return WorkerResolution(
        kind="PYTHON",
        command_prefix=(str(path), "-m", "mmd_mouth.recognition.worker"),
        executable_path=str(path),
        working_directory=str(
            addon_root.parent if (addon_root / "__init__.py").is_file() else addon_root
        ),
        display_name="Development Vosk worker",
    )


def _custom_resolution(path: Path) -> WorkerResolution:
    return WorkerResolution(
        kind="CUSTOM",
        command_prefix=(str(path),),
        executable_path=str(path),
        working_directory=str(path.parent),
        display_name="Custom Vosk worker",
    )


def resolve_worker(
    addon_root: str | os.PathLike[str],
    *,
    mode: str = "AUTO",
    configured_executable: str = "",
    configured_python: str = "",
) -> WorkerResolution:
    """Resolve a worker without starting a process.

    Automatic mode intentionally never falls back to Blender's own Python.
    Blender's Python version and binary extension ABI are independent from the
    worker environment.
    """

    root = _as_path(addon_root).resolve()
    selected_mode = (mode or "AUTO").upper()
    if selected_mode not in {"AUTO", "PACKAGED", "PYTHON", "CUSTOM"}:
        return _unavailable(selected_mode, f"unknown worker mode: {selected_mode}")

    configured_executable_path = _existing_file(configured_executable)
    configured_python_path = _existing_file(configured_python)

    if selected_mode in {"AUTO", "CUSTOM"} and configured_executable:
        if configured_executable_path is not None:
            return _custom_resolution(configured_executable_path)
        if selected_mode == "CUSTOM":
            return _unavailable(
                selected_mode,
                f"configured worker executable does not exist: {configured_executable}",
            )

    if selected_mode in {"AUTO", "PACKAGED"}:
        for candidate in _packaged_worker_candidates(root):
            path = _existing_file(candidate)
            if path is not None:
                return _packaged_resolution(path, root)
        if selected_mode == "PACKAGED":
            return _unavailable(
                selected_mode,
                "no packaged worker was found in the add-on directory",
            )

    if selected_mode in {"AUTO", "PYTHON"}:
        if configured_python:
            if configured_python_path is not None:
                return _python_resolution(configured_python_path, root)
            if selected_mode == "PYTHON":
                return _unavailable(
                    selected_mode,
                    f"configured worker Python does not exist: {configured_python}",
                )
        for candidate in _python_candidates(root):
            path = _existing_file(candidate)
            if path is not None:
                return _python_resolution(path, root)
        if selected_mode == "PYTHON":
            return _unavailable(
                selected_mode,
                "no dedicated worker Python was found in the add-on directory",
            )

    return _unavailable(
        selected_mode,
        "no packaged worker or dedicated worker Python was found",
    )


def _hidden_process_options(
    working_directory: str,
    *,
    environment: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        "cwd": working_directory or None,
        "env": dict(environment) if environment is not None else None,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
    }
    if os.name == "nt":
        options["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        startupinfo_type = getattr(subprocess, "STARTUPINFO", None)
        if startupinfo_type is not None:
            startupinfo = startupinfo_type()
            startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
            startupinfo.wShowWindow = 0
            options["startupinfo"] = startupinfo
    return options


def probe_worker(
    resolution: WorkerResolution,
    *,
    addon_root: str | os.PathLike[str],
    timeout_sec: float = 5.0,
) -> Dict[str, Any]:
    """Run the cheap worker health command and validate its protocol."""

    if not resolution.available:
        raise WorkerRuntimeError(resolution.reason or "worker is unavailable")
    root = _as_path(addon_root).resolve()
    options = _hidden_process_options(
        resolution.working_directory,
        environment=resolution.environment(root),
    )
    options["stdout"] = subprocess.PIPE
    try:
        completed = subprocess.run(
            resolution.command("--health"),
            check=False,
            timeout=max(0.1, timeout_sec),
            text=True,
            encoding="utf-8",
            errors="replace",
            **options,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkerRuntimeError(f"worker health check failed: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise WorkerRuntimeError(
            f"worker health check exited with {completed.returncode}"
            + (f": {detail}" if detail else "")
        )
    try:
        payload = json.loads((completed.stdout or "").strip())
    except json.JSONDecodeError as exc:
        raise WorkerRuntimeError("worker health check returned invalid JSON") from exc
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise WorkerRuntimeError("worker health check returned an invalid response")
    protocol_version = int(payload.get("protocol_version", 0))
    if protocol_version != WORKER_PROTOCOL_VERSION:
        raise WorkerRuntimeError(
            "worker protocol mismatch: "
            f"expected {WORKER_PROTOCOL_VERSION}, got {protocol_version}"
        )
    return payload


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


class WorkerManager:
    """Start, poll, and cancel one-shot worker jobs."""

    def __init__(self, addon_root: str | os.PathLike[str]):
        self.addon_root = _as_path(addon_root).resolve()

    def resolve(self, **kwargs: str) -> WorkerResolution:
        return resolve_worker(self.addon_root, **kwargs)

    def probe(self, resolution: WorkerResolution) -> Dict[str, Any]:
        return probe_worker(resolution, addon_root=self.addon_root)

    def start(
        self,
        job: Mapping[str, Any],
        cache_directory: str | os.PathLike[str],
        *,
        resolution: WorkerResolution,
        task_id: str | None = None,
    ) -> WorkerTask:
        if not resolution.available:
            raise WorkerRuntimeError(resolution.reason or "worker is unavailable")
        task_id = task_id or uuid.uuid4().hex
        cache_root = _as_path(cache_directory).resolve()
        job_path = cache_root / "jobs" / f"{task_id}.json"
        output_path = cache_root / "results" / f"{task_id}.json"
        stderr_path = cache_root / "logs" / f"{task_id}.log"
        if output_path.exists():
            output_path.unlink()
        payload = dict(job)
        payload.setdefault("protocol_version", WORKER_PROTOCOL_VERSION)
        _write_json_atomic(job_path, payload)

        environment = resolution.environment(self.addon_root)
        options = _hidden_process_options(
            resolution.working_directory,
            environment=environment,
        )
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_file = stderr_path.open("w+b")
        options["stderr"] = stderr_file
        try:
            process = subprocess.Popen(
                resolution.command(
                    "--job",
                    str(job_path),
                    "--output",
                    str(output_path),
                ),
                **options,
            )
        except OSError as exc:
            stderr_file.close()
            raise WorkerRuntimeError(f"could not start Vosk worker: {exc}") from exc
        return WorkerTask(
            task_id=task_id,
            process=process,
            job_path=job_path,
            output_path=output_path,
            resolution=resolution,
            started_at=time.monotonic(),
            stderr_path=stderr_path,
            stderr_file=stderr_file,
        )

    @staticmethod
    def _read_stderr(task: WorkerTask) -> str:
        if task.stderr_file is None:
            return ""
        try:
            task.stderr_file.flush()
            task.stderr_file.seek(0)
            return task.stderr_file.read().decode("utf-8", "replace")
        except (AttributeError, OSError, ValueError):
            return ""
        finally:
            try:
                task.stderr_file.close()
            except (AttributeError, OSError, ValueError):
                pass
            task.stderr_file = None

    @staticmethod
    def poll(task: WorkerTask) -> WorkerPollResult:
        returncode = task.process.poll()
        if returncode is None:
            return WorkerPollResult(state="RUNNING")

        payload: Dict[str, Any] | None = None
        if task.output_path.is_file():
            try:
                with task.output_path.open("r", encoding="utf-8") as file:
                    loaded = json.load(file)
                if isinstance(loaded, dict):
                    payload = loaded
            except (OSError, json.JSONDecodeError) as exc:
                WorkerManager._read_stderr(task)
                return WorkerPollResult(
                    state="ERROR",
                    error=f"worker result could not be read: {exc}",
                    returncode=returncode,
                )

        stderr = WorkerManager._read_stderr(task)
        if payload is None:
            return WorkerPollResult(
                state="ERROR",
                error=(stderr.strip() or f"worker exited with {returncode}"),
                returncode=returncode,
            )
        if not payload.get("ok", False):
            return WorkerPollResult(
                state="ERROR",
                payload=payload,
                error=str(payload.get("error") or stderr.strip() or "worker job failed"),
                returncode=returncode,
            )
        return WorkerPollResult(
            state="DONE",
            payload=payload,
            returncode=returncode,
        )

    @staticmethod
    def cancel(task: WorkerTask) -> None:
        if task.process.poll() is None:
            task.process.terminate()
            try:
                task.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                task.process.kill()
                task.process.wait(timeout=1.0)
        if task.stderr_file is not None:
            task.stderr_file.close()
            task.stderr_file = None


__all__ = [
    "WorkerManager",
    "WorkerPollResult",
    "WorkerResolution",
    "WorkerRuntimeError",
    "WorkerTask",
    "probe_worker",
    "resolve_worker",
]
