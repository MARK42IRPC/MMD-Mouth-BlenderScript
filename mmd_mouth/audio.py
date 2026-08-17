"""Owned Video Sequence Editor audio previews for mouth clips."""

from __future__ import annotations

from math import ceil
import os
from pathlib import Path
from typing import Any
import warnings

import bpy


CLIP_ID_KEY = "mmd_mouth_clip_id"


class AudioPreviewError(RuntimeError):
    """Raised when a clip audio preview cannot be synchronized."""


def _normalized_path(value: str) -> str:
    return os.path.normcase(os.path.abspath(value))


def _owned_strips(scene: Any, clip_id: str) -> list[Any]:
    editor = scene.sequence_editor
    if editor is None or not clip_id:
        return []
    return [
        strip
        for strip in editor.strips
        if str(strip.get(CLIP_ID_KEY, "")) == clip_id
    ]


def _available_channel(editor: Any, preferred: int = 0) -> int:
    occupied = {int(strip.channel) for strip in editor.strips}
    if 1 <= preferred <= 128 and preferred not in occupied:
        return preferred
    for channel in range(1, 129):
        if channel not in occupied:
            return channel
    raise AudioPreviewError("the sequencer has no free channel for the audio preview")


def remove_clip_audio(scene: Any, clip: Any) -> int:
    """Remove only VSE strips carrying this clip's ownership marker."""

    editor = scene.sequence_editor
    if editor is None:
        clip.audio_strip_name = ""
        return 0
    removed = 0
    for strip in list(_owned_strips(scene, str(clip.clip_id))):
        editor.strips.remove(strip)
        removed += 1
    clip.audio_strip_name = ""
    return removed


def _apply_timing(scene: Any, strip: Any, clip: Any) -> None:
    fps = scene.render.fps / scene.render.fps_base
    if fps <= 0.0:
        raise AudioPreviewError("render FPS must be positive")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        strip.frame_offset_start = 0.0
        strip.frame_offset_end = 0.0
        strip.frame_start = float(clip.start_frame)

        source_frames = max(1, int(strip.frame_duration))
        requested_offset = max(0, round(float(clip.audio_offset_sec) * fps))
        offset_frames = min(requested_offset, source_frames - 1)
        if offset_frames:
            strip.frame_offset_start = float(offset_frames)
            strip.frame_start = float(clip.start_frame - offset_frames)

        if clip.duration_sec > 0.0:
            available = max(1, int(strip.frame_final_end - strip.frame_final_start))
            requested = max(1, int(ceil(float(clip.duration_sec) * fps)))
            strip.frame_final_duration = min(requested, available)

        scene.frame_end = max(scene.frame_end, int(strip.frame_final_end))


def sync_clip_audio(scene: Any, clip: Any) -> Any | None:
    """Create or update the clip's owned sound strip."""

    clip_id = str(clip.clip_id)
    if not clip_id:
        return None

    audio_value = str(clip.audio_path).strip()
    if not audio_value:
        remove_clip_audio(scene, clip)
        return None
    audio_path = Path(bpy.path.abspath(audio_value)).expanduser()
    if not audio_path.is_file():
        remove_clip_audio(scene, clip)
        raise AudioPreviewError(f"audio file does not exist: {audio_path}")

    owned = _owned_strips(scene, clip_id)
    expected_path = _normalized_path(str(audio_path))
    matching = next(
        (
            strip
            for strip in owned
            if strip.type == "SOUND"
            and strip.sound is not None
            and _normalized_path(bpy.path.abspath(strip.sound.filepath))
            == expected_path
        ),
        None,
    )
    preferred_channel = int(owned[0].channel) if owned else 0
    for strip in list(owned):
        if strip != matching:
            scene.sequence_editor.strips.remove(strip)

    if matching is None:
        editor = scene.sequence_editor_create()
        channel = _available_channel(editor, preferred_channel)
        try:
            matching = editor.strips.new_sound(
                f"MMDMouth_Audio_{clip_id[:8]}",
                str(audio_path),
                channel=channel,
                frame_start=int(clip.start_frame),
            )
        except RuntimeError as exc:
            raise AudioPreviewError(f"could not add audio preview: {exc}") from exc
        matching[CLIP_ID_KEY] = clip_id

    matching.volume = float(clip.audio_volume)
    _apply_timing(scene, matching, clip)
    clip.audio_strip_name = matching.name
    return matching


__all__ = [
    "AudioPreviewError",
    "CLIP_ID_KEY",
    "remove_clip_audio",
    "sync_clip_audio",
]
