"""Blender-side registration for model archives shipped with the add-on."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import bpy
from bpy.app.handlers import persistent

from .recognition.model_assets import (
    BUNDLED_MODEL_ASSETS,
    BundledModelAsset,
    bundled_asset,
    is_vosk_model_directory,
)


_INITIALIZE_TIMER_REGISTERED = False


def _addon_root() -> Path:
    return Path(__file__).resolve().parent


def model_cache_root() -> Path:
    value = bpy.utils.user_resource(
        "DATAFILES",
        path="mmd_mouth/models",
        create=True,
    )
    root = Path(value) if value else Path(bpy.app.tempdir) / "mmd_mouth" / "models"
    root.mkdir(parents=True, exist_ok=True)
    return root


def archive_path(asset: BundledModelAsset) -> Path:
    candidates = (
        _addon_root() / "resources" / "vosk" / asset.archive_name,
        _addon_root().parent / asset.archive_name,
    )
    return next((path for path in candidates if path.is_file()), candidates[0])


def ensure_settings_models(settings: Any) -> None:
    existing = {model.model_id: model for model in settings.recognizer_models}
    cache_root = model_cache_root()
    for asset in BUNDLED_MODEL_ASSETS:
        model = existing.get(asset.model_id)
        if model is None:
            model = settings.recognizer_models.add()
            model.model_id = asset.model_id
            model.display_name = asset.display_name
            model.language_code = asset.language_code
            model.model_path = str(cache_root / asset.model_id)
            model.enabled = True
            model.priority = 0
        if not model.is_bundled:
            model.is_bundled = True


def bundled_payload(model: Any) -> Dict[str, str]:
    asset = bundled_asset(model.model_id)
    if asset is None:
        return {}
    return {
        "archive_path": str(archive_path(asset)),
        "archive_sha256": asset.archive_sha256,
    }


def model_is_ready(model: Any) -> bool:
    path = Path(bpy.path.abspath(model.model_path)).expanduser()
    return is_vosk_model_directory(path)


@persistent
def _ensure_after_load(_unused: Any) -> None:
    for scene in bpy.data.scenes:
        ensure_settings_models(scene.mmd_mouth)


def _initialize_timer() -> float | None:
    global _INITIALIZE_TIMER_REGISTERED
    try:
        if len(bpy.data.scenes) == 0:
            return 0.1
    except AttributeError:
        return 0.1
    try:
        _ensure_after_load(None)
    except AttributeError:
        return 0.1
    _INITIALIZE_TIMER_REGISTERED = False
    return None


def _schedule_initialization() -> None:
    global _INITIALIZE_TIMER_REGISTERED
    if _INITIALIZE_TIMER_REGISTERED:
        return
    bpy.app.timers.register(_initialize_timer, first_interval=0.0)
    _INITIALIZE_TIMER_REGISTERED = True


def register() -> None:
    if _ensure_after_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_ensure_after_load)
    if hasattr(bpy.data, "scenes") and len(bpy.data.scenes) > 0:
        _ensure_after_load(None)
    _schedule_initialization()


def unregister() -> None:
    global _INITIALIZE_TIMER_REGISTERED
    if _ensure_after_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_ensure_after_load)
    if _INITIALIZE_TIMER_REGISTERED:
        try:
            if bpy.app.timers.is_registered(_initialize_timer):
                bpy.app.timers.unregister(_initialize_timer)
        except (AttributeError, RuntimeError):
            pass
    _INITIALIZE_TIMER_REGISTERED = False


__all__ = [
    "archive_path",
    "bundled_payload",
    "ensure_settings_models",
    "model_cache_root",
    "model_is_ready",
    "register",
    "unregister",
]
