"""Vosk multi-model recognition pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from ..core.schema import LanguageSegment, RecognitionCandidate, RecognitionDocument
from ..core.timeline import build_viseme_events
from ..language.g2p import G2PError, phonemize_words
from .scoring import CandidateScoreConfig, select_candidates
from .vosk_backend import VoskBackendError, VoskModelSpec, VoskRecognizer


class VoskPipelineError(RuntimeError):
    """Raised when no configured Vosk candidate can be produced."""


@dataclass
class RecognitionBatchResult:
    document: RecognitionDocument
    errors: List[Dict[str, str]] = field(default_factory=list)


def _merge_words(winners: Iterable[RecognitionCandidate]):
    words = []
    for candidate in winners:
        words.extend(candidate.words)
    return sorted(words, key=lambda word: (word.start_sec, word.end_sec))


def run_vosk_pipeline(
    audio_path: str,
    model_specs: Sequence[VoskModelSpec],
    *,
    segment_id: str = "segment-0001",
    start_sec: float = 0.0,
    end_sec: Optional[float] = None,
    preferred_language_code: str = "",
    attack_ms: float = 35.0,
    release_ms: float = 45.0,
    score_config: CandidateScoreConfig | None = None,
) -> RecognitionBatchResult:
    """Run configured models on one shared audio segment and select winners.

    The preferred language is a user-supplied prior.  It is intentionally
    separate from Vosk's per-word confidence because those values are not
    calibrated across independent language models.
    """

    score_config = score_config or CandidateScoreConfig()
    recognizer = VoskRecognizer()
    candidates: List[RecognitionCandidate] = []
    errors: List[Dict[str, str]] = []
    calibration_map = {}
    priority_map = {}

    for spec in model_specs:
        if not spec.enabled:
            continue
        calibration_map[spec.model_id] = (
            spec.calibration_bias,
            spec.calibration_temperature,
        )
        priority_map[spec.model_id] = spec.priority
        try:
            candidates.append(
                recognizer.recognize_wav(
                    audio_path,
                    spec,
                    segment_id=segment_id,
                    start_sec=start_sec,
                    end_sec=end_sec,
                )
            )
        except (VoskBackendError, ValueError) as exc:
            errors.append(
                {
                    "model_id": spec.model_id,
                    "language_code": spec.language_code,
                    "error": str(exc),
                }
            )

    if not candidates:
        detail = "; ".join(error["error"] for error in errors)
        raise VoskPipelineError(
            "no Vosk candidate completed successfully"
            + (f": {detail}" if detail else "")
        )

    winners = select_candidates(
        candidates,
        calibrations=calibration_map,
        priorities=priority_map,
        preferred_language_code=preferred_language_code,
        config=score_config,
    )
    words = _merge_words(winners)
    phonemes = []
    events = []
    timeline_error = ""
    try:
        default_language = winners[0].language_code if len(winners) == 1 else "mixed"
        phonemes = phonemize_words(
            words,
            default_language_code=default_language,
        )
        events = build_viseme_events(
            phonemes,
            attack_ms=attack_ms,
            release_ms=release_ms,
        )
    except (G2PError, RuntimeError, ValueError) as exc:
        timeline_error = str(exc)
        errors.append(
            {
                "model_id": winners[0].model_id if len(winners) == 1 else "mixed",
                "language_code": (
                    winners[0].language_code if len(winners) == 1 else "mixed"
                ),
                "stage": "G2P",
                "error": timeline_error,
            }
        )
    language_segments = [
        LanguageSegment(
            start_sec=winner.start_sec,
            end_sec=winner.end_sec,
            language_code=winner.language_code,
            model_id=winner.model_id,
            confidence=winner.selection_score,
            source="MODEL_SCORE",
            candidate_id=winner.candidate_id,
        )
        for winner in winners
    ]
    is_single = len(winners) == 1
    normalized_preference = (
        preferred_language_code.strip().replace("_", "-").lower()
    )
    has_language_preference = normalized_preference not in {
        "",
        "auto",
        "mixed",
        "und",
    }
    metadata = {"errors": errors}
    metadata["timeline_config"] = {
        "attack_ms": attack_ms,
        "release_ms": release_ms,
    }
    if timeline_error:
        metadata["timeline_error"] = timeline_error
    language_codes = {candidate.language_code for candidate in candidates}
    if len(language_codes) > 1 and not has_language_preference:
        metadata["selection_warning"] = (
            "Vosk confidence is not calibrated across languages; "
            "set a preferred language or use a model filter."
        )
    if has_language_preference:
        metadata["preferred_language_code"] = preferred_language_code

    document = RecognitionDocument(
        backend_id="vosk",
        model_id=winners[0].model_id if is_single else "mixed",
        language_code=winners[0].language_code if is_single else "mixed",
        audio_duration_sec=max(
            0.0,
            max(candidate.end_sec for candidate in candidates) - start_sec,
        ),
        selected_candidate_id=winners[0].candidate_id if is_single else "",
        candidate_scoring_version=score_config.version,
        candidates=list(candidates),
        words=words,
        phonemes=phonemes,
        events=events,
        language_segments=language_segments,
        metadata=metadata,
    )
    document.validate()
    return RecognitionBatchResult(document=document, errors=errors)
