"""Blender regression for regenerating from an edited timeline."""

from __future__ import annotations

from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mmd_mouth  # noqa: E402
from mmd_mouth import operators  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def create_face() -> tuple[bpy.types.Object, bpy.types.Object]:
    root = bpy.data.objects.new("Timeline Root", None)
    bpy.context.scene.collection.objects.link(root)
    mesh = bpy.data.meshes.new("Timeline Face Mesh")
    mesh.from_pydata(
        [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
        [],
        [(0, 1, 2)],
    )
    face = bpy.data.objects.new("Timeline Face", mesh)
    bpy.context.scene.collection.objects.link(face)
    face.parent = root
    face.shape_key_add(name="Basis")
    for name in ("あ", "い", "う", "え", "お", "口閉じ"):
        face.shape_key_add(name=name)
    return root, face


def main() -> None:
    mmd_mouth.register()
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    root, face = create_face()

    require("FINISHED" in bpy.ops.mmd_mouth.add_model(), "model setup failed")
    settings = scene.mmd_mouth
    profile = settings.model_profiles[0]
    profile.root_object = root
    require("FINISHED" in bpy.ops.mmd_mouth.add_clip(), "clip setup failed")
    clip = profile.clips[0]
    clip.generation_mode = "BAKE"
    clip.duration_sec = 1.4
    clip.easing_mode = "LINEAR"
    clip.attack_ms = 0.0
    clip.release_ms = 0.0

    event = clip.events.add()
    event.viseme_id = "A"
    event.start_sec = 0.1
    event.end_sec = 0.3
    event.weight = 1.0
    require("FINISHED" in bpy.ops.mmd_mouth.scan_bindings(), "scan failed")
    require("FINISHED" in bpy.ops.mmd_mouth.generate(), "initial generate failed")

    event.viseme_id = "O"
    event.start_sec = 0.8
    event.end_sec = 1.0
    require(clip.status == "STALE", "timeline edit did not mark clip stale")

    def forbidden_recognition(*_args, **_kwargs):
        raise AssertionError("Regenerate unexpectedly started recognition")

    operators.start_recognition = forbidden_recognition
    require(
        "FINISHED" in bpy.ops.mmd_mouth.regenerate(),
        "regenerate did not use the edited timeline",
    )
    keys = face.data.shape_keys.key_blocks
    scene.frame_set(6)
    require(keys["あ"].value < 0.1, "old A timeline position remained active")
    require(keys["お"].value < 0.1, "new O timeline started too early")
    scene.frame_set(27)
    require(keys["お"].value > 0.9, "edited O timeline was not generated")
    require(keys["あ"].value < 0.1, "old A viseme survived regeneration")
    print("MMD_TIMELINE_REGENERATE_OK", flush=True)


main()
