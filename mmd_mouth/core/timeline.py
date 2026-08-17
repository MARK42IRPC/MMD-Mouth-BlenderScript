"""Consonant-aware viseme events and deterministic frame sampling."""

from __future__ import annotations

from math import ceil, cos, isclose, pi
from typing import Dict, Iterable, Mapping, Sequence

from .schema import PhonemeSegment, VisemeEvent


VISEME_CHANNELS = ("REST", "CLOSED", "A", "I", "U", "E", "O")
VOWEL_CHANNELS = ("A", "I", "U", "E", "O")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _ease_progress(progress: float, easing_mode: str) -> float:
    value = _clamp(progress)
    if easing_mode == "SMOOTHSTEP":
        return value * value * (3.0 - 2.0 * value)
    if easing_mode == "SINE":
        return 0.5 - 0.5 * cos(pi * value)
    if easing_mode == "EASE_IN":
        return value * value
    if easing_mode == "EASE_OUT":
        return 1.0 - (1.0 - value) * (1.0 - value)
    return value


def build_viseme_events(
    phonemes: Sequence[PhonemeSegment],
    *,
    attack_ms: float = 35.0,
    release_ms: float = 45.0,
) -> list[VisemeEvent]:
    """Convert aligned IPA phones into vowel, closure, and suppression events."""

    attack_sec = max(0.0, attack_ms) / 1000.0
    release_sec = max(0.0, release_ms) / 1000.0
    events: list[VisemeEvent] = []
    for index, phoneme in enumerate(phonemes):
        common = {
            "confidence": phoneme.confidence,
            "source": "G2P",
            "source_index": index,
            "source_text": phoneme.source_text,
            "phoneme": phoneme.phoneme,
            "language_code": phoneme.language_code,
            "source_phoneme": phoneme.source_phoneme,
            "articulation_class": phoneme.articulation_class,
        }
        if phoneme.viseme_id == "CLOSED" and phoneme.close_strength > 0.0:
            events.append(
                VisemeEvent(
                    viseme_id="CLOSED",
                    start_sec=max(0.0, phoneme.start_sec - attack_sec),
                    end_sec=phoneme.end_sec + release_sec,
                    weight=_clamp(phoneme.close_strength),
                    priority=100,
                    **common,
                )
            )
            continue
        if phoneme.viseme_id in VOWEL_CHANNELS:
            weight = 1.0 if phoneme.phoneme_type == "VOWEL" else 0.65
            events.append(
                VisemeEvent(
                    viseme_id=phoneme.viseme_id,
                    start_sec=phoneme.start_sec,
                    end_sec=phoneme.end_sec,
                    weight=weight,
                    priority=50,
                    **common,
                )
            )
        if phoneme.vowel_suppression > 0.0:
            events.append(
                VisemeEvent(
                    viseme_id="REST",
                    start_sec=phoneme.start_sec,
                    end_sec=phoneme.end_sec,
                    weight=_clamp(phoneme.vowel_suppression),
                    priority=80,
                    **common,
                )
            )
    return sorted(events, key=lambda value: (value.start_sec, -value.priority))


def _envelope(
    event: VisemeEvent,
    time_sec: float,
    *,
    attack_sec: float,
    release_sec: float,
    hold_ratio: float,
    easing_mode: str,
) -> float:
    duration = event.end_sec - event.start_sec
    if duration <= 0.0:
        return event.weight if time_sec == event.start_sec else 0.0

    edge_duration = duration * (1.0 - _clamp(hold_ratio))
    requested_edges = attack_sec + release_sec
    if requested_edges > 0.0 and requested_edges > edge_duration:
        scale = edge_duration / requested_edges
        actual_attack = attack_sec * scale
        actual_release = release_sec * scale
    else:
        actual_attack = min(attack_sec, edge_duration)
        actual_release = min(release_sec, max(0.0, edge_duration - actual_attack))

    # Non-linear vowel envelopes overlap at shared boundaries; closure layers
    # keep their original window so bilabial suppression remains authoritative.
    if easing_mode != "LINEAR" and event.viseme_id in VOWEL_CHANNELS:
        active_start = event.start_sec - actual_attack
        active_end = event.end_sec + actual_release
        if time_sec < active_start or time_sec > active_end:
            return 0.0
        if actual_attack > 0.0 and time_sec < event.start_sec:
            progress = (time_sec - active_start) / actual_attack
            return event.weight * _ease_progress(progress, easing_mode)
        if actual_release > 0.0 and time_sec > event.end_sec:
            progress = (time_sec - event.end_sec) / actual_release
            return event.weight * (1.0 - _ease_progress(progress, easing_mode))
        return event.weight

    if time_sec < event.start_sec or time_sec > event.end_sec:
        return 0.0
    if actual_attack > 0.0 and time_sec < event.start_sec + actual_attack:
        progress = (time_sec - event.start_sec) / actual_attack
        return event.weight * _ease_progress(progress, easing_mode)
    if actual_release > 0.0 and time_sec > event.end_sec - actual_release:
        progress = (event.end_sec - time_sec) / actual_release
        return event.weight * _ease_progress(progress, easing_mode)
    return event.weight


