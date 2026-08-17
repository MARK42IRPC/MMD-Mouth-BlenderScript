"""Blender 5.2 regression for undo during asynchronous recognition."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("MMD_MOUTH_TEST_PACKAGE", ROOT)).resolve()
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import mmd_mouth  # noqa: E402
from mmd_mouth import blender_runtime  # noqa: E402


AUDIO = ROOT / "zh_vo_MAIN_YHX_2_7.wav"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def current_clip(scene):
    settings = scene.mmd_mouth
    profile = settings.model_profiles[settings.active_model_index]
    return profile, profile.clips[profile.active_clip_index]


def main() -> None:
    require(AUDIO.is_file(), f"test WAV is missing: {AUDIO}")
    mmd_mouth.register()
    scene = bpy.context.scene
    bpy.ops.mmd_mouth.add_model()
    bpy.ops.mmd_mouth.add_clip()
    _profile, clip = current_clip(scene)
    clip.audio_path = str(AUDIO)
    clip.language_code = "zh-CN"

    bpy.ops.ed.undo_push(message="MMD Mouth configured")
    require(
        "FINISHED" in bpy.ops.mmd_mouth.recognize(),
        "recognition did not start",
    )
    require(blender_runtime._ACTIVE is not None, "worker task was not recorded")
    require(scene.mmd_mouth.is_busy, "scene did not enter busy state")
    bpy.ops.ed.undo_push(message="MMD Mouth running")

    require("FINISHED" in bpy.ops.ed.undo(), "Blender undo failed")
    scene = bpy.context.scene
    settings = scene.mmd_mouth
    profile, clip = current_clip(scene)
    require(blender_runtime._ACTIVE is None, "undo left the worker task active")
    require(not settings.is_busy, "undo left the scene busy")
    require(not settings.worker_task_id, "undo left a worker task ID")
    require(settings.worker_status != "RUNNING", "undo left worker status running")
    require(clip.status != "RUNNING", "undo left clip status running")
    require(
        "FINISHED" in bpy.ops.mmd_mouth.remove_clip(),
        "clip could not be deleted after undo",
    )
    require(len(profile.clips) == 0, "clip survived deletion after undo")

    bpy.ops.mmd_mouth.add_clip()
    profile, clip = current_clip(scene)
    settings.is_busy = True
    settings.worker_status = "RUNNING"
    settings.worker_task_id = "orphaned-task"
    clip.status = "RUNNING"
    require(
        blender_runtime.reconcile_runtime_state(scene),
        "orphaned runtime state was not detected",
    )
    require(not settings.is_busy, "orphaned busy flag survived reconciliation")
    require(clip.status == "DRAFT", "orphaned clip did not return to draft")
    require(
        "FINISHED" in bpy.ops.mmd_mouth.remove_clip(),
        "reconciled clip could not be deleted",
    )

    print(f"MMD_UNDO_RUNTIME_OK addon={Path(mmd_mouth.__file__).resolve()}", flush=True)


try:
    main()
finally:
    blender_runtime.cancel_active()
