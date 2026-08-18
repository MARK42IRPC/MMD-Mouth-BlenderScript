"""Blender 5.2 end-to-end test for bundled recognition and mouth baking."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time

import bpy


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("MMD_MOUTH_TEST_PACKAGE", ROOT)).resolve()
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import mmd_mouth  # noqa: E402
from mmd_mouth import blender_runtime  # noqa: E402
from mmd_mouth.recognition.model_assets import (  # noqa: E402
    is_vosk_model_directory,
)


AUDIO = Path(
    os.environ.get("MMD_MOUTH_TEST_AUDIO", str(ROOT / "zh_vo_MAIN_YHX_2_7.wav"))
).resolve()
CACHE = ROOT / "cache" / "blender-generate-e2e"
OUTPUT = CACHE / "result.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def create_face() -> tuple[bpy.types.Object, bpy.types.Object]:
    root = bpy.data.objects.new("E2E MMD Root", None)
    bpy.context.scene.collection.objects.link(root)
    mesh = bpy.data.meshes.new("E2E Face Mesh")
    mesh.from_pydata(
        [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
        [],
        [(0, 1, 2)],
    )
    face = bpy.data.objects.new("E2E Face", mesh)
    bpy.context.scene.collection.objects.link(face)
    face.parent = root
    face.shape_key_add(name="Basis")
    for name in ("あ", "い", "う", "え", "お", "口閉じ"):
        face.shape_key_add(name=name)
    return root, face


def wait_for_worker(timeout_sec: float = 180.0) -> None:
    deadline = time.monotonic() + timeout_sec
    while blender_runtime._ACTIVE is not None and time.monotonic() < deadline:
        interval = blender_runtime._poll_timer()
        if interval is None:
            break
        time.sleep(min(0.2, max(0.05, interval)))
    require(blender_runtime._ACTIVE is None, "worker did not finish before timeout")


def main() -> None:
    mmd_mouth.register()
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    settings = scene.mmd_mouth
    root, face = create_face()

    cn_model = next(
        model
        for model in settings.recognizer_models
        if model.model_id == "vosk-model-small-cn-0.22"
    )
    cn_model.model_path = str(
        CACHE / "models" / PACKAGE_ROOT.name / cn_model.model_id
    )

    bpy.ops.mmd_mouth.add_model()
    profile = settings.model_profiles[0]
    profile.root_object = root
    profile.display_name = "E2E Model"
    bpy.ops.mmd_mouth.add_clip()
    clip = profile.clips[0]
    clip.display_name = "E2E Speech"
    clip.audio_path = str(AUDIO)
    clip.start_frame = 20
    clip.language_code = "zh-CN"
    clip.generation_mode = "BAKE"

    require("FINISHED" in bpy.ops.mmd_mouth.generate(), "generate did not start")
    require(settings.is_busy, "recognition was not started asynchronously")
    wait_for_worker()

    require(settings.worker_status == "READY", settings.worker_last_error)
    require(clip.status == "BAKED", clip.last_error)
    require(clip.source_transcript, "transcript is empty")
    require(len(clip.phonemes) > 0, "phonemes were not imported into RNA")
    require(len(clip.events) > 0, "viseme events were not imported into RNA")
    require(len(clip.assets) == 1, "baked NLA asset was not recorded")
    require(len(profile.bindings) == 5, "mouth output did not stay on five vowels")
    require(is_vosk_model_directory(Path(cn_model.model_path)), "model ZIP was not extracted")

    closed = next(event for event in clip.events if event.viseme_id == "CLOSED")
    midpoint = (closed.start_sec + closed.end_sec) * 0.5
    local_sec = max(0.0, midpoint - clip.audio_offset_sec)
    scene.frame_set(clip.start_frame + round(local_sec * 30.0))
    keys = face.data.shape_keys.key_blocks
    require(
        max(keys[name].value for name in ("あ", "い", "う", "え", "お")) < 0.5,
        "closed-mouth event did not suppress vowel morphs",
    )

    payload = {
        "worker": settings.worker_display_name,
        "addon_file": str(Path(mmd_mouth.__file__).resolve()),
        "status": clip.status,
        "transcript": clip.source_transcript,
        "phonemes": len(clip.phonemes),
        "events": len(clip.events),
        "closed_events": sum(event.viseme_id == "CLOSED" for event in clip.events),
        "bindings": len(profile.bindings),
        "assets": len(clip.assets),
        "action": clip.assets[0].action_name,
        "model_path": cn_model.model_path,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"MMD_GENERATE_E2E_OK {json.dumps(payload, ensure_ascii=False)}", flush=True)


main()
