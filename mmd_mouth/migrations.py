"""Small, explicit migrations for persisted Blender RNA state."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import bpy
from bpy.app.handlers import persistent

from .constants import SCHEMA_VERSION, TIMELINE_VERSION


_INITIALIZE_TIMER_REGISTERED = False


def migrate_settings(settings: Any) -> None:
    for profile in settings.model_profiles:
        if not profile.profile_id:
            profile.profile_id = uuid4().hex
        for clip in profile.clips:
            if not clip.clip_id:
                clip.clip_id = uuid4().hex
            if clip.timeline_version < TIMELINE_VERSION:
                if clip.events or clip.phonemes or clip.recognition_candidates:
                    clip.status = "STALE"
                else:
                    clip.timeline_version = TIMELINE_VERSION
    settings.schema_version = SCHEMA_VERSION


@persistent
def _migrate_after_load(_unused: Any) -> None:
    for scene in bpy.data.scenes:
        migrate_settings(scene.mmd_mouth)


def _initialize_timer() -> float | None:
    global _INITIALIZE_TIMER_REGISTERED
    try:
        _migrate_after_load(None)
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
    if _migrate_after_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_migrate_after_load)
    if hasattr(bpy.data, "scenes"):
        _migrate_after_load(None)
    else:
        _schedule_initialization()


def unregister() -> None:
    global _INITIALIZE_TIMER_REGISTERED
    if _migrate_after_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_migrate_after_load)
    if _INITIALIZE_TIMER_REGISTERED:
        try:
            if bpy.app.timers.is_registered(_initialize_timer):
                bpy.app.timers.unregister(_initialize_timer)
        except (AttributeError, RuntimeError):
            pass
    _INITIALIZE_TIMER_REGISTERED = False


__all__ = ["migrate_settings", "register", "unregister"]
