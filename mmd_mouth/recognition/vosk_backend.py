"""Optional Vosk backend.

This module does not import Vosk at module import time. It is intended to run
in an external worker environment where the ``vosk`` package is installed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from contextlib import contextmanager
import os
from pathlib import Path
import json
import struct
from threading import RLock
from typing import Any, Dict, Iterator, Optional
import wave

from ..core.schema import RecognitionCandidate, WordSegment
from .model_assets import ModelAssetError, ensure_vosk_model_directory


class VoskBackendError(RuntimeError):
    """Raised when a Vosk job cannot be started or completed."""


_VOSK_CWD_LOCK = RLock()


@contextmanager
def _vosk_model_argument(model_path: Path) -> Iterator[str]:
    """Yield a model argument that the Windows native layer can open.

    Vosk 0.3.45 passes the UTF-8 path bytes directly to its Windows native
    loader.  A non-ASCII absolute path can therefore fail even though Python
    itself can read the directory.  Loading ``.`` while the process is
    temporarily inside the model directory keeps the argument ASCII and lets
    the Windows filesystem resolve the Unicode working directory correctly.
    """

    resolved = model_path.resolve()
    if os.name != "nt" or str(resolved).isascii():
        yield str(resolved)
        return

    with _VOSK_CWD_LOCK:
        previous = Path.cwd()
        try:
            os.chdir(str(resolved))
            yield "."
        except OSError as exc:
            raise VoskBackendError(
                f"cannot enter Vosk model directory: {resolved}"
            ) from exc
        finally:
            os.chdir(str(previous))


@dataclass(frozen=True)
class VoskModelSpec:
    model_id: str
    language_code: str
    model_path: str
    archive_path: str = ""
    archive_sha256: str = ""
    calibration_bias: float = 0.0
    calibration_temperature: float = 1.0
    enabled: bool = True
    priority: int = 0

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "VoskModelSpec":
        required = ("model_id", "language_code", "model_path")
        missing = [key for key in required if not value.get(key)]
        if missing:
            raise ValueError(f"missing model fields: {', '.join(missing)}")
        return cls(
            model_id=str(value["model_id"]),
            language_code=str(value["language_code"]),
            model_path=str(value["model_path"]),
            archive_path=str(value.get("archive_path", "")),
            archive_sha256=str(value.get("archive_sha256", "")),
            calibration_bias=float(value.get("calibration_bias", 0.0)),
            calibration_temperature=float(
                value.get("calibration_temperature", 1.0)
            ),
            enabled=bool(value.get("enabled", True)),
            priority=int(value.get("priority", 0)),
        )

    def validate(self) -> None:
        if not self.model_id:
            raise ValueError("model_id is required")
        if not self.language_code:
            raise ValueError("language_code is required")
        if not self.model_path:
            raise ValueError("model_path is required")
        if self.calibration_temperature <= 0.0:
            raise ValueError("calibration_temperature must be positive")

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _downmix_s16(raw: bytes, channels: int) -> bytes:
    if channels <= 1:
        return raw
    sample_count = len(raw) // 2
    if sample_count == 0:
        return b""
    samples = struct.unpack(f"<{sample_count}h", raw)
    mono = []
    for index in range(0, sample_count, channels):
        frame = samples[index : index + channels]
        mono.append(int(sum(frame) / len(frame)))
    return struct.pack(f"<{len(mono)}h", *mono)


def _read_vosk_result(
    payload: str,
    *,
    base_start_sec: float,
    language_code: str,
    model_id: str,
) -> list[WordSegment]:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise VoskBackendError("Vosk returned invalid JSON") from exc

    words = []
    for item in data.get("result", []):
        text = str(item.get("word", "")).strip()
        if not text:
            continue
        start_sec = float(item.get("start", 0.0)) + base_start_sec
        end_sec = float(item.get("end", start_sec - base_start_sec))
        end_sec += base_start_sec
        raw_confidence = _clamp(float(item.get("conf", 0.0)))
        words.append(
            WordSegment(
                text=text,
                start_sec=max(0.0, start_sec),
                end_sec=max(start_sec, end_sec),
                confidence=raw_confidence,
                raw_confidence=raw_confidence,
                language_code=language_code,
                model_id=model_id,
            )
        )
    return words


class VoskRecognizer:
    """Loads Vosk models lazily and returns normalized word candidates."""

    def __init__(self, chunk_frames: int = 4000):
        self.chunk_frames = max(256, int(chunk_frames))
        self._vosk = None
        self._models: Dict[str, Any] = {}

    def _load_vosk(self):
        if self._vosk is not None:
            return self._vosk
        try:
            import vosk
        except ImportError as exc:
            raise VoskBackendError(
                "Vosk is not installed in the worker Python environment"
            ) from exc
        self._vosk = vosk
        return vosk

    def _load_model(self, spec: VoskModelSpec):
        spec.validate()
        model_path = Path(spec.model_path).expanduser()
        if not model_path.is_dir():
            if spec.archive_path:
                try:
                    model_path = ensure_vosk_model_directory(
                        model_path,
                        spec.archive_path,
                        archive_sha256=spec.archive_sha256,
                    )
                except ModelAssetError as exc:
                    raise VoskBackendError(str(exc)) from exc
            else:
                raise VoskBackendError(
                    f"Vosk model directory does not exist: {model_path}"
                )
        cache_key = str(model_path.resolve())
        if cache_key not in self._models:
            vosk = self._load_vosk()
            try:
                with _vosk_model_argument(model_path) as model_argument:
                    self._models[cache_key] = vosk.Model(model_argument)
            except Exception as exc:  # Vosk exposes backend-specific errors.
                raise VoskBackendError(
                    f"failed to load Vosk model: {model_path}"
                ) from exc
        return self._models[cache_key]

    def recognize_wav(
        self,
        audio_path: str,
        spec: VoskModelSpec,
        *,
        segment_id: str = "segment-0001",
        start_sec: float = 0.0,
        end_sec: Optional[float] = None,
    ) -> RecognitionCandidate:
        """Recognize one PCM WAV region with one language model.

        The first worker contract accepts PCM WAV with 16-bit samples. Stereo
        input is downmixed to mono. MP3 and other containers belong in the
        preprocessing layer and are deliberately not hidden here.
        """

        if start_sec < 0.0:
            raise ValueError("start_sec must be non-negative")
        audio_file = Path(audio_path).expanduser()
        if not audio_file.is_file():
            raise VoskBackendError(f"audio file does not exist: {audio_file}")

        model = self._load_model(spec)
        vosk = self._load_vosk()
        words = []

        try:
            with wave.open(str(audio_file), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                total_frames = wav_file.getnframes()
                if wav_file.getcomptype() != "NONE":
                    raise VoskBackendError("audio must be an uncompressed PCM WAV")
                if sample_width != 2:
                    raise VoskBackendError(
                        "audio must use 16-bit PCM samples for the first worker"
                    )
                if channels < 1 or sample_rate <= 0:
                    raise VoskBackendError("audio has invalid channel or rate data")

                actual_start_frame = min(
                    total_frames,
                    max(0, int(round(start_sec * sample_rate))),
                )
                if end_sec is None:
                    actual_end_frame = total_frames
                else:
                    actual_end_frame = min(
                        total_frames,
                        max(
                            actual_start_frame,
                            int(round(end_sec * sample_rate)),
                        ),
                    )
                frame_count = actual_end_frame - actual_start_frame
                if frame_count <= 0:
                    raise VoskBackendError("audio segment is empty")

                actual_start_sec = actual_start_frame / sample_rate
                actual_end_sec = actual_end_frame / sample_rate
                recognizer = vosk.KaldiRecognizer(model, sample_rate)
                if hasattr(recognizer, "SetWords"):
                    recognizer.SetWords(True)
                wav_file.setpos(actual_start_frame)
                remaining = frame_count
                while remaining > 0:
                    read_frames = min(self.chunk_frames, remaining)
                    raw = wav_file.readframes(read_frames)
                    if channels > 1:
                        raw = _downmix_s16(raw, channels)
                    if recognizer.AcceptWaveform(raw):
                        words.extend(
                            _read_vosk_result(
                                recognizer.Result(),
                                base_start_sec=actual_start_sec,
                                language_code=spec.language_code,
                                model_id=spec.model_id,
                            )
                        )
                    remaining -= read_frames
                words.extend(
                    _read_vosk_result(
                        recognizer.FinalResult(),
                        base_start_sec=actual_start_sec,
                        language_code=spec.language_code,
                        model_id=spec.model_id,
                    )
                )
        except wave.Error as exc:
            raise VoskBackendError(f"invalid WAV file: {audio_file}") from exc

        return RecognitionCandidate(
            candidate_id=f"{segment_id}:{spec.model_id}",
            segment_id=segment_id,
            language_code=spec.language_code,
            model_id=spec.model_id,
            start_sec=actual_start_sec,
            end_sec=actual_end_sec,
            words=words,
        )
