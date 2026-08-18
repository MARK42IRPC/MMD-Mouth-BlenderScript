"""Blender 5.2 smoke test for binding, bake, NLA, and driver output."""

from __future__ import annotations

from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mmd_mouth  # noqa: E402
from mmd_mouth.constants import TIMELINE_VERSION  # noqa: E402
from mmd_mouth.migrations import migrate_settings  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def create_face() -> tuple[bpy.types.Object, bpy.types.Object]:
    root = bpy.data.objects.new("MMD Root", None)
    bpy.context.scene.collection.objects.link(root)

    mesh = bpy.data.meshes.new("Face Mesh")
    mesh.from_pydata(
        [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
        [],
        [(0, 1, 2)],
    )
    face = bpy.data.objects.new("Face", mesh)
    bpy.context.scene.collection.objects.link(face)
    face.parent = root
    face.shape_key_add(name="Basis")
    for name in ("あ", "い", "う", "え", "お", "口閉じ"):
        face.shape_key_add(name=name)
    return root, face


def add_event(clip, viseme_id: str, start_sec: float, end_sec: float) -> None:
    event = clip.events.add()
    event.viseme_id = viseme_id
    event.start_sec = start_sec
    event.end_sec = end_sec
    event.weight = 1.0
    event.confidence = 1.0


def driver_for(key_block):
    shape_keys = key_block.id_data
    return shape_keys.animation_data.drivers.find(
        key_block.path_from_id("value"),
        index=-1,
    )


def main() -> None:
    mmd_mouth.register()
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    root, face = create_face()

    bpy.ops.mmd_mouth.add_model()
    profile = scene.mmd_mouth.model_profiles[0]
    profile.display_name = "Smoke Model"
    profile.root_object = root
    bpy.ops.mmd_mouth.add_clip()
    clip = profile.clips[0]
    clip.display_name = "Smoke Clip"
    clip.start_frame = 12
    clip.duration_sec = 1.0
    add_event(clip, "A", 0.1, 0.8)
    add_event(clip, "CLOSED", 0.45, 0.65)

    require(
        "FINISHED" in bpy.ops.mmd_mouth.scan_bindings(),
        "scan operator failed",
    )
    require(len(profile.bindings) == 5, "expected five vowel bindings")
    require(profile.binding_status == "VALID", "binding scan was not valid")

    clip.generation_mode = "BAKE"
    require("FINISHED" in bpy.ops.mmd_mouth.generate(), "bake operator failed")
    require(len(clip.assets) == 1, "bake did not record one NLA asset")
    bake_action_name = clip.assets[0].action_name
    require(bpy.data.actions.get(bake_action_name) is not None, "bake action missing")
    scene.frame_set(20)
    require(face.data.shape_keys.key_blocks["あ"].value > 0.9, "A did not open")
    scene.frame_set(28)
    require(
        face.data.shape_keys.key_blocks["あ"].value < 0.1,
        "closure did not suppress A",
    )

    clip.generation_mode = "DRIVER"
    require("FINISHED" in bpy.ops.mmd_mouth.generate(), "driver operator failed")
    require(bpy.data.actions.get(bake_action_name) is None, "old bake action survived")
    controller = clip.assets[0].controller_object
    require(controller is not None, "driver controller was not recorded")
    controller_name = controller.name
    require(
        driver_for(face.data.shape_keys.key_blocks["あ"]) is not None,
        "A driver is missing",
    )
    scene.frame_set(20)
    require(controller["mmd_mouth_A"] > 0.9, "controller A curve is inactive")
    require(face.data.shape_keys.key_blocks["あ"].value > 0.9, "A driver is inactive")

    require(
        "FINISHED" in bpy.ops.mmd_mouth.clear_generated(),
        "clear operator failed",
    )
    require(len(clip.assets) == 0, "asset records were not cleared")
    require(bpy.data.objects.get(controller_name) is None, "controller was not removed")
    require(
        driver_for(face.data.shape_keys.key_blocks["あ"]) is None,
        "owned driver was not removed",
    )

    unrelated = bpy.data.objects.new("Unrelated Driver", None)
    scene.collection.objects.link(unrelated)
    unrelated["value"] = 0.0
    key = face.data.shape_keys.key_blocks["あ"]
    fcurve = face.data.shape_keys.driver_add(key.path_from_id("value"))
    variable = fcurve.driver.variables.new()
    variable.name = "v"
    variable.targets[0].id = unrelated
    variable.targets[0].data_path = '["value"]'
    try:
        result = bpy.ops.mmd_mouth.generate()
    except RuntimeError:
        result = {"CANCELLED"}
    require("CANCELLED" in result, "unrelated shape-key driver was overwritten")
    require(driver_for(key) == fcurve, "unrelated driver was removed")

    clip.timeline_version = TIMELINE_VERSION - 1
    clip.status = "RECOGNIZED"
    migrate_settings(scene.mmd_mouth)
    require(clip.status == "STALE", "old timeline was not marked stale")

    print("MMD_ANIMATION_SMOKE_OK", flush=True)


main()
