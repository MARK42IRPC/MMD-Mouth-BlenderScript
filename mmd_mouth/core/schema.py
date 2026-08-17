"""Serializable, Blender-independent speech and viseme data structures."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from ..constants import (
    CANDIDATE_SCORING_VERSION,
    IPA_NORMALIZATION_VERSION,
    SCHEMA_VERSION,
    TIMELINE_VERSION,
)

@dataclass
class WordSegment:
    text: str
    start_sec: float
    end_sec: float
    confidence: float = 0.0
    raw_confidence: float = 0.0
    language_code: str = ""
    model_id: str = ""

    def validate(self) -> None:
        if self.start_sec < 0.0:
            raise ValueError("word start_sec must be non-negative")
        if self.end_sec < self.start_sec:
            raise ValueError("word end_sec must not precede start_sec")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("word confidence must be between 0 and 1")
        if not 0.0 <= self.raw_confidence <= 1.0:
            raise ValueError("word raw_confidence must be between 0 and 1")


@dataclass
class RecognitionCandidate:
    candidate_id: str
    segment_id: str
    language_code: str
    model_id: str
    start_sec: float
    end_sec: float
    raw_score: float = 0.0
    normalized_score: float = 0.0
    selection_score: float = 0.0
    selected: bool = False
    words: List[WordSegment] = field(default_factory=list)
    cache_path: str = ""

    def validate(self) -> None:
        if self.start_sec < 0.0:
            raise ValueError("candidate start_sec must be non-negative")
        if self.end_sec < self.start_sec:
            raise ValueError("candidate end_sec must not precede start_sec")
        if not self.language_code:
            raise ValueError("candidate language_code is required")
        if not self.model_id:
            raise ValueError("candidate model_id is required")
        if not 0.0 <= self.normalized_score <= 1.0:
            raise ValueError("candidate normalized_score must be between 0 and 1")
        if not 0.0 <= self.selection_score <= 1.0:
            raise ValueError("candidate selection_score must be between 0 and 1")
        for word in self.words:
            word.validate()


@dataclass
class PhonemeSegment:
    phoneme: str
    start_sec: float
    end_sec: float
    source_text: str = ""
    confidence: float = 0.0
    source_phoneme: str = ""
    phoneme_type: str = "UNKNOWN"
    place: str = "UNKNOWN"
    manner: str = "UNKNOWN"
    voicing: str = "UNKNOWN"
    articulation_class: str = ""
    viseme_id: str = "REST"
    close_strength: float = 0.0
    vowel_suppression: float = 0.0
    language_code: str = ""

    def validate(self) -> None:
        if self.start_sec < 0.0:
            raise ValueError("phoneme start_sec must be non-negative")
        if self.end_sec < self.start_sec:
            raise ValueError("phoneme end_sec must not precede start_sec")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("phoneme confidence must be between 0 and 1")
        if not 0.0 <= self.close_strength <= 1.0:
            raise ValueError("phoneme close_strength must be between 0 and 1")
        if not 0.0 <= self.vowel_suppression <= 1.0:
            raise ValueError("phoneme vowel_suppression must be between 0 and 1")


@dataclass
class LanguageSegment:
    start_sec: float
    end_sec: float
    language_code: str
    model_id: str = ""
    confidence: float = 0.0
    source: str = "CLIP_DEFAULT"
    candidate_id: str = ""

    def validate(self) -> None:
        if self.start_sec < 0.0:
            raise ValueError("language start_sec must be non-negative")
        if self.end_sec < self.start_sec:
            raise ValueError("language end_sec must not precede start_sec")
        if not self.language_code:
            raise ValueError("language_code is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("language confidence must be between 0 and 1")


@dataclass
class VisemeEvent:
    viseme_id: str
    start_sec: float
    end_sec: float
    weight: float = 1.0
    confidence: float = 0.0
    source: str = "G2P"
    source_index: int = -1
    source_text: str = ""
    phoneme: str = ""
    language_code: str = ""
    source_phoneme: str = ""
    articulation_class: str = ""
    priority: int = 0

    def validate(self) -> None:
        if self.start_sec < 0.0:
            raise ValueError("viseme start_sec must be non-negative")
        if self.end_sec < self.start_sec:
            raise ValueError("viseme end_sec must not precede start_sec")
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError("viseme weight must be between 0 and 1")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("viseme confidence must be between 0 and 1")


@dataclass
class RecognitionDocument:
    backend_id: str
    model_id: str
    language_code: str
    timebase: str = "seconds"
    audio_duration_sec: float = 0.0
    selected_candidate_id: str = ""
    candidate_scoring_version: int = CANDIDATE_SCORING_VERSION
    candidates: List[RecognitionCandidate] = field(default_factory=list)
    words: List[WordSegment] = field(default_factory=list)
    phonemes: List[PhonemeSegment] = field(default_factory=list)
    events: List[VisemeEvent] = field(default_factory=list)
    language_segments: List[LanguageSegment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> None:
        if not self.backend_id:
            raise ValueError("backend_id is required")
        if not self.model_id:
            raise ValueError("model_id is required")
        if not self.language_code:
            raise ValueError("language_code is required")
        if self.timebase != "seconds":
            raise ValueError("only the seconds timebase is supported")
        if self.audio_duration_sec < 0.0:
            raise ValueError("audio_duration_sec must be non-negative")
        for candidate in self.candidates:
            candidate.validate()
        for word in self.words:
            word.validate()
        for phoneme in self.phonemes:
            phoneme.validate()
        for event in self.events:
            event.validate()
        for language_segment in self.language_segments:
            language_segment.validate()

        language_starts = [
            segment.start_sec for segment in self.language_segments
        ]
        if language_starts != sorted(language_starts):
            raise ValueError("language_segments must be sorted by start_sec")

        if self.selected_candidate_id and not any(
            candidate.candidate_id == self.selected_candidate_id
            for candidate in self.candidates
        ):
            raise ValueError("selected_candidate_id does not reference a candidate")

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)


@dataclass
class TimelineDocument:
    backend_id: str
    model_id: str
    language_code: str
    timebase: str = "seconds"
    audio_duration_sec: float = 0.0
    phonemes: List[PhonemeSegment] = field(default_factory=list)
    events: List[VisemeEvent] = field(default_factory=list)
    timeline_version: int = TIMELINE_VERSION
    ipa_normalization_version: int = IPA_NORMALIZATION_VERSION
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def validate(self) -> None:
        if not self.backend_id:
            raise ValueError("backend_id is required")
        if not self.model_id:
            raise ValueError("model_id is required")
        if not self.language_code:
            raise ValueError("language_code is required")
        if self.timebase != "seconds":
            raise ValueError("only the seconds timebase is supported")
        if self.audio_duration_sec < 0.0:
            raise ValueError("audio_duration_sec must be non-negative")
        for phoneme in self.phonemes:
            phoneme.validate()
        for event in self.events:
            event.validate()

        starts = [event.start_sec for event in self.events]
        if starts != sorted(starts):
            raise ValueError("events must be sorted by start_sec")

    def to_dict(self) -> Dict[str, Any]:
        self.validate()
        return asdict(self)
