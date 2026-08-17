"""Cross-model candidate scoring and selection."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, Iterable, Mapping, Sequence, Tuple

from ..constants import CANDIDATE_SCORING_VERSION
from ..core.schema import RecognitionCandidate


@dataclass(frozen=True)
class CandidateScoreConfig:
    version: int = CANDIDATE_SCORING_VERSION
    confidence_weight: float = 0.70
    coverage_weight: float = 0.20
    presence_weight: float = 0.10
    preferred_language_weight: float = 0.35

    def validate(self) -> None:
        weights = (
            self.confidence_weight,
            self.coverage_weight,
            self.presence_weight,
        )
        if any(weight < 0.0 for weight in weights):
            raise ValueError("candidate score weights must be non-negative")
        if not math.isclose(sum(weights), 1.0, abs_tol=1e-6):
            raise ValueError("candidate score weights must sum to 1")
        if not 0.0 <= self.preferred_language_weight <= 1.0:
            raise ValueError("preferred language weight must be between 0 and 1")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _calibrate(raw: float, bias: float, temperature: float) -> float:
    temperature = max(1e-6, temperature)
    probability = _clamp(raw)
    epsilon = 1e-5
    probability = max(epsilon, min(1.0 - epsilon, probability))
    logit = math.log(probability / (1.0 - probability))
    calibrated = 1.0 / (1.0 + math.exp(-((logit + bias) / temperature)))
    return _clamp(calibrated)


def _language_match_score(
    candidate_language_code: str,
    preferred_language_code: str,
) -> float | None:
    """Return an optional language prior without treating AUTO as a language."""

    preferred = preferred_language_code.strip().replace("_", "-").lower()
    if not preferred or preferred in {"auto", "mixed", "und"}:
        return None
    candidate = candidate_language_code.strip().replace("_", "-").lower()
    if not candidate:
        return 0.0
    if candidate == preferred:
        return 1.0
    if candidate.split("-", 1)[0] == preferred.split("-", 1)[0]:
        return 0.8
    return 0.0


def _union_duration(intervals: Iterable[Tuple[float, float]]) -> float:
    ordered = sorted((start, end) for start, end in intervals if end > start)
    if not ordered:
        return 0.0
    total = 0.0
    current_start, current_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
            continue
        total += current_end - current_start
        current_start, current_end = start, end
    return total + current_end - current_start


def score_candidate(
    candidate: RecognitionCandidate,
    *,
    calibration_bias: float = 0.0,
    calibration_temperature: float = 1.0,
    preferred_language_code: str = "",
    config: CandidateScoreConfig | None = None,
) -> RecognitionCandidate:
    """Populate raw, normalized, and final selection scores in place."""

    config = config or CandidateScoreConfig()
    config.validate()
    raw_values = [word.raw_confidence for word in candidate.words]
    if raw_values:
        durations = [
            max(0.0, word.end_sec - word.start_sec)
            for word in candidate.words
        ]
        total_duration = sum(durations)
        if total_duration > 0.0:
            raw_score = sum(
                raw * duration
                for raw, duration in zip(raw_values, durations)
            ) / total_duration
            normalized_score = sum(
                _calibrate(raw, calibration_bias, calibration_temperature)
                * duration
                for raw, duration in zip(raw_values, durations)
            ) / total_duration
        else:
            raw_score = sum(raw_values) / len(raw_values)
            normalized_score = sum(
                _calibrate(raw, calibration_bias, calibration_temperature)
                for raw in raw_values
            ) / len(raw_values)
    else:
        raw_score = 0.0
        normalized_score = 0.0

    segment_duration = max(0.0, candidate.end_sec - candidate.start_sec)
    word_coverage = 0.0
    if segment_duration > 0.0:
        word_coverage = _clamp(
            _union_duration(
                (
                    max(candidate.start_sec, word.start_sec),
                    min(candidate.end_sec, word.end_sec),
                )
                for word in candidate.words
            )
            / segment_duration
        )
    text_presence = 1.0 if candidate.words else 0.0

    candidate.raw_score = _clamp(raw_score)
    candidate.normalized_score = _clamp(normalized_score)
    base_selection_score = _clamp(
        config.confidence_weight * candidate.normalized_score
        + config.coverage_weight * word_coverage
        + config.presence_weight * text_presence
    )
    language_match = _language_match_score(
        candidate.language_code,
        preferred_language_code,
    )
    if language_match is None:
        candidate.selection_score = base_selection_score
    else:
        language_weight = config.preferred_language_weight
        candidate.selection_score = _clamp(
            (1.0 - language_weight) * base_selection_score
            + language_weight * language_match
        )
    for word in candidate.words:
        word.confidence = _calibrate(
            word.raw_confidence,
            calibration_bias,
            calibration_temperature,
        )
    return candidate


def select_candidates(
    candidates: Sequence[RecognitionCandidate],
    *,
    calibrations: Mapping[str, Tuple[float, float]] | None = None,
    priorities: Mapping[str, int] | None = None,
    preferred_language_code: str = "",
    config: CandidateScoreConfig | None = None,
) -> list[RecognitionCandidate]:
    """Score candidates and select one winner for each segment.

    ``calibrations`` maps model ID to ``(bias, temperature)``. All candidates
    remain in the input collection; only their ``selected`` flag changes.
    """

    config = config or CandidateScoreConfig()
    config.validate()
    calibrations = calibrations or {}
    priorities = priorities or {}
    grouped: Dict[str, list[RecognitionCandidate]] = {}
    for candidate in candidates:
        bias, temperature = calibrations.get(candidate.model_id, (0.0, 1.0))
        score_candidate(
            candidate,
            calibration_bias=bias,
            calibration_temperature=temperature,
            preferred_language_code=preferred_language_code,
            config=config,
        )
        candidate.selected = False
        grouped.setdefault(candidate.segment_id, []).append(candidate)

    winners = []
    for group in grouped.values():
        winner = max(
            group,
            key=lambda item: (
                item.selection_score,
                item.normalized_score,
                item.raw_score,
                priorities.get(item.model_id, 0),
            ),
        )
        winner.selected = True
        winners.append(winner)
    return sorted(winners, key=lambda item: item.start_sec)
