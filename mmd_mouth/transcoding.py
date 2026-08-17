"""Blender-native conversion to the PCM WAV format used by the worker."""

from __future__ import annotations

from hashlib import sha1
from pathlib import Path
import wave

import bpy


class AudioTranscodeError(ValueError):
    """Raised when Blender cannot decode or export a source audio file."""


def _absolute_path(value: str) -> Path:
    return Path(bpy.path.abspath(str(value))).expanduser().resolve()


def _source_audio_path(clip) -> Path:
    converted = str(getattr(clip, "transcoded_audio_path", "")).strip()
    if converted:
        converted_path = _absolute_path(converted)
        if converted_path.is_file():
            return converted_path
    raw = str(getattr(clip, "audio_path", "")).strip()
    return _absolute_path(raw) if raw else Path()


def _is_pcm16_wav(path: Path) -> bool:
    if path.suffix.casefold() != ".wav" or not path.is_file():
        return False
    try:
        with wave.open(str(path), "rb") as wav_file:
            return (
                wav_file.getcomptype() == "NONE"
                and wav_file.getsampwidth() == 2
                and wav_file.getnchannels() > 0
                and wav_file.getframerate() > 0
            )
    except (OSError, EOFError, wave.Error):
        return False


def _cache_directory(scene, settings) -> Path:
    configured = str(getattr(settings, "cache_directory", "")).strip()
    if configured:
        directory = _absolute_path(configured)
    elif bpy.data.filepath:
        directory = Path(bpy.data.filepath).resolve().parent / ".mmd_mouth_cache"
    else:
        directory = Path(bpy.app.tempdir).resolve() / "mmd_mouth"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "audio"


def _cache_path(scene, clip, source_path: Path) -> Path:
    settings = scene.mmd_mouth
    try:
        stat = source_path.stat()
        fingerprint = f"{source_path}|{stat.st_size}|{stat.st_mtime_ns}"
    except OSError:
        fingerprint = str(source_path)
    digest = sha1(fingerprint.encode("utf-8", "surrogatepass")).hexdigest()[:20]
    clip_tag = str(getattr(clip, "clip_id", "audio"))[:8] or "audio"
    return _cache_directory(scene, settings) / f"{clip_tag}_{digest}.wav"


def _export_pcm_wav(source_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import aud

        # Aud decodes the complete source without depending on the active VSE
        # scene or Blender's current frame range.
        sound = aud.Sound.file(str(source_path))
        rate, channels = sound.specs
        if rate <= 0.0 or channels <= 0:
            raise AudioTranscodeError(
                f"Blender could not read audio metadata: {source_path}"
            )
        if channels != aud.CHANNELS_MONO:
            sound = sound.rechannel(aud.CHANNELS_MONO)
        sound.write(
            str(output_path),
            max(1, int(round(rate))),
            aud.CHANNELS_MONO,
            aud.FORMAT_S16,
            aud.CONTAINER_WAV,
            aud.CODEC_PCM,
            0,
            4096,
        )
        if not _is_pcm16_wav(output_path):
            raise AudioTranscodeError(
                "Blender did not produce a valid 16-bit PCM WAV file"
            )
    except AudioTranscodeError:
        raise
    except Exception as exc:
        raise AudioTranscodeError(
            f"audio conversion failed for {source_path}: {exc}"
        ) from exc


def ensure_compatible_audio(scene, clip) -> Path:
    """Return a worker-compatible WAV, transcoding the selected source once."""

    source_path = _source_audio_path(clip)
    if not source_path or not source_path.is_file():
        clip.audio_transcode_error = ""
        raise AudioTranscodeError(
            f"audio file does not exist: {source_path or '<empty>'}"
        )
    converted_value = str(getattr(clip, "transcoded_audio_path", "")).strip()
    converted_path = _absolute_path(converted_value) if converted_value else Path()
    using_converted = bool(converted_value) and source_path == converted_path
    if _is_pcm16_wav(source_path):
        if not using_converted:
            clip.transcoded_audio_path = ""
        clip.audio_transcode_error = ""
        return source_path

    output_path = _cache_path(scene, clip, source_path)
    if not _is_pcm16_wav(output_path):
        try:
            _export_pcm_wav(source_path, output_path)
        except AudioTranscodeError as exc:
            clip.audio_transcode_error = str(exc)
            raise
    clip.transcoded_audio_path = str(output_path)
    clip.audio_transcode_error = ""
    return output_path


def transcode_clip_audio(scene, clip) -> Path:
    """Convert a clip's selected source, or return it when already compatible."""

    source_path = _source_audio_path(clip)
    if source_path and _is_pcm16_wav(source_path):
        converted_value = str(getattr(clip, "transcoded_audio_path", "")).strip()
        converted_path = _absolute_path(converted_value) if converted_value else Path()
        if not converted_value or source_path != converted_path:
            clip.transcoded_audio_path = ""
        clip.audio_transcode_error = ""
        return source_path
    return ensure_compatible_audio(scene, clip)


def effective_audio_path(clip) -> Path:
    """Return an existing converted path before falling back to the source."""

    return _source_audio_path(clip)


__all__ = [
    "AudioTranscodeError",
    "effective_audio_path",
    "ensure_compatible_audio",
    "transcode_clip_audio",
]
