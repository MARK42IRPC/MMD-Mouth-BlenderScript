"""MMD morph discovery and Blender 5.2 animation generation."""

from __future__ import annotations

from collections import defaultdict
from math import ceil
import re
from typing import Any, Iterable, Sequence
from uuid import uuid4

import bpy

from .constants import SCHEMA_VERSION
from .core.schema import VisemeEvent
from .core.timeline import VOWEL_CHANNELS, sample_viseme_channels


class AnimationError(RuntimeError):
    """Raised when the selected model cannot receive generated animation."""


MMD_MORPH_ALIASES = {
    "A": ("あ", "a"),
    "I": ("い", "i"),
    "U": ("う", "u"),
    "E": ("え", "e"),
    "O": ("お", "o"),
    "CLOSED": ("口閉じ", "close", "closed"),
}


def _objects_below(root: Any) -> Iterable[Any]:
    stack = [root]
    seen = set()
    while stack:
        current = stack.pop()
        pointer = current.as_pointer()
        if pointer in seen:
            continue
        seen.add(pointer)
        yield current
        stack.extend(reversed(list(current.children)))


def _shape_key_matches(obj: Any) -> dict[str, str]:
    if obj.type != "MESH" or obj.data.shape_keys is None:
        return {}
    key_blocks = obj.data.shape_keys.key_blocks
    lowered = {key.name.strip().casefold(): key.name for key in key_blocks}
    matches = {}
    for channel, aliases in MMD_MORPH_ALIASES.items():
        name = next(
            (lowered[alias.casefold()] for alias in aliases if alias.casefold() in lowered),
            "",
        )
        if name:
            matches[channel] = name
    return matches


def scan_mmd_bindings(profile: Any) -> int:
    root = profile.root_object
    if root is None:
        profile.binding_status = "ERROR"
        raise AnimationError("select an MMD model root before scanning mouth morphs")

    candidates = []
    for index, obj in enumerate(_objects_below(root)):
        matches = _shape_key_matches(obj)
        vowel_count = sum(channel in matches for channel in VOWEL_CHANNELS)
        if vowel_count:
            candidates.append((vowel_count, -index, obj, matches))
    profile.bindings.clear()
    if not candidates:
        profile.binding_status = "ERROR"
        raise AnimationError("no MMD A/I/U/E/O shape keys were found below the model root")

    _score, _order, target, matches = max(candidates, key=lambda value: value[:2])
    for channel in (*VOWEL_CHANNELS, "CLOSED"):
        key_name = matches.get(channel)
        if not key_name:
            continue
        binding = profile.bindings.add()
        binding.viseme_id = channel
        binding.enabled = True
        binding.target_kind = "SHAPE_KEY"
        binding.target_object = target
        binding.target_key_name = key_name
        binding.scale = 1.0
        binding.offset = 0.0
        binding.minimum = 0.0
        binding.maximum = 1.0
        binding.note = "MMD standard morph"

    vowel_count = sum(
        binding.viseme_id in VOWEL_CHANNELS for binding in profile.bindings
    )
    profile.binding_status = "VALID" if vowel_count == 5 else "WARNING"
    return len(profile.bindings)


def _rna_events(clip: Any) -> list[VisemeEvent]:
    offset = max(0.0, float(clip.audio_offset_sec))
    result = []
    for value in clip.events:
        end_sec = max(0.0, float(value.end_sec) - offset)
        start_sec = min(end_sec, max(0.0, float(value.start_sec) - offset))
        result.append(
            VisemeEvent(
                viseme_id=value.viseme_id,
                start_sec=start_sec,
                end_sec=end_sec,
                weight=value.weight,
                confidence=value.confidence,
                source=value.source,
                source_index=value.source_index,
                source_text=value.source_text,
                phoneme=value.phoneme,
                language_code=value.language_code,
                source_phoneme=value.source_phoneme,
                articulation_class=value.articulation_class,
                priority=value.priority,
            )
        )
    return result


def _safe_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_.-]+", "_", value).strip("_")
    return (cleaned or fallback)[:48]


def _binding_value(binding: Any, value: float) -> float:
    mapped = 1.0 - value if binding.invert else value
    mapped = mapped * binding.scale + binding.offset
    return max(binding.minimum, min(binding.maximum, mapped))


def _add_curve(
    action: Any,
    datablock: Any,
    data_path: str,
    samples: Sequence[tuple[float, float]],
) -> None:
    fcurve = action.fcurve_ensure_for_datablock(
        datablock,
        data_path,
        group_name="MMD Mouth",
    )
    points = fcurve.keyframe_points
    points.add(len(samples))
    for point, (frame, value) in zip(points, samples):
        point.co = (frame, value)
        point.interpolation = "LINEAR"
    fcurve.update()


