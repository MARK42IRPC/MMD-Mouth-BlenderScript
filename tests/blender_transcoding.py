"""Blender regression test for common-audio transcoding."""

from __future__ import annotations

from pathlib import Path
import sys
import wave

import bpy


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "cache" / "transcoding" / "input.mp3"
CACHE = ROOT / "cache" / "transcoding" / "output"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import mmd_mouth  # noqa: E402
from mmd_mouth.audio import CLIP_ID_KEY  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    require(INPUT.is_file(), f"compressed test input is missing: {INPUT}")
    mmd_mouth.register()
    scene = bpy.context.scene
    settings = scene.mmd_mouth
    settings.cache_directory = str(CACHE)

    require("FINISHED" in bpy.ops.mmd_mouth.add_model(), "model setup failed")
    require("FINISHED" in bpy.ops.mmd_mouth.add_clip(), "clip setup failed")
    profile = settings.model_profiles[0]
    clip = profile.clips[0]
    clip.audio_path = str(INPUT)
    source_before = INPUT.read_bytes()

    require(
        "FINISHED" in bpy.ops.mmd_mouth.transcode_audio(),
        clip.audio_transcode_error or "transcode operator failed",
    )
    output = Path(bpy.path.abspath(clip.transcoded_audio_path)).resolve()
    require(output.is_file(), f"converted file is missing: {output}")
    require(INPUT.read_bytes() == source_before, "source audio was overwritten")
    require(output != INPUT.resolve(), "converted file aliases the source")
    with wave.open(str(output), "rb") as wav_file:
        require(wav_file.getcomptype() == "NONE", "output is not PCM")
        require(wav_file.getsampwidth() == 2, "output is not 16-bit")
        require(wav_file.getnchannels() > 0, "output has no audio channels")
        require(wav_file.getframerate() > 0, "output has no sample rate")

    editor = scene.sequence_editor
    owned = [
        strip
        for strip in editor.strips
        if str(strip.get(CLIP_ID_KEY, "")) == clip.clip_id
    ]
    require(len(owned) == 1, "converted audio preview was not synchronized")
    require(
        Path(bpy.path.abspath(owned[0].sound.filepath)).resolve() == output,
        "audio preview still points at the source file",
    )
    require(clip.audio_path == str(INPUT), "source audio property changed")
    print(f"MMD_TRANSCODING_OK input={INPUT} output={output}", flush=True)


main()
