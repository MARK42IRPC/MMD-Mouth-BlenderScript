"""Blender-main-thread integration for the Vosk worker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import uuid
from typing import Any, Dict

import bpy
from bpy.app.handlers import persistent

from .bundled_models import bundled_payload, ensure_settings_models
from .constants import (
    IPA_NORMALIZATION_VERSION,
    LANGUAGE_ITEMS,
    SCHEMA_VERSION,
    TIMELINE_VERSION,
    WORKER_PROTOCOL_VERSION,
)
from .recognition.runtime import (
    WorkerManager,
    WorkerRuntimeError,
    WorkerTask,
    resolve_worker,
)
from .properties import sort_clip_events
from .transcoding import ensure_compatible_audio


@dataclass
class _ActiveRecognition:
    task: WorkerTask
    scene_name: str
    profile_id: str
    clip_id: str
    generate_after_recognition: bool = False


_MANAGER: WorkerManager | None = None
_ACTIVE: _ActiveRecognition | None = None
_TIMER_REGISTERED = False
_RECONCILE_TIMER_REGISTERED = False


def _addon_root() -> Path:
    return Path(__file__).resolve().parent


def _manager() -> WorkerManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = WorkerManager(_addon_root())
    return _MANAGER


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _absolute_path(value: str) -> str:
    if not value:
        return ""
    return bpy.path.abspath(value)


def _tag_redraw() -> None:
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                area.tag_redraw()
    except (AttributeError, RuntimeError):
        pass


def is_recognition_active() -> bool:
    return _ACTIVE is not None


def _clear_orphaned_scene_state(scene: Any) -> bool:
    settings = getattr(scene, "mmd_mouth", None)
    if settings is None:
        return False
    changed = False
    if settings.is_busy:
        settings.is_busy = False
        changed = True
    if settings.worker_task_id:
        settings.worker_task_id = ""
        changed = True
    if settings.worker_status == "RUNNING":
        settings.worker_status = "UNKNOWN"
        settings.worker_last_error = ""
        changed = True
    for profile in settings.model_profiles:
        for clip in profile.clips:
            if clip.status != "RUNNING":
                continue
            clip.status = "RECOGNIZED" if clip.events else "DRAFT"
            clip.last_error = ""
            changed = True
    return changed


def reconcile_runtime_state(scene: Any | None = None) -> bool:
    """Clear persisted RUNNING flags that have no matching Python task."""

    targets = [scene] if scene is not None else list(bpy.data.scenes)
    changed = False
    for target in targets:
        if target is None:
            continue
        if _ACTIVE is not None and target.name == _ACTIVE.scene_name:
            continue
        changed = _clear_orphaned_scene_state(target) or changed
    if changed:
        _tag_redraw()
    return changed


def _set_worker_state(
    settings: Any,
    *,
    status: str,
    display_name: str = "",
    error: str = "",
) -> None:
    settings.worker_status = status
    if display_name:
        settings.worker_display_name = display_name
    settings.worker_last_check = _timestamp()
    settings.worker_last_error = error


def resolve_for_settings(settings: Any):
    return resolve_worker(
        _addon_root(),
        mode=settings.worker_mode,
        configured_executable=_absolute_path(settings.worker_executable),
        configured_python=_absolute_path(settings.worker_python),
    )


def check_worker(settings: Any) -> bool:
    """Probe the worker and mirror the result into Blender RNA."""

    resolution = resolve_for_settings(settings)
    if not resolution.available:
        _set_worker_state(
            settings,
            status="MISSING",
            display_name="Unavailable",
            error=resolution.reason,
        )
        return False
    try:
        payload = _manager().probe(resolution)
    except WorkerRuntimeError as exc:
        _set_worker_state(
            settings,
            status="ERROR",
            display_name=resolution.display_name,
            error=str(exc),
        )
        return False
    settings.worker_protocol_version = int(
        payload.get("protocol_version", WORKER_PROTOCOL_VERSION)
    )
    _set_worker_state(
        settings,
        status="READY",
        display_name=resolution.display_name,
    )
    return True


def _find_profile(settings: Any, profile_id: str) -> Any | None:
    for profile in settings.model_profiles:
        if profile.profile_id == profile_id:
            return profile
    return None


def _find_clip(profile: Any, clip_id: str) -> Any | None:
    for clip in profile.clips:
        if clip.clip_id == clip_id:
            return clip
    return None


def _cache_directory(scene: Any, settings: Any) -> Path:
    configured = _absolute_path(settings.cache_directory)
    if configured:
        directory = Path(configured)
    elif bpy.data.filepath:
        directory = Path(bpy.data.filepath).resolve().parent / ".mmd_mouth_cache"
    else:
        directory = Path(bpy.app.tempdir) / "mmd_mouth"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _model_payloads(settings: Any, clip: Any) -> list[Dict[str, Any]]:
    ensure_settings_models(settings)
    payloads: list[Dict[str, Any]] = []
    requested_language = clip.language_code.strip().replace("_", "-").lower()
    requested_family = requested_language.split("-", 1)[0]
    use_language_filter = requested_language not in {"", "auto", "mixed", "und"}
    for model in settings.recognizer_models:
        if not model.enabled:
            continue
        if clip.recognizer_model_filter and (
            model.model_id != clip.recognizer_model_filter
        ):
            continue
        model_family = (
            model.language_code.strip().replace("_", "-").lower().split("-", 1)[0]
        )
        if (
            not clip.recognizer_model_filter
            and use_language_filter
            and model_family != requested_family
        ):
            continue
        if not model.model_id or not model.language_code or not model.model_path:
            continue
        payload = {
            "model_id": model.model_id,
            "language_code": model.language_code,
            "model_path": _absolute_path(model.model_path),
            "calibration_bias": model.calibration_bias,
            "calibration_temperature": model.calibration_temperature,
            "enabled": True,
            "priority": model.priority,
        }
        payload.update(bundled_payload(model))
        payloads.append(payload)
    if not payloads:
        raise ValueError(
            "no enabled Vosk model is configured; add a model directory first"
        )
    return payloads


def _job_payload(scene: Any, settings: Any, profile: Any, clip: Any) -> Dict[str, Any]:
    audio_path = str(ensure_compatible_audio(scene, clip))
    if clip.audio_offset_sec < 0.0:
        raise ValueError("audio offset must be non-negative")
    end_sec = None
    if clip.duration_sec > 0.0:
        end_sec = clip.audio_offset_sec + clip.duration_sec
    return {
        "protocol_version": WORKER_PROTOCOL_VERSION,
        "audio_path": audio_path,
        "models": _model_payloads(settings, clip),
        "segment_id": f"{clip.clip_id}:segment-0001",
        "start_sec": clip.audio_offset_sec,
        "end_sec": end_sec,
        "requested_language_code": clip.language_code,
        "timeline_config": {
            "attack_ms": clip.attack_ms,
            "release_ms": clip.release_ms,
            "hold_ratio": clip.hold_ratio,
        },
        "profile_id": profile.profile_id,
        "clip_id": clip.clip_id,
        "render_fps": scene.render.fps,
        "render_fps_base": scene.render.fps_base,
    }


def _register_timer() -> None:
    global _TIMER_REGISTERED
    if _TIMER_REGISTERED:
        return
    bpy.app.timers.register(_poll_timer, first_interval=0.15)
    _TIMER_REGISTERED = True


def _unregister_timer() -> None:
    global _TIMER_REGISTERED
    try:
        if _TIMER_REGISTERED and bpy.app.timers.is_registered(_poll_timer):
            bpy.app.timers.unregister(_poll_timer)
    except (AttributeError, RuntimeError):
        pass
    _TIMER_REGISTERED = False


def start_recognition(
    scene: Any,
    profile: Any,
    clip: Any,
    *,
    generate_after_recognition: bool = False,
) -> str:
    """Start one recognition task and arrange main-thread result polling."""

    global _ACTIVE
    if _ACTIVE is not None:
        raise WorkerRuntimeError("another recognition task is already running")
    settings = scene.mmd_mouth
    resolution = resolve_for_settings(settings)
    if not resolution.available:
        _set_worker_state(
            settings,
            status="MISSING",
            display_name="Unavailable",
            error=resolution.reason,
        )
        raise WorkerRuntimeError(resolution.reason)
    if settings.worker_status != "READY":
        if not check_worker(settings):
            raise WorkerRuntimeError(
                settings.worker_last_error or "worker health check failed"
            )
        resolution = resolve_for_settings(settings)

    job = _job_payload(scene, settings, profile, clip)
    cache_directory = _cache_directory(scene, settings)
    task = _manager().start(
        job,
        cache_directory,
        resolution=resolution,
        task_id=uuid.uuid4().hex,
    )
    clip.render_fps = scene.render.fps
    clip.render_fps_base = scene.render.fps_base
    clip.cache_path = str(task.output_path)
    clip.status = "RUNNING"
    clip.last_error = ""
    settings.is_busy = True
    settings.worker_task_id = task.task_id
    settings.worker_status = "RUNNING"
    _ACTIVE = _ActiveRecognition(
        task=task,
        scene_name=scene.name,
        profile_id=profile.profile_id,
        clip_id=clip.clip_id,
        generate_after_recognition=generate_after_recognition,
    )
    _register_timer()
    _tag_redraw()
    return task.task_id


def _copy_candidate(clip: Any, value: Dict[str, Any], output_path: Path) -> None:
    candidate = clip.recognition_candidates.add()
    candidate.candidate_id = str(value.get("candidate_id", ""))
    candidate.segment_id = str(value.get("segment_id", ""))
    candidate.language_code = str(value.get("language_code", ""))
    candidate.model_id = str(value.get("model_id", ""))
    candidate.start_sec = float(value.get("start_sec", 0.0))
    candidate.end_sec = float(value.get("end_sec", candidate.start_sec))
    candidate.raw_score = float(value.get("raw_score", 0.0))
    candidate.normalized_score = float(value.get("normalized_score", 0.0))
    candidate.selection_score = float(value.get("selection_score", 0.0))
    candidate.selected = bool(value.get("selected", False))
    candidate.word_count = len(value.get("words", []))
    candidate.cache_path = str(output_path)


def _copy_language_segment(clip: Any, value: Dict[str, Any]) -> None:
    segment = clip.language_segments.add()
    segment.start_sec = float(value.get("start_sec", 0.0))
    segment.end_sec = float(value.get("end_sec", segment.start_sec))
    segment.language_code = str(value.get("language_code", ""))
    segment.model_id = str(value.get("model_id", ""))
    segment.confidence = float(value.get("confidence", 0.0))
    segment.source = str(value.get("source", "MODEL_SCORE"))
    segment.candidate_id = str(value.get("candidate_id", ""))


def _copy_phoneme(clip: Any, value: Dict[str, Any]) -> None:
    phoneme = clip.phonemes.add()
    phoneme.phoneme = str(value.get("phoneme", ""))
    phoneme.source_phoneme = str(value.get("source_phoneme", ""))
    phoneme.start_sec = float(value.get("start_sec", 0.0))
    phoneme.end_sec = float(value.get("end_sec", phoneme.start_sec))
    phoneme.phoneme_type = str(value.get("phoneme_type", "UNKNOWN"))
    phoneme.place = str(value.get("place", "UNKNOWN"))
    phoneme.manner = str(value.get("manner", "UNKNOWN"))
    phoneme.voicing = str(value.get("voicing", "UNKNOWN"))
    phoneme.articulation_class = str(value.get("articulation_class", ""))
    phoneme.viseme_id = str(value.get("viseme_id", "REST"))
    phoneme.close_strength = float(value.get("close_strength", 0.0))
    phoneme.vowel_suppression = float(value.get("vowel_suppression", 0.0))
    phoneme.confidence = float(value.get("confidence", 0.0))
    phoneme.source_text = str(value.get("source_text", ""))
    phoneme.language_code = str(value.get("language_code", ""))


def _copy_event(clip: Any, value: Dict[str, Any]) -> None:
    event = clip.events.add()
    event.viseme_id = str(value.get("viseme_id", "REST"))
    event.start_sec = float(value.get("start_sec", 0.0))
    event.end_sec = float(value.get("end_sec", event.start_sec))
    event.weight = float(value.get("weight", 1.0))
    event.confidence = float(value.get("confidence", 0.0))
    event.source = str(value.get("source", "G2P"))
    event.source_index = int(value.get("source_index", -1))
    event.source_text = str(value.get("source_text", ""))
    event.phoneme = str(value.get("phoneme", ""))
    event.language_code = str(value.get("language_code", ""))
    event.source_phoneme = str(value.get("source_phoneme", ""))
    event.articulation_class = str(value.get("articulation_class", ""))
    event.priority = int(value.get("priority", 0))


def _import_document(
    scene: Any,
    profile: Any,
    clip: Any,
    payload: Dict[str, Any],
    output_path: Path,
) -> None:
    del scene, profile
    document = payload.get("document")
    if not isinstance(document, dict):
        raise ValueError("worker result does not contain a recognition document")
    document_schema = int(document.get("schema_version", 0))
    if document_schema != SCHEMA_VERSION:
        raise ValueError(
            "worker schema mismatch: "
            f"expected {SCHEMA_VERSION}, got {document_schema}"
        )
    clip.recognition_candidates.clear()
    clip.language_segments.clear()
    clip.phonemes.clear()
    clip.events.clear()
    for value in document.get("candidates", []):
        if isinstance(value, dict):
            _copy_candidate(clip, value, output_path)
    for value in document.get("language_segments", []):
        if isinstance(value, dict):
            _copy_language_segment(clip, value)
    for value in document.get("phonemes", []):
        if isinstance(value, dict):
            _copy_phoneme(clip, value)
    for value in document.get("events", []):
        if isinstance(value, dict):
            _copy_event(clip, value)
    sort_clip_events(clip)
    clip.active_event_index = 0
    words = [
        value.get("text", "")
        for value in document.get("words", [])
        if isinstance(value, dict) and value.get("text")
    ]
    clip.source_transcript = " ".join(str(value) for value in words)
    clip.audio_hash = ""
    clip.selected_candidate_id = str(document.get("selected_candidate_id", ""))
    clip.recognizer_model_id = str(document.get("model_id", ""))
    recognized_language = str(document.get("language_code", clip.language_code))
    valid_languages = {item[0] for item in LANGUAGE_ITEMS}
    if clip.language_code != "AUTO" and recognized_language in valid_languages:
        clip.language_code = recognized_language
    clip.duration_sec = max(
        clip.duration_sec,
        float(document.get("audio_duration_sec", 0.0)),
    )
    clip.event_count = len(clip.events)
    clip.phoneme_count = len(clip.phonemes)
    clip.candidate_scoring_version = int(
        document.get(
            "candidate_scoring_version", clip.candidate_scoring_version
        )
    )
    clip.timeline_version = TIMELINE_VERSION
    clip.ipa_normalization_version = IPA_NORMALIZATION_VERSION
    clip.status = "RECOGNIZED"
    errors = payload.get("errors", [])
    if errors:
        clip.last_error = "; ".join(
            str(value.get("error", ""))
            for value in errors
            if isinstance(value, dict) and value.get("error")
        )
    else:
        clip.last_error = ""


def _finish_active(result: Any) -> None:
    global _ACTIVE, _TIMER_REGISTERED
    active = _ACTIVE
    _ACTIVE = None
    _TIMER_REGISTERED = False
    scene = bpy.data.scenes.get(active.scene_name)
    if scene is None:
        _tag_redraw()
        return
    settings = scene.mmd_mouth
    profile = _find_profile(settings, active.profile_id)
    clip = _find_clip(profile, active.clip_id) if profile is not None else None
    settings.is_busy = False
    settings.worker_task_id = ""
    if result.state == "DONE" and profile is not None and clip is not None:
        try:
            _import_document(
                scene,
                profile,
                clip,
                result.payload or {},
                active.task.output_path,
            )
            settings.worker_status = "READY"
            settings.worker_last_error = ""
        except (TypeError, ValueError, KeyError) as exc:
            clip.status = "ERROR"
            clip.last_error = str(exc)
            settings.worker_status = "ERROR"
            settings.worker_last_error = str(exc)
        else:
            if active.generate_after_recognition:
                from .animation import AnimationError, generate_clip

                try:
                    generate_clip(scene, profile, clip)
                    settings.last_error = ""
                except (AnimationError, RuntimeError, ValueError) as exc:
                    clip.status = "ERROR"
                    clip.last_error = str(exc)
                    settings.last_error = str(exc)
    elif clip is not None:
        clip.status = "ERROR"
        clip.last_error = result.error or "worker job failed"
        settings.worker_status = "ERROR"
        settings.worker_last_error = clip.last_error
    _tag_redraw()


def _poll_timer() -> float | None:
    if _ACTIVE is None:
        return None
    result = _manager().poll(_ACTIVE.task)
    if result.state == "RUNNING":
        return 0.15
    _finish_active(result)
    return None


def cancel_active(scene: Any | None = None) -> bool:
    """Cancel the active worker without deleting existing animation assets."""

    global _ACTIVE, _TIMER_REGISTERED
    if _ACTIVE is None:
        return reconcile_runtime_state(scene)
    active = _ACTIVE
    _manager().cancel(active.task)
    _ACTIVE = None
    _unregister_timer()
    target_scene = scene or bpy.data.scenes.get(active.scene_name)
    if target_scene is not None:
        settings = target_scene.mmd_mouth
        profile = _find_profile(settings, active.profile_id)
        clip = _find_clip(profile, active.clip_id) if profile is not None else None
        settings.is_busy = False
        settings.worker_task_id = ""
        settings.worker_status = "READY"
        settings.worker_last_error = ""
        if clip is not None:
            clip.status = "RECOGNIZED" if clip.recognition_candidates else "DRAFT"
            clip.last_error = ""
    _tag_redraw()
    return True


@persistent
def _history_change_pre(_unused: Any) -> None:
    if _ACTIVE is not None:
        cancel_active()


@persistent
def _history_change_post(_unused: Any) -> None:
    if _ACTIVE is not None:
        cancel_active()
    reconcile_runtime_state()


@persistent
def _load_pre(_unused: Any) -> None:
    shutdown()


@persistent
def _load_post(_unused: Any) -> None:
    reconcile_runtime_state()


def _initial_reconcile_timer() -> float | None:
    global _RECONCILE_TIMER_REGISTERED
    try:
        if len(bpy.data.scenes) == 0:
            return 0.1
        reconcile_runtime_state()
    except AttributeError:
        return 0.1
    _RECONCILE_TIMER_REGISTERED = False
    return None


def _schedule_initial_reconcile() -> None:
    global _RECONCILE_TIMER_REGISTERED
    if _RECONCILE_TIMER_REGISTERED:
        return
    bpy.app.timers.register(_initial_reconcile_timer, first_interval=0.0)
    _RECONCILE_TIMER_REGISTERED = True


def _unregister_initial_reconcile() -> None:
    global _RECONCILE_TIMER_REGISTERED
    if _RECONCILE_TIMER_REGISTERED:
        try:
            if bpy.app.timers.is_registered(_initial_reconcile_timer):
                bpy.app.timers.unregister(_initial_reconcile_timer)
        except (AttributeError, RuntimeError):
            pass
    _RECONCILE_TIMER_REGISTERED = False


def register() -> None:
    handlers = bpy.app.handlers
    for collection, callback in (
        (handlers.undo_pre, _history_change_pre),
        (handlers.undo_post, _history_change_post),
        (handlers.redo_pre, _history_change_pre),
        (handlers.redo_post, _history_change_post),
        (handlers.load_pre, _load_pre),
        (handlers.load_post, _load_post),
    ):
        if callback not in collection:
            collection.append(callback)
    _schedule_initial_reconcile()


def unregister() -> None:
    handlers = bpy.app.handlers
    for collection, callback in (
        (handlers.undo_pre, _history_change_pre),
        (handlers.undo_post, _history_change_post),
        (handlers.redo_pre, _history_change_pre),
        (handlers.redo_post, _history_change_post),
        (handlers.load_pre, _load_pre),
        (handlers.load_post, _load_post),
    ):
        if callback in collection:
            collection.remove(callback)
    shutdown()


def shutdown() -> None:
    """Stop a running worker before the add-on unregisters its RNA classes."""

    global _MANAGER, _ACTIVE, _TIMER_REGISTERED
    if _ACTIVE is not None:
        _manager().cancel(_ACTIVE.task)
        _ACTIVE = None
    _unregister_timer()
    _unregister_initial_reconcile()
    _MANAGER = None


__all__ = [
    "cancel_active",
    "check_worker",
    "is_recognition_active",
    "reconcile_runtime_state",
    "register",
    "resolve_for_settings",
    "shutdown",
    "start_recognition",
    "unregister",
]