def _add_nla_strip(
    datablock: Any,
    action: Any,
    *,
    strip_name: str,
    start_frame: int,
    local_end_frame: float,
) -> Any:
    animation_data = datablock.animation_data_create()
    track = animation_data.nla_tracks.new()
    track.name = strip_name
    strip = track.strips.new(strip_name, start_frame, action)
    strip.action_frame_start = 0.0
    strip.action_frame_end = max(1.0, local_end_frame)
    strip.frame_start = float(start_frame)
    strip.frame_end = float(start_frame) + max(1.0, local_end_frame)
    strip.blend_type = "REPLACE"
    strip.extrapolation = "NOTHING"
    strip.influence = 1.0
    return strip


def _animation_owner(obj: Any) -> Any | None:
    if obj is None:
        return None
    if obj.type == "MESH" and obj.data.shape_keys is not None:
        return obj.data.shape_keys
    return obj


def move_generated_assets(clip: Any) -> int:
    """Move the clip's recorded NLA strips without touching their Actions."""

    moved = 0
    for asset in clip.assets:
        owner = _animation_owner(asset.owner_object)
        animation_data = owner.animation_data if owner is not None else None
        if animation_data is None:
            continue
        for track in animation_data.nla_tracks:
            for strip in track.strips:
                if (
                    strip.name != asset.strip_name
                    or getattr(strip.action, "name", "") != asset.action_name
                ):
                    continue
                duration = max(1.0, float(strip.frame_end - strip.frame_start))
                strip.frame_start = float(clip.start_frame)
                strip.frame_end = float(clip.start_frame) + duration
                moved += 1
    return moved


def remove_generated_assets(clip: Any) -> None:
    controllers = {
        asset.controller_object
        for asset in clip.assets
        if asset.controller_object is not None
    }
    action_names = set()
    for asset in clip.assets:
        action_names.add(asset.action_name)
        owner = _animation_owner(asset.owner_object)
        animation_data = owner.animation_data if owner is not None else None
        if animation_data is None:
            continue
        for track in list(animation_data.nla_tracks):
            for strip in list(track.strips):
                if (
                    strip.name == asset.strip_name
                    and getattr(strip.action, "name", "") == asset.action_name
                ):
                    track.strips.remove(strip)
            if not track.strips and track.name == asset.strip_name:
                animation_data.nla_tracks.remove(track)
        if animation_data.action is not None and animation_data.action.name == asset.action_name:
            animation_data.action = None
    clip.assets.clear()
    for name in action_names:
        action = bpy.data.actions.get(name)
        if action is not None and action.users == 0:
            bpy.data.actions.remove(action)

    for controller in controllers:
        _remove_controller_if_unused(clip, controller)


def _driver_fcurve(datablock: Any, data_path: str) -> Any | None:
    animation_data = datablock.animation_data
    if animation_data is None:
        return None
    return animation_data.drivers.find(data_path, index=-1)


def _driver_targets_object(fcurve: Any, target_object: Any) -> bool:
    return any(
        target.id == target_object
        for variable in fcurve.driver.variables
        for target in variable.targets
    )


def _driver_profile_ids(fcurve: Any) -> set[str]:
    result = set()
    for variable in fcurve.driver.variables:
        for target in variable.targets:
            target_id = target.id
            if target_id is None or not hasattr(target_id, "get"):
                continue
            profile_id = target_id.get("mmd_mouth_profile_id", "")
            if profile_id:
                result.add(str(profile_id))
    return result


def _remove_controller_drivers(controller: Any) -> None:
    for shape_keys in bpy.data.shape_keys:
        animation_data = shape_keys.animation_data
        if animation_data is None:
            continue
        for fcurve in list(animation_data.drivers):
            if _driver_targets_object(fcurve, controller):
                shape_keys.driver_remove(fcurve.data_path, fcurve.array_index)


def _remove_controller_if_unused(clip: Any, controller: Any) -> None:
    profile_id = str(controller.get("mmd_mouth_profile_id", ""))
    if not profile_id:
        return
    for scene in bpy.data.scenes:
        settings = getattr(scene, "mmd_mouth", None)
        if settings is None:
            continue
        for profile in settings.model_profiles:
            if profile.profile_id != profile_id:
                continue
            for other_clip in profile.clips:
                if other_clip == clip:
                    continue
                if any(
                    asset.controller_object == controller
                    for asset in other_clip.assets
                ):
                    return
    _remove_controller_drivers(controller)
    if bpy.data.objects.get(controller.name) == controller:
        bpy.data.objects.remove(controller, do_unlink=True)


