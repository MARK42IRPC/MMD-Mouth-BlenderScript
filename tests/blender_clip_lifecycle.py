"""Blender 5.2 regression for clip preview, strength, regeneration, and deletion."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import warnings

import bpy


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = Path(os.environ.get("MMD_MOUTH_TEST_PACKAGE", ROOT)).resolve()
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

import mmd_mouth  # noqa: E402
from mmd_mouth.audio import CLIP_ID_KEY  # noqa: E402


AUDIO = ROOT / "zh_vo_MAIN_YHX_2_7.wav"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def create_face() -> tuple[bpy.types.Object, bpy.types.Object]:
    root = bpy.data.objects.new("Lifecycle MMD Root", None)
    bpy.context.scene.collection.objects.link(root)
    mesh = bpy.data.meshes.new("Lifecycle Face Mesh")
    mesh.from_pydata(
        [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
        [],
        [(0, 1, 2)],
    )
    face = bpy.data.objects.new("Lifecycle Face", mesh)
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


def owned_audio_strips(scene, clip_id: str) -> list:
    editor = scene.sequence_editor
    if editor is None:
        return []
    return [
        strip
        for strip in editor.strips
        if str(strip.get(CLIP_ID_KEY, "")) == clip_id
    ]


def driver_for(key_block):
    shape_keys = key_block.id_data
    animation_data = shape_keys.animation_data
    if animation_data is None:
        return None
    return animation_data.drivers.find(
        key_block.path_from_id("value"),
        index=-1,
    )


def recorded_strip(clip):
    asset = clip.assets[0]
    owner = asset.owner_object
    datablock = owner.data.shape_keys if owner.type == "MESH" else owner
    for track in datablock.animation_data.nla_tracks:
        for strip in track.strips:
            if strip.name == asset.strip_name:
                return strip
    return None


def main() -> None:
    require(AUDIO.is_file(), f"test WAV is missing: {AUDIO}")
    mmd_mouth.register()
    scene = bpy.context.scene
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    root, face = create_face()

    bpy.ops.mmd_mouth.add_model()
    profile = scene.mmd_mouth.model_profiles[0]
    profile.root_object = root
    bpy.ops.mmd_mouth.add_clip()
    clip = profile.clips[0]
    clip.audio_path = str(AUDIO)
    clip.start_frame = 18
    clip.audio_offset_sec = 0.25
    clip.duration_sec = 1.0
    clip.audio_volume = 0.35

    audio_strips = owned_audio_strips(scene, clip.clip_id)
    require(len(audio_strips) == 1, "selecting audio did not create one owned strip")
    audio_strip = audio_strips[0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        require(audio_strip.frame_final_start == 18, "audio start frame was not synced")
        require(audio_strip.frame_final_duration == 30, "audio duration was not synced")
    require(abs(audio_strip.volume - 0.35) < 1e-6, "preview volume was not synced")

    add_event(clip, "A", 0.35, 1.05)
    add_event(clip, "CLOSED", 0.65, 0.8)
    require(
        "FINISHED" in bpy.ops.mmd_mouth.scan_bindings(),
        "binding scan failed",
    )

    clip.generation_mode = "BAKE"
    clip.mouth_strength = 0.4
    require("FINISHED" in bpy.ops.mmd_mouth.generate(), "strength bake failed")
    first_action = clip.assets[0].action_name
    first_action_pointer = bpy.data.actions[first_action].as_pointer()
    scene.frame_set(24)
    a_key = face.data.shape_keys.key_blocks["あ"]
    require(0.35 < a_key.value < 0.45, "bake did not apply mouth strength")

    clip.mouth_strength = 0.65
    require(
        "FINISHED" in bpy.ops.mmd_mouth.regenerate(),
        "regenerate operator failed",
    )
    regenerated_action = bpy.data.actions[clip.assets[0].action_name]
    require(
        regenerated_action.as_pointer() != first_action_pointer,
        "regeneration reused the old Action datablock",
    )
    require(
        sum(clip.clip_id[:8] in action.name for action in bpy.data.actions) == 1,
        "regeneration left more than one clip Action",
    )
    scene.frame_set(24)
    require(0.6 < a_key.value < 0.7, "regeneration did not update strength")

    clip.start_frame = 30
    audio_strip = owned_audio_strips(scene, clip.clip_id)[0]
    nla_strip = recorded_strip(clip)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        require(audio_strip.frame_final_start == 30, "audio strip did not move")
    require(nla_strip is not None, "generated NLA strip is missing")
    require(abs(nla_strip.frame_start - 30.0) < 1e-6, "NLA strip did not move")

    clip.generation_mode = "DRIVER"
    clip.mouth_strength = 0.3
    require(
        "FINISHED" in bpy.ops.mmd_mouth.regenerate(),
        "driver regeneration failed",
    )
    controller = clip.assets[0].controller_object
    require(controller is not None, "driver controller is missing")
    controller_name = controller.name
    scene.frame_set(36)
    require(
        0.25 < controller["mmd_mouth_A"] < 0.35,
        "driver output did not apply mouth strength",
    )
    require(driver_for(a_key) is not None, "owned shape-key driver is missing")

    view = bpy.context.preferences.view
    view.language = "zh_HANS"
    view.use_translate_interface = True
    require(
        bpy.app.translations.pgettext_iface("Delete Clip") == "删除片段",
        "Simplified Chinese UI translation was not registered",
    )
    require(
        bpy.app.translations.pgettext_iface("Mouth Blend") == "口型混合",
        "easing control translation was not registered",
    )
    require(
        bpy.app.translations.pgettext_iface("Smoothstep") == "平滑步进",
        "easing mode translation was not registered",
    )
    require(
        bpy.app.translations.pgettext_iface("Bake All Keyframes") == "烘焙所有关键帧",
        "all-keyframe bake translation was not registered",
    )

    clip_id = clip.clip_id
    require("FINISHED" in bpy.ops.mmd_mouth.remove_clip(), "clip deletion failed")
    require(len(profile.clips) == 0, "clip record survived deletion")
    require(not owned_audio_strips(scene, clip_id), "owned audio strip survived deletion")
    require(bpy.data.objects.get(controller_name) is None, "controller survived deletion")
    require(driver_for(a_key) is None, "owned driver survived deletion")

    print(f"MMD_CLIP_LIFECYCLE_OK addon={Path(mmd_mouth.__file__).resolve()}", flush=True)


main()
