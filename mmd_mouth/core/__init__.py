"""Blender-independent domain objects for MMD Mouth."""

from .schema import (
    LanguageSegment,
    PhonemeSegment,
    RecognitionCandidate,
    RecognitionDocument,
    TimelineDocument,
    VisemeEvent,
    WordSegment,
)
from .phonetics import PhonemeFeatures, features_for_ipa
from .timeline import (
    VISEME_CHANNELS,
    VOWEL_CHANNELS,
    build_viseme_events,
    evaluate_viseme_channels,
    sample_viseme_channels,
)

__all__ = [
    "LanguageSegment",
    "PhonemeSegment",
    "RecognitionCandidate",
    "RecognitionDocument",
    "TimelineDocument",
    "VisemeEvent",
    "WordSegment",
    "PhonemeFeatures",
    "features_for_ipa",
    "VISEME_CHANNELS",
    "VOWEL_CHANNELS",
    "build_viseme_events",
    "evaluate_viseme_channels",
    "sample_viseme_channels",
]