def evaluate_viseme_channels(
    events: Iterable[VisemeEvent],
    time_sec: float,
    *,
    attack_ms: float = 35.0,
    release_ms: float = 45.0,
    hold_ratio: float = 0.55,
    easing_mode: str = "LINEAR",
) -> Dict[str, float]:
    values = {channel: 0.0 for channel in VISEME_CHANNELS}
    attack_sec = max(0.0, attack_ms) / 1000.0
    release_sec = max(0.0, release_ms) / 1000.0
    for event in events:
        if event.viseme_id not in values:
            continue
        value = _clamp(
            _envelope(
                event,
                time_sec,
                attack_sec=attack_sec,
                release_sec=release_sec,
                hold_ratio=hold_ratio,
                easing_mode=easing_mode,
            )
        )
        values[event.viseme_id] = max(values[event.viseme_id], value)

    suppression = max(values["REST"], values["CLOSED"])
    for channel in VOWEL_CHANNELS:
        values[channel] *= 1.0 - suppression
    active_vowels = [
        channel for channel in VOWEL_CHANNELS if values[channel] > 0.0
    ]
    vowel_total = sum(values[channel] for channel in active_vowels)
    if len(active_vowels) > 1 and vowel_total > 0.0:
        for channel in VOWEL_CHANNELS:
            values[channel] /= vowel_total
    return values


def _simplify_samples(samples: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(samples) <= 2:
        return list(samples)
    result = [samples[0]]
    for previous, current, following in zip(samples, samples[1:], samples[2:]):
        first_span = current[0] - previous[0]
        second_span = following[0] - current[0]
        first_slope = 0.0 if first_span == 0.0 else (current[1] - previous[1]) / first_span
        second_slope = (
            0.0 if second_span == 0.0 else (following[1] - current[1]) / second_span
        )
        if not isclose(first_slope, second_slope, abs_tol=1e-5):
            result.append(current)
    result.append(samples[-1])
    return result


def sample_viseme_channels(
    events: Sequence[VisemeEvent],
    *,
    duration_sec: float,
    fps: float,
    attack_ms: float = 35.0,
    release_ms: float = 45.0,
    hold_ratio: float = 0.55,
    easing_mode: str = "LINEAR",
) -> Mapping[str, list[tuple[float, float]]]:
    if fps <= 0.0:
        raise ValueError("effective FPS must be positive")
    timeline_end = max(
        max(0.0, duration_sec),
        max((event.end_sec for event in events), default=0.0),
    )
    frame_count = max(1, int(ceil(timeline_end * fps)))
    sampled = {channel: [] for channel in VISEME_CHANNELS}
    for frame in range(frame_count + 1):
        values = evaluate_viseme_channels(
            events,
            frame / fps,
            attack_ms=attack_ms,
            release_ms=release_ms,
            hold_ratio=hold_ratio,
            easing_mode=easing_mode,
        )
        for channel in VISEME_CHANNELS:
            sampled[channel].append((float(frame), values[channel]))
    return {
        channel: _simplify_samples(values)
        for channel, values in sampled.items()
    }


__all__ = [
    "VISEME_CHANNELS",
    "VOWEL_CHANNELS",
    "build_viseme_events",
    "evaluate_viseme_channels",
    "sample_viseme_channels",
]
