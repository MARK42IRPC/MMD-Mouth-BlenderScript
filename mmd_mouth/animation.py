"""MMD morph discovery and Blender 5.2 animation generation."""

from __future__ import annotations

from bisect import bisect_right
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
}

_KEYFRAME_BAKE_TAG = "mmd_mouth_keyframe_bake"
_KEYFRAME_BAKE_PROFILE = "mmd_mouth_profile_id"


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

    # Rescanning is a binding replacement boundary. Remove all prior
    # profile-owned output, including legacy CLOSED bindings, before dropping
    # the old binding records.
    remove_profile_keyframe_bake(profile)
    _remove_legacy_non_vowel_drivers(profile)
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
    for channel in VOWEL_CHANNELS:
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
    ordered_events = sorted(
        clip.events,
        key=lambda value: (
            float(value.start_sec),
            float(value.end_sec),
            int(value.source_index),
            value.viseme_id,
        ),
    )
    for value in ordered_events:
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
        point.interpolation = "BEZIER"
        point.handle_left_type = "AUTO_CLAMPED"
        point.handle_right_type = "AUTO_CLAMPED"
    fcurve.update()


def _reduce_curve_samples(
    samples: Sequence[tuple[float, float]],
    *,
    tolerance: float = 0.005,
) -> list[tuple[float, float]]:
    """Keep curve control points while dropping frame-by-frame samples."""

    if len(samples) <= 2:
        return list(samples)
    ordered = sorted(samples, key=lambda value: value[0])
    deduplicated = []
    for frame, value in ordered:
        if deduplicated and frame == deduplicated[-1][0]:
            deduplicated[-1] = (frame, value)
        else:
            deduplicated.append((frame, value))
    if len(deduplicated) <= 2:
        return deduplicated

    keep = {0, len(deduplicated) - 1}
    pending = [(0, len(deduplicated) - 1)]
    while pending:
        left_index, right_index = pending.pop()
        left_frame, left_value = deduplicated[left_index]
        right_frame, right_value = deduplicated[right_index]
        span = right_frame - left_frame
        largest_error = tolerance
        largest_index = None
        for index in range(left_index + 1, right_index):
            frame, value = deduplicated[index]
            if span <= 0.0:
                expected = left_value
            else:
                progress = (frame - left_frame) / span
                expected = left_value + (right_value - left_value) * progress
            error = abs(value - expected)
            if error > largest_error:
                largest_error = error
                largest_index = index
        if largest_index is not None:
            keep.add(largest_index)
            pending.append((left_index, largest_index))
            pending.append((largest_index, right_index))
    return [value for index, value in enumerate(deduplicated) if index in keep]


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


def _is_profile_keyframe_action(action: Any, profile_id: str) -> bool:
    return bool(
        action is not None
        and action.get(_KEYFRAME_BAKE_TAG, False)
        and str(action.get(_KEYFRAME_BAKE_PROFILE, "")) == str(profile_id)
    )


def _record_profile_keyframe_asset(
    profile: Any,
    *,
    owner_object: Any,
    action: Any,
    strip: Any | None = None,
) -> None:
    asset = profile.keyframe_assets.add()
    asset.asset_id = uuid4().hex
    asset.asset_kind = "NLA_STRIP" if strip is not None else "ACTION"
    asset.owner_object = owner_object
    asset.action_name = action.name
    asset.strip_name = strip.name if strip is not None else ""
    asset.controller_object = None
    asset.generated_at_schema = SCHEMA_VERSION


def _action_fcurves(action: Any) -> Iterable[Any]:
    """Yield F-curves from all Blender 5.2 Action channel bags."""

    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                yield from channelbag.fcurves


def _remove_action_curves(action: Any, data_paths: set[str]) -> bool:
    removed = False
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                for fcurve in list(channelbag.fcurves):
                    if fcurve.data_path not in data_paths:
                        continue
                    channelbag.fcurves.remove(fcurve)
                    removed = True
    return removed


def _profile_keyframe_paths(profile: Any) -> dict[Any, set[str]]:
    paths: dict[Any, set[str]] = defaultdict(set)
    for binding in getattr(profile, "bindings", ()):
        if binding.target_kind != "SHAPE_KEY":
            continue
        obj = binding.target_object
        if obj is None or obj.type != "MESH" or obj.data.shape_keys is None:
            continue
        key = obj.data.shape_keys.key_blocks.get(binding.target_key_name)
        if key is not None:
            paths[obj.data.shape_keys].add(key.path_from_id("value"))
    return paths


def _action_has_fcurves(action: Any) -> bool:
    return next(_action_fcurves(action), None) is not None


