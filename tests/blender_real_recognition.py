"""Headless Blender smoke test for one real Vosk recognition job."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import bpy


ROOT = Path(__file__).resolve().parents[1]
AUDIO = ROOT / "zh_vo_MAIN_YHX_2_7.wav"
MODEL = ROOT / "models" / "vosk-model-small-cn-0.22"
OUTPUT = ROOT / "cache" / "real" / "blender-rna-cn.json"
PACKAGE_ROOT = Path(os.environ.get("MMD_MOUTH_TEST_PACKAGE", ROOT))

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import mmd_mouth  # noqa: E402
from mmd_mouth import blender_runtime  # noqa: E402


def fail(message: str) -> None:
    print(f"MMD_REAL_TEST_ERROR: {message}", flush=True)
    bpy.ops.wm.quit_blender()


def finish() -> float | None:
    if blender_runtime._ACTIVE is not None:
        return 0.2

    scene = bpy.context.scene
    settings = scene.mmd_mouth
    profile = settings.model_profiles[0]
    clip = profile.clips[0]
    payload = {
        "worker_status": settings.worker_status,
        "clip_status": clip.status,
        "source_transcript": clip.source_transcript,
        "candidate_count": len(clip.recognition_candidates),
        "language_segment_count": len(clip.language_segments),
        "selected_candidate_id": clip.selected_candidate_id,
        "recognizer_model_id": clip.recognizer_model_id,
        "duration_sec": clip.duration_sec,
        "last_error": clip.last_error,
        "candidates": [
            {
                "model_id": candidate.model_id,
                "language_code": candidate.language_code,
                "selection_score": candidate.selection_score,
                "selected": candidate.selected,
                "word_count": candidate.word_count,
            }
            for candidate in clip.recognition_candidates
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False), flush=True)
    bpy.ops.wm.quit_blender()
    return None


def main() -> None:
    mmd_mouth.register()
    scene = bpy.context.scene
    settings = scene.mmd_mouth

    bpy.ops.mmd_mouth.add_model()
    profile = settings.model_profiles[0]
    bpy.ops.mmd_mouth.add_clip()
    clip = profile.clips[0]
    clip.audio_path = str(AUDIO)
    clip.duration_sec = 0.0

    bpy.ops.mmd_mouth.add_recognizer_model()
    model = settings.recognizer_models[0]
    model.model_id = "vosk-model-small-cn-0.22"
    model.display_name = "Chinese small"
    model.language_code = "zh-CN"
    model.model_path = str(MODEL)
    model.enabled = True

    if not bpy.ops.mmd_mouth.check_worker.poll():
        fail("worker check operator is unavailable")
        return
    result = bpy.ops.mmd_mouth.check_worker()
    if "FINISHED" not in result:
        fail(settings.worker_last_error or "worker health check failed")
        return
    result = bpy.ops.mmd_mouth.recognize()
    if "FINISHED" not in result:
        fail(settings.worker_last_error or "recognition operator failed")
        return
    while blender_runtime._ACTIVE is not None:
        interval = blender_runtime._poll_timer()
        if interval is None:
            break
        time.sleep(min(0.2, max(0.05, interval)))
    finish()


main()