def _record_asset(
    clip: Any,
    *,
    owner_object: Any,
    action: Any,
    strip: Any,
    controller: Any | None = None,
) -> None:
    asset = clip.assets.add()
    asset.asset_id = uuid4().hex
    asset.asset_kind = "NLA_STRIP"
    asset.owner_object = owner_object
    asset.action_name = action.name
    asset.strip_name = strip.name
    asset.controller_object = controller
    asset.generated_at_schema = SCHEMA_VERSION


def _validate_shape_binding(binding: Any) -> tuple[Any, Any]:
    obj = binding.target_object
    if obj is None or obj.type != "MESH" or obj.data.shape_keys is None:
        raise AnimationError(f"invalid shape-key target for {binding.viseme_id}")
    key = obj.data.shape_keys.key_blocks.get(binding.target_key_name)
    if key is None:
        raise AnimationError(
            f"shape key '{binding.target_key_name}' is missing for {binding.viseme_id}"
        )
    return obj, key


def _remove_own_driver(key: Any, profile_id: str) -> None:
    shape_keys = key.id_data
    data_path = key.path_from_id("value")
    fcurve = _driver_fcurve(shape_keys, data_path)
    if fcurve is None:
        return
    if profile_id in _driver_profile_ids(fcurve):
        shape_keys.driver_remove(data_path)
    else:
        raise AnimationError(
            f"shape key '{key.name}' already has a driver not owned by this profile"
        )


def _bake_shape_keys(
    profile: Any,
    clip: Any,
    sampled: dict[str, list[tuple[float, float]]],
    local_end_frame: float,
) -> int:
    grouped: dict[Any, list[tuple[Any, Any]]] = defaultdict(list)
    for binding in profile.bindings:
        if not binding.enabled or binding.target_kind != "SHAPE_KEY":
            continue
        obj, key = _validate_shape_binding(binding)
        grouped[obj.data.shape_keys].append((binding, key))

    generated = 0
    profile_tag = _safe_name(profile.display_name, "Model")
    clip_tag = _safe_name(clip.display_name, "Clip")
    for shape_keys, values in grouped.items():
        previous_action = (
            shape_keys.animation_data.action
            if shape_keys.animation_data is not None
            else None
        )
        action = bpy.data.actions.new(
            f"MMDMouth_{profile_tag}_{clip_tag}_{clip.clip_id[:8]}"
        )
        shape_keys.animation_data_create().action = action
        try:
            for binding, key in values:
                _remove_own_driver(key, profile.profile_id)
                channel_samples = [
                    (frame, _binding_value(binding, value))
                    for frame, value in sampled[binding.viseme_id]
                ]
                _add_curve(
                    action,
                    shape_keys,
                    key.path_from_id("value"),
                    channel_samples,
                )
        finally:
            shape_keys.animation_data.action = previous_action
        strip_name = f"MMDMouth_{clip.clip_id[:8]}"
        strip = _add_nla_strip(
            shape_keys,
            action,
            strip_name=strip_name,
            start_frame=clip.start_frame,
            local_end_frame=local_end_frame,
        )
        _record_asset(
            clip,
            owner_object=values[0][0].target_object,
            action=action,
            strip=strip,
        )
        generated += 1
    return generated


def _profile_controller(scene: Any, profile: Any) -> Any:
    controller = next(
        (
            obj
            for obj in bpy.data.objects
            if obj.get("mmd_mouth_profile_id") == profile.profile_id
        ),
        None,
    )
    if controller is None:
        controller = bpy.data.objects.new(
            f"MMDMouth_Controller_{profile.profile_id[:8]}",
            None,
        )
        scene.collection.objects.link(controller)
        controller["mmd_mouth_profile_id"] = profile.profile_id
        controller.empty_display_type = "PLAIN_AXES"
        controller.empty_display_size = 0.25
        controller.hide_render = True
        if profile.root_object is not None:
            controller.parent = profile.root_object
    for channel in (*VOWEL_CHANNELS, "CLOSED"):
        property_name = f"mmd_mouth_{channel}"
        if property_name not in controller:
            controller[property_name] = 0.0
            controller.id_properties_ui(property_name).update(
                min=0.0,
                max=1.0,
                soft_min=0.0,
                soft_max=1.0,
            )
    return controller


def _driver_expression(binding: Any) -> str:
    value = "(1.0-v)" if binding.invert else "v"
    mapped = f"(({value})*{binding.scale!r}+{binding.offset!r})"
    return f"min({binding.maximum!r},max({binding.minimum!r},{mapped}))"