def _add_profile_nla_strip(
    datablock: Any,
    action: Any,
    *,
    strip_name: str,
    end_frame: float,
) -> Any:
    """Overlay a profile-owned mouth Action without replacing base animation."""

    animation_data = datablock.animation_data_create()
    track = animation_data.nla_tracks.new()
    track.name = strip_name
    end_frame = max(1.0, float(end_frame))
    strip = track.strips.new(strip_name, 0, action)
    strip.action_frame_start = 0.0
    strip.action_frame_end = end_frame
    strip.frame_start = 0.0
    strip.frame_end = end_frame
    strip.blend_type = "REPLACE"
    strip.extrapolation = "NOTHING"
    strip.influence = 1.0
    return strip


def remove_profile_keyframe_bake(profile: Any) -> bool:
    """Remove generated mouth curves while preserving unrelated channels."""

    keyframe_paths = _profile_keyframe_paths(profile)
    assets = list(getattr(profile, "keyframe_assets", ()))
    action_names = {asset.action_name for asset in assets if asset.action_name}
    action_paths: dict[str, set[str]] = defaultdict(set)
    for asset in assets:
        if not asset.action_name:
            continue
        owner = asset.owner_object
        shape_keys = (
            owner.data.shape_keys
            if owner is not None
            and owner.type == "MESH"
            and owner.data.shape_keys is not None
            else None
        )
        if shape_keys is not None:
            action_paths[asset.action_name].update(
                keyframe_paths.get(shape_keys, set())
            )
    removed = bool(action_names)
    removable_actions = set()
    for asset in assets:
        if not asset.strip_name:
            continue
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
                    removed = True
            if not track.strips and track.name == asset.strip_name:
                animation_data.nla_tracks.remove(track)
    for shape_keys in bpy.data.shape_keys:
        animation_data = shape_keys.animation_data
        action = animation_data.action if animation_data is not None else None
        if _is_profile_keyframe_action(action, profile.profile_id):
            action_names.add(action.name)
            removed = True
            _remove_action_curves(action, keyframe_paths.get(shape_keys, set()))
            if not _action_has_fcurves(action):
                animation_data.action = None
                removable_actions.add(action.name)
            else:
                action[_KEYFRAME_BAKE_TAG] = False
                action[_KEYFRAME_BAKE_PROFILE] = ""
    profile.keyframe_assets.clear()
    for name in action_names:
        action = bpy.data.actions.get(name)
        if action is None or not _is_profile_keyframe_action(
            action,
            profile.profile_id,
        ):
            continue
        paths = action_paths.get(name, set())
        if not paths:
            paths = set().union(*keyframe_paths.values()) if keyframe_paths else set()
        _remove_action_curves(action, paths)
        if name in removable_actions or not _action_has_fcurves(action):
            if action.users == 0:
                bpy.data.actions.remove(action)
            else:
                bpy.data.actions.remove(action, do_unlink=True)
        else:
            action[_KEYFRAME_BAKE_TAG] = False
            action[_KEYFRAME_BAKE_PROFILE] = ""
    return removed


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


def _remove_legacy_non_vowel_drivers(profile: Any) -> None:
    """Drop this profile's old CLOSED/custom shape-key drivers only."""

    for binding in getattr(profile, "bindings", ()):
        if (
            binding.viseme_id in VOWEL_CHANNELS
            or binding.target_kind != "SHAPE_KEY"
        ):
            continue
        obj = binding.target_object
        if obj is None or obj.type != "MESH" or obj.data.shape_keys is None:
            continue
        key = obj.data.shape_keys.key_blocks.get(binding.target_key_name)
        if key is None:
            continue
        data_path = key.path_from_id("value")
        fcurve = _driver_fcurve(key.id_data, data_path)
        if fcurve is not None and profile.profile_id in _driver_profile_ids(fcurve):
            key.id_data.driver_remove(data_path)


def _remove_unmanaged_profile_drivers(profile: Any) -> None:
    """Remove stale profile drivers outside the five vowel target paths."""

    allowed: dict[Any, set[str]] = defaultdict(set)
    for binding in getattr(profile, "bindings", ()):
        if (
            binding.viseme_id not in VOWEL_CHANNELS
            or binding.target_kind != "SHAPE_KEY"
        ):
            continue
        obj = binding.target_object
        if obj is None or obj.type != "MESH" or obj.data.shape_keys is None:
            continue
        key = obj.data.shape_keys.key_blocks.get(binding.target_key_name)
        if key is not None:
            allowed[obj.data.shape_keys].add(key.path_from_id("value"))

    for shape_keys in bpy.data.shape_keys:
        animation_data = shape_keys.animation_data
        if animation_data is None:
            continue
        for fcurve in list(animation_data.drivers):
            if profile.profile_id not in _driver_profile_ids(fcurve):
                continue
            if fcurve.data_path in allowed.get(shape_keys, set()):
                continue
            shape_keys.driver_remove(fcurve.data_path, fcurve.array_index)


