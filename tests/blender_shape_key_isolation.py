"""Blender regression for strict mouth shape-key ownership boundaries."""

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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def curve_for(action, key_block):
    data_path = key_block.path_from_id("value")
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                for fcurve in channelbag.fcurves:
                    if fcurve.data_path == data_path:
                        return fcurve
    return None


def create_face():
    root = bpy.data.objects.new("Isolation Root", None)
    bpy.context.scene.collection.objects.link(root)
    mesh = bpy.data.meshes.new("Isolation Mesh")
    mesh.from_pydata(
        [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
        [],
        [(0, 1, 2)],
    )
    face = bpy.data.objects.new("Isolation Face", mesh)
    bpy.context.scene.collection.objects.link(face)
    face.parent = root
    face.shape_key_add(name="Basis")
    for name in ("あ", "い", "う", "え", "お", "口閉じ", "blink"):
        face.shape_key_add(name=name)
    return root, face


def add_unrelated_action(face):
    shape_keys = face.data.shape_keys
    action = bpy.data.actions.new("Unrelated Morph Action")
    shape_keys.animation_data_create().action = action
    curve = action.fcurve_ensure_for_datablock(
        shape_keys,
        shape_keys.key_blocks["blink"].path_from_id("value"),
        group_name="Unrelated",
    )
    curve.keyframe_points.add(2)
    curve.keyframe_points[0].co = (0.0, 0.65)
    curve.keyframe_points[1].co = (100.0, 0.65)
    curve.update()
    return action


def add_event(clip, viseme_id):
    event = clip.events.add()
    event.viseme_id = viseme_id
    event.start_sec = 0.1
    event.end_sec = 0.9
    event.weight = 1.0


def main() -> None:
    mmd_mouth.register()
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    root, face = create_face()
    base_action = add_unrelated_action(face)
    shape_keys = face.data.shape_keys
    blink = shape_keys.key_blocks["blink"]

    require("FINISHED" in bpy.ops.mmd_mouth.add_model(), "model setup failed")
    profile = scene.mmd_mouth.model_profiles[0]
    profile.root_object = root
    require("FINISHED" in bpy.ops.mmd_mouth.add_clip(), "clip setup failed")
    clip = profile.clips[0]
    clip.start_frame = 10
    clip.duration_sec = 1.0
    add_event(clip, "A")
    require("FINISHED" in bpy.ops.mmd_mouth.scan_bindings(), "scan failed")
    require(len(profile.bindings) == 5, "scan bound a non-vowel shape key")

    require(
        "FINISHED" in bpy.ops.mmd_mouth.bake_all_keyframes(),
        "all-keyframe bake failed",
    )
    require(
        shape_keys.animation_data.action == base_action,
        "all-keyframe bake replaced the unrelated active Action",
    )
    generated_action = bpy.data.actions[profile.keyframe_assets[0].action_name]
    require(curve_for(generated_action, blink) is None, "mouth Action owns blink")
    require(
        curve_for(generated_action, shape_keys.key_blocks["口閉じ"]) is None,
        "mouth Action owns the CLOSED morph",
    )
    require(curve_for(base_action, blink) is not None, "blink curve was removed")
    scene.frame_set(15)
    require(blink.value > 0.6, "blink was changed by all-keyframe bake")

    require("FINISHED" in bpy.ops.mmd_mouth.clear_generated(), "clear failed")
    require(shape_keys.animation_data.action == base_action, "clear changed base Action")
    scene.frame_set(15)
    require(blink.value > 0.6, "blink was changed during clear")

    clip.generation_mode = "DRIVER"
    require("FINISHED" in bpy.ops.mmd_mouth.generate(), "driver generation failed")
    require(curve_for(base_action, blink) is not None, "driver removed blink curve")
    require(
        shape_keys.key_blocks["blink"].id_data.animation_data.drivers.find(
            blink.path_from_id("value"),
            index=-1,
        )
        is None,
        "driver generation added a blink driver",
    )
    require("FINISHED" in bpy.ops.mmd_mouth.clear_generated(), "driver clear failed")
    require(shape_keys.animation_data.action == base_action, "driver clear changed base Action")

    clip.generation_mode = "BAKE"
    require("FINISHED" in bpy.ops.mmd_mouth.generate(), "bake generation failed")
    require(shape_keys.animation_data.action == base_action, "bake replaced base Action")
    scene.frame_set(15)
    require(blink.value > 0.6, "blink was changed by bake generation")

    print("MMD_SHAPE_KEY_ISOLATION_OK", flush=True)


main()
