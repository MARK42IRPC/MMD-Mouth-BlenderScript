"""Blender regression for profile-level editable shape-key keyframes."""

from __future__ import annotations

from pathlib import Path
import sys

import bpy


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mmd_mouth  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def create_face() -> tuple[bpy.types.Object, bpy.types.Object]:
    root = bpy.data.objects.new("All Keyframes Root", None)
    bpy.context.scene.collection.objects.link(root)
    mesh = bpy.data.meshes.new("All Keyframes Mesh")
    mesh.from_pydata(
        [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
        [],
        [(0, 1, 2)],
    )
    face = bpy.data.objects.new("All Keyframes Face", mesh)
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


def curve_for(action, key_block):
    data_path = key_block.path_from_id("value")
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                for fcurve in channelbag.fcurves:
                    if fcurve.data_path == data_path:
                        return fcurve
    return None


def main() -> None:
    mmd_mouth.register()
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    root, face = create_face()

    require("FINISHED" in bpy.ops.mmd_mouth.add_model(), "model setup failed")
    profile = scene.mmd_mouth.model_profiles[0]
    profile.root_object = root
    require("FINISHED" in bpy.ops.mmd_mouth.add_clip(), "first clip setup failed")
    first = profile.clips[0]
    first.start_frame = 1
    first.duration_sec = 1.5
    first.easing_mode = "LINEAR"
    add_event(first, "A", 0.1, 0.9)

    require("FINISHED" in bpy.ops.mmd_mouth.add_clip(), "second clip setup failed")
    second = profile.clips[1]
    second.start_frame = 50
    second.duration_sec = 1.2
    second.easing_mode = "LINEAR"
    add_event(second, "O", 0.1, 0.8)
    first.generation_mode = "DRIVER"

    require("FINISHED" in bpy.ops.mmd_mouth.scan_bindings(), "scan failed")
    require(
        "FINISHED" in bpy.ops.mmd_mouth.bake_all_keyframes(),
        "all-keyframe bake failed",
    )
    require(len(profile.keyframe_assets) == 1, "profile Action was not recorded")
    shape_keys = face.data.shape_keys
    action = shape_keys.animation_data.action
    require(action is not None, "shape-key Action is not active")
    require(not shape_keys.animation_data.nla_tracks, "NLA tracks were left behind")
    require(
        action.name == profile.keyframe_assets[0].action_name,
        "recorded Action does not own the active shape-key animation",
    )
    a_curve = curve_for(action, shape_keys.key_blocks["あ"])
    require(a_curve is not None, "A keyframe curve is missing")
    require(len(a_curve.keyframe_points) < 30, "curve was baked frame-by-frame")

    scene.frame_set(15)
    require(shape_keys.key_blocks["あ"].value > 0.9, "first clip keyframes are inactive")
    scene.frame_set(65)
    require(shape_keys.key_blocks["お"].value > 0.9, "second clip keyframes are inactive")

    old_action_pointer = action.as_pointer()
    second.events[0].viseme_id = "E"
    require(second.status == "STALE", "timeline edit did not mark clip stale")
    require(
        "FINISHED" in bpy.ops.mmd_mouth.bake_all_keyframes(),
        "all-keyframe regeneration failed",
    )
    new_action = shape_keys.animation_data.action
    require(
        new_action is not None and new_action.as_pointer() != old_action_pointer,
        "regeneration reused the old Action datablock",
    )
    require(len(bpy.data.actions) == 1, "old Action survived regeneration")
    scene.frame_set(65)
    require(shape_keys.key_blocks["え"].value > 0.9, "regenerated E keyframes are inactive")
    require(shape_keys.key_blocks["お"].value < 0.1, "old O keyframes survived regeneration")
    print("MMD_BAKE_ALL_KEYFRAMES_OK", flush=True)


main()