def _bake_shape_keys(
    profile: Any,
    clip: Any,
    sampled: dict[str, list[tuple[float, float]]],
    local_end_frame: float,
) -> int:
    grouped: dict[Any, list[tuple[Any, Any]]] = defaultdict(list)
    for binding in profile.bindings:
        if (
            not binding.enabled
            or binding.target_kind != "SHAPE_KEY"
            or binding.viseme_id not in VOWEL_CHANNELS
        ):
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
    for channel in VOWEL_CHANNELS:
        property_name = f"mmd_mouth_{channel}"
        if property_name not in controller:
            controller[property_name] = 0.0
            controller.id_properties_ui(property_name).update(
                min=0.0,
                max=1.0,
                soft_min=0.0,
                soft_max=1.0,
            )
    if "mmd_mouth_CLOSED" in controller:
        del controller["mmd_mouth_CLOSED"]
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
    _remove_unmanaged_profile_drivers(profile)
    count = 0
    for binding in profile.bindings:
        if (
            not binding.enabled
            or binding.target_kind != "SHAPE_KEY"
            or binding.viseme_id not in VOWEL_CHANNELS
        ):
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
        for channel in VOWEL_CHANNELS:
            _add_curve(
                action,
                controller,
                f'["mmd_mouth_{channel}"]',
                sampled[channel],
            )
    finally:
        controller.animation_data.action = previous_action

    for binding in profile.bindings:
        if (
            not binding.enabled
            or binding.target_kind != "SHAPE_KEY"
            or binding.viseme_id not in VOWEL_CHANNELS
        ):
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