def _ensure_driver(binding: Any, key: Any, controller: Any) -> None:
    shape_keys = key.id_data
    data_path = key.path_from_id("value")
    fcurve = _driver_fcurve(shape_keys, data_path)
    if fcurve is not None:
        is_ours = _driver_targets_object(fcurve, controller)
        if not is_ours:
            raise AnimationError(
                f"shape key '{key.name}' already has an unrelated driver"
            )
        while fcurve.driver.variables:
            fcurve.driver.variables.remove(fcurve.driver.variables[0])
    else:
        fcurve = shape_keys.driver_add(data_path)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    driver.expression = _driver_expression(binding)
    variable = driver.variables.new()
    variable.name = "v"
    target = variable.targets[0]
    target.id = controller
    target.data_path = f'["mmd_mouth_{binding.viseme_id}"]'


def _validate_output_bindings(profile: Any) -> None:
    count = 0
    for binding in profile.bindings:
        if not binding.enabled or binding.target_kind != "SHAPE_KEY":
            continue
        _obj, key = _validate_shape_binding(binding)
        count += 1
        fcurve = _driver_fcurve(key.id_data, key.path_from_id("value"))
        if fcurve is not None and profile.profile_id not in _driver_profile_ids(fcurve):
            raise AnimationError(
                f"shape key '{key.name}' already has a driver not owned by this profile"
            )
    if count == 0:
        raise AnimationError("no enabled shape-key bindings could be generated")


def _build_driver_output(
    scene: Any,
    profile: Any,
    clip: Any,
    sampled: dict[str, list[tuple[float, float]]],
    local_end_frame: float,
) -> int:
    controller = _profile_controller(scene, profile)
    previous_action = (
        controller.animation_data.action
        if controller.animation_data is not None
        else None
    )
    action = bpy.data.actions.new(
        f"MMDMouth_Controller_{_safe_name(clip.display_name, 'Clip')}_{clip.clip_id[:8]}"
    )
    controller.animation_data_create().action = action
    try:
        for channel in (*VOWEL_CHANNELS, "CLOSED"):
            _add_curve(
                action,
                controller,
                f'["mmd_mouth_{channel}"]',
                sampled[channel],
            )
    finally:
        controller.animation_data.action = previous_action

    for binding in profile.bindings:
        if not binding.enabled or binding.target_kind != "SHAPE_KEY":
            continue
        _obj, key = _validate_shape_binding(binding)
        _ensure_driver(binding, key, controller)

    strip_name = f"MMDMouth_{clip.clip_id[:8]}"
    strip = _add_nla_strip(
        controller,
        action,
        strip_name=strip_name,
        start_frame=clip.start_frame,
        local_end_frame=local_end_frame,
    )
    _record_asset(
        clip,
        owner_object=controller,
        action=action,
        strip=strip,
        controller=controller,
    )
    return 1


def generate_clip(scene: Any, profile: Any, clip: Any) -> int:
    if profile.root_object is None:
        raise AnimationError("select an MMD model root before generating mouth animation")
    if not clip.events:
        raise AnimationError("the clip has no viseme timeline; recognize the audio first")
    if not profile.bindings:
        scan_mmd_bindings(profile)
    _validate_output_bindings(profile)

    events = _rna_events(clip)
    effective_fps = scene.render.fps / scene.render.fps_base
    sampled = dict(
        sample_viseme_channels(
            events,
            duration_sec=clip.duration_sec,
            fps=effective_fps,
            attack_ms=scene.mmd_mouth.default_attack_ms,
            release_ms=scene.mmd_mouth.default_release_ms,
            hold_ratio=scene.mmd_mouth.default_hold_ratio,
            easing_mode=clip.easing_mode,
        )
    )
    strength = max(0.0, float(clip.mouth_strength))
    for channel in (*VOWEL_CHANNELS, "CLOSED"):
        sampled[channel] = [
            (frame, value * strength)
            for frame, value in sampled[channel]
        ]
    local_end_frame = max(
        (frame for values in sampled.values() for frame, _value in values),
        default=1.0,
    )
    remove_generated_assets(clip)
    if clip.generation_mode == "DRIVER":
        generated = _build_driver_output(
            scene,
            profile,
            clip,
            sampled,
            local_end_frame,
        )
    else:
        generated = _bake_shape_keys(
            profile,
            clip,
            sampled,
            local_end_frame,
        )
    if generated <= 0:
        raise AnimationError("no enabled shape-key bindings could be generated")

    clip.status = "BAKED"
    clip.last_error = ""
    clip.render_fps = scene.render.fps
    clip.render_fps_base = scene.render.fps_base
    scene.frame_end = max(
        scene.frame_end,
        int(ceil(clip.start_frame + local_end_frame)),
    )
    return generated


__all__ = [
    "AnimationError",
    "MMD_MORPH_ALIASES",
    "generate_clip",
    "move_generated_assets",
    "remove_generated_assets",
    "scan_mmd_bindings",
]