def _sample_clip_output(
    scene: Any,
    clip: Any,
) -> tuple[dict[str, list[tuple[float, float]]], float]:
    events = _rna_events(clip)
    effective_fps = scene.render.fps / scene.render.fps_base
    sampled = dict(
        sample_viseme_channels(
            events,
            duration_sec=clip.duration_sec,
            fps=effective_fps,
            attack_ms=clip.attack_ms,
            release_ms=clip.release_ms,
            hold_ratio=clip.hold_ratio,
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
    return sampled, local_end_frame


def _sample_value_at(
    samples: Sequence[tuple[float, float]],
    frame: float,
) -> float:
    if not samples or frame <= samples[0][0]:
        return samples[0][1] if samples else 0.0
    if frame >= samples[-1][0]:
        return samples[-1][1]
    frames = [sample[0] for sample in samples]
    right_index = bisect_right(frames, frame)
    left_frame, left_value = samples[right_index - 1]
    right_frame, right_value = samples[right_index]
    span = right_frame - left_frame
    if span <= 0.0:
        return right_value
    progress = (frame - left_frame) / span
    return left_value + (right_value - left_value) * progress


def _merge_profile_samples(
    prepared: Sequence[
        tuple[Any, dict[str, list[tuple[float, float]]], float]
    ],
) -> dict[str, list[tuple[float, float]]]:
    """Merge clip-local points into global frame samples.

    When clips overlap, the later clip in the profile takes precedence, which
    matches the replace-style layering used by the regular NLA output.
    """

    channels = (*VOWEL_CHANNELS, "CLOSED")
    frames = sorted(
        {
            float(clip.start_frame) + local_frame
            for clip, sampled, _local_end in prepared
            for values in sampled.values()
            for local_frame, _value in values
        }
    )
    merged = {channel: [] for channel in channels}
    for frame in frames:
        selected = None
        for index in range(len(prepared) - 1, -1, -1):
            clip, _sampled, local_end = prepared[index]
            local_frame = frame - float(clip.start_frame)
            if 0.0 <= local_frame <= local_end:
                selected = prepared[index]
                break
        if selected is None:
            values = {channel: 0.0 for channel in channels}
        else:
            _clip, sampled, local_end = selected
            local_frame = frame - float(_clip.start_frame)
            values = {
                channel: _sample_value_at(sampled[channel], local_frame)
                for channel in channels
            }
        for channel in channels:
            merged[channel].append((frame, values[channel]))
    return merged


def bake_profile_keyframes(scene: Any, profile: Any) -> tuple[int, int]:
    """Bake every populated clip into directly editable shape-key Actions."""

    if profile.root_object is None:
        raise AnimationError("select an MMD model root before baking keyframes")
    if not profile.bindings:
        scan_mmd_bindings(profile)
    _validate_output_bindings(profile)

    prepared = []
    for clip in profile.clips:
        if not clip.events:
            continue
        sampled, local_end_frame = _sample_clip_output(scene, clip)
        prepared.append((clip, sampled, local_end_frame))
    if not prepared:
        raise AnimationError("no mouth clip has a viseme timeline to bake")

    grouped: dict[Any, list[tuple[Any, Any]]] = defaultdict(list)
    for binding in profile.bindings:
        if (
            not binding.enabled
            or binding.target_kind != "SHAPE_KEY"
            or binding.viseme_id not in VOWEL_CHANNELS
        ):
            continue
        obj, key = _validate_shape_binding(binding)
        grouped[obj.data.shape_keys].append((binding, key))

    # Remove only the previous profile output.  Existing Actions and NLA
    # tracks remain the base animation for unrelated shape-key channels.
    remove_profile_keyframe_bake(profile)
    output_plans = {}
    for shape_keys, values in grouped.items():
        animation_data = shape_keys.animation_data
        previous_action = (
            animation_data.action if animation_data is not None else None
        )
        target_paths = {key.path_from_id("value") for _binding, key in values}
        has_unrelated_action = bool(
            previous_action is not None
            and any(
                fcurve.data_path not in target_paths
                for fcurve in _action_fcurves(previous_action)
            )
        )
        use_nla = bool(
            animation_data is not None
            and animation_data.nla_tracks
        ) or has_unrelated_action
        output_plans[shape_keys] = (values, previous_action, use_nla)

    merged = _merge_profile_samples(prepared)
    prepared_pointers = {clip.as_pointer() for clip, _sampled, _end in prepared}
    for clip in profile.clips:
        remove_generated_assets(clip)
        if clip.as_pointer() not in prepared_pointers:
            clip.status = "DRAFT"
            clip.last_error = ""

    profile_tag = _safe_name(profile.display_name, "Model")
    generated = 0
    for shape_keys, (bindings, previous_action, use_nla) in output_plans.items():
        action = bpy.data.actions.new(
            f"MMDMouth_Keyframes_{profile_tag}_"
            f"{_safe_name(shape_keys.name, 'ShapeKeys')}_"
            f"{profile.profile_id[:8]}"
        )
        action[_KEYFRAME_BAKE_TAG] = True
        action[_KEYFRAME_BAKE_PROFILE] = profile.profile_id
        shape_keys.animation_data_create().action = action
        try:
            for binding, key in bindings:
                channel_samples = [
                    (frame, _binding_value(binding, value))
                    for frame, value in merged[binding.viseme_id]
                ]
                reduced = _reduce_curve_samples(channel_samples)
                _add_curve(
                    action,
                    shape_keys,
                    key.path_from_id("value"),
                    reduced,
                )
        except Exception:
            shape_keys.animation_data.action = previous_action
            if action.users == 0:
                bpy.data.actions.remove(action)
            raise

        if use_nla:
            shape_keys.animation_data.action = previous_action
            strip = _add_profile_nla_strip(
                shape_keys,
                action,
                strip_name=f"MMDMouth_Keyframes_{profile.profile_id[:8]}",
                end_frame=max(
                    frame
                    for values in merged.values()
                    for frame, _value in values
                ),
            )
            _record_profile_keyframe_asset(
                profile,
                owner_object=bindings[0][0].target_object,
                action=action,
                strip=strip,
            )
        else:
            _record_profile_keyframe_asset(
                profile,
                owner_object=bindings[0][0].target_object,
                action=action,
            )
        generated += 1

    for clip, _sampled, local_end_frame in prepared:
        clip.generation_mode = "BAKE"
        clip.status = "BAKED"
        clip.last_error = ""
        clip.render_fps = scene.render.fps
        clip.render_fps_base = scene.render.fps_base
        scene.frame_end = max(
            scene.frame_end,
            int(ceil(clip.start_frame + local_end_frame)),
        )
    return len(prepared), generated


def generate_clip(scene: Any, profile: Any, clip: Any) -> int:
    if profile.root_object is None:
        raise AnimationError("select an MMD model root before generating mouth animation")
    if not clip.events:
        raise AnimationError("the clip has no viseme timeline; recognize the audio first")
    if not profile.bindings:
        scan_mmd_bindings(profile)
    _validate_output_bindings(profile)

    sampled, local_end_frame = _sample_clip_output(scene, clip)
    had_profile_keyframes = remove_profile_keyframe_bake(profile)
    if had_profile_keyframes:
        for other_clip in profile.clips:
            if other_clip.as_pointer() == clip.as_pointer():
                continue
            other_clip.status = "RECOGNIZED" if other_clip.events else "DRAFT"
            other_clip.last_error = ""
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
    "bake_profile_keyframes",
    "generate_clip",
    "move_generated_assets",
    "remove_profile_keyframe_bake",
    "remove_generated_assets",
    "scan_mmd_bindings",
]
