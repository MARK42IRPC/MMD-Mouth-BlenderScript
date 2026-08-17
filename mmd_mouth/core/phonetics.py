"""Canonical IPA symbols and articulatory features for mouth animation."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Dict, Iterable


@dataclass(frozen=True)
class PhonemeFeatures:
    """Visual and articulatory metadata for one normalized phoneme."""

    source_symbol: str
    canonical_ipa: str
    phoneme_type: str
    place: str
    manner: str
    voicing: str
    articulation_class: str
    viseme_id: str
    close_strength: float = 0.0
    vowel_suppression: float = 0.0


_PHONEME_MAP: Dict[str, PhonemeFeatures] = {}


def _register(
    symbols: Iterable[str],
    *,
    phoneme_type: str,
    place: str,
    manner: str,
    voicing: str,
    articulation_class: str,
    viseme_id: str,
    close_strength: float = 0.0,
    vowel_suppression: float = 0.0,
) -> None:
    for symbol in symbols:
        _PHONEME_MAP[symbol] = PhonemeFeatures(
            source_symbol=symbol,
            canonical_ipa=symbol,
            phoneme_type=phoneme_type,
            place=place,
            manner=manner,
            voicing=voicing,
            articulation_class=articulation_class,
            viseme_id=viseme_id,
            close_strength=close_strength,
            vowel_suppression=vowel_suppression,
        )


_register(
    ("a", "ɑ", "ɐ", "æ", "ʌ"),
    phoneme_type="VOWEL",
    place="VOWEL",
    manner="VOWEL",
    voicing="VOICED",
    articulation_class="VOWEL_A",
    viseme_id="A",
)
_register(
    ("e", "ɛ", "ə", "ɜ", "ɘ"),
    phoneme_type="VOWEL",
    place="VOWEL",
    manner="VOWEL",
    voicing="VOICED",
    articulation_class="VOWEL_E",
    viseme_id="E",
)
_register(
    ("i", "ɪ"),
    phoneme_type="VOWEL",
    place="VOWEL",
    manner="VOWEL",
    voicing="VOICED",
    articulation_class="VOWEL_I",
    viseme_id="I",
)
_register(
    ("o", "ɔ", "ɒ", "ø", "œ"),
    phoneme_type="VOWEL",
    place="VOWEL",
    manner="VOWEL",
    voicing="VOICED",
    articulation_class="VOWEL_O",
    viseme_id="O",
)
_register(
    ("u", "ʊ", "ɯ", "ɤ", "y", "ʏ"),
    phoneme_type="VOWEL",
    place="VOWEL",
    manner="VOWEL",
    voicing="VOICED",
    articulation_class="VOWEL_U",
    viseme_id="U",
)

# Full lip closure. These events suppress nearby vowel opening.
_register(
    ("p",),
    phoneme_type="CONSONANT",
    place="BILABIAL",
    manner="STOP",
    voicing="VOICELESS",
    articulation_class="BILABIAL_CLOSURE",
    viseme_id="CLOSED",
    close_strength=1.0,
    vowel_suppression=1.0,
)
_register(
    ("b",),
    phoneme_type="CONSONANT",
    place="BILABIAL",
    manner="STOP",
    voicing="VOICED",
    articulation_class="BILABIAL_CLOSURE",
    viseme_id="CLOSED",
    close_strength=1.0,
    vowel_suppression=1.0,
)
_register(
    ("m",),
    phoneme_type="CONSONANT",
    place="BILABIAL",
    manner="NASAL",
    voicing="VOICED",
    articulation_class="BILABIAL_CLOSURE",
    viseme_id="CLOSED",
    close_strength=1.0,
    vowel_suppression=1.0,
)

# Partial lip contact. The default mapping is intentionally weaker than a
# bilabial closure because these sounds use the lower lip and upper teeth.
_register(
    ("ɸ",),
    phoneme_type="CONSONANT",
    place="BILABIAL",
    manner="FRICATIVE",
    voicing="VOICELESS",
    articulation_class="BILABIAL_FRICATIVE",
    viseme_id="CLOSED",
    close_strength=0.55,
    vowel_suppression=0.7,
)
_register(
    ("β",),
    phoneme_type="CONSONANT",
    place="BILABIAL",
    manner="FRICATIVE",
    voicing="VOICED",
    articulation_class="BILABIAL_FRICATIVE",
    viseme_id="CLOSED",
    close_strength=0.55,
    vowel_suppression=0.7,
)
_register(
    ("f",),
    phoneme_type="CONSONANT",
    place="LABIODENTAL",
    manner="FRICATIVE",
    voicing="VOICELESS",
    articulation_class="LABIODENTAL",
    viseme_id="CLOSED",
    close_strength=0.35,
    vowel_suppression=0.55,
)
_register(
    ("v",),
    phoneme_type="CONSONANT",
    place="LABIODENTAL",
    manner="FRICATIVE",
    voicing="VOICED",
    articulation_class="LABIODENTAL",
    viseme_id="CLOSED",
    close_strength=0.35,
    vowel_suppression=0.55,
)

_register(
    ("t",),
    phoneme_type="CONSONANT",
    place="ALVEOLAR",
    manner="STOP",
    voicing="VOICELESS",
    articulation_class="ALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.35,
)
_register(
    ("d",),
    phoneme_type="CONSONANT",
    place="ALVEOLAR",
    manner="STOP",
    voicing="VOICED",
    articulation_class="ALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.35,
)
_register(
    ("n",),
    phoneme_type="CONSONANT",
    place="ALVEOLAR",
    manner="NASAL",
    voicing="VOICED",
    articulation_class="ALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.25,
)
_register(
    ("s",),
    phoneme_type="CONSONANT",
    place="ALVEOLAR",
    manner="FRICATIVE",
    voicing="VOICELESS",
    articulation_class="ALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.15,
)
_register(
    ("θ",),
    phoneme_type="CONSONANT",
    place="DENTAL",
    manner="FRICATIVE",
    voicing="VOICELESS",
    articulation_class="DENTAL_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("ð",),
    phoneme_type="CONSONANT",
    place="DENTAL",
    manner="FRICATIVE",
    voicing="VOICED",
    articulation_class="DENTAL_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("z", "l", "ɾ", "r", "ɹ"),
    phoneme_type="CONSONANT",
    place="ALVEOLAR",
    manner="APPROXIMANT",
    voicing="VOICED",
    articulation_class="ALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.15,
)

_register(
    ("ʃ",),
    phoneme_type="CONSONANT",
    place="POSTALVEOLAR",
    manner="FRICATIVE",
    voicing="VOICELESS",
    articulation_class="POSTALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("ʒ",),
    phoneme_type="CONSONANT",
    place="POSTALVEOLAR",
    manner="FRICATIVE",
    voicing="VOICED",
    articulation_class="POSTALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("tʃ",),
    phoneme_type="CONSONANT",
    place="POSTALVEOLAR",
    manner="AFFRICATE",
    voicing="VOICELESS",
    articulation_class="POSTALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("dʒ",),
    phoneme_type="CONSONANT",
    place="POSTALVEOLAR",
    manner="AFFRICATE",
    voicing="VOICED",
    articulation_class="POSTALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("ɕ",),
    phoneme_type="CONSONANT",
    place="PALATAL",
    manner="FRICATIVE",
    voicing="VOICELESS",
    articulation_class="PALATAL_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("tɕ",),
    phoneme_type="CONSONANT",
    place="PALATAL",
    manner="AFFRICATE",
    voicing="VOICELESS",
    articulation_class="PALATAL_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("dʑ",),
    phoneme_type="CONSONANT",
    place="PALATAL",
    manner="AFFRICATE",
    voicing="VOICED",
    articulation_class="PALATAL_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("ɲ",),
    phoneme_type="CONSONANT",
    place="PALATAL",
    manner="NASAL",
    voicing="VOICED",
    articulation_class="PALATAL_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("ʑ",),
    phoneme_type="CONSONANT",
    place="PALATAL",
    manner="FRICATIVE",
    voicing="VOICED",
    articulation_class="PALATAL_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("ts",),
    phoneme_type="CONSONANT",
    place="ALVEOLAR",
    manner="AFFRICATE",
    voicing="VOICELESS",
    articulation_class="ALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("dz",),
    phoneme_type="CONSONANT",
    place="ALVEOLAR",
    manner="AFFRICATE",
    voicing="VOICED",
    articulation_class="ALVEOLAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("ʂ", "ʐ", "ɻ", "ʈ", "ɖ"),
    phoneme_type="CONSONANT",
    place="POSTALVEOLAR",
    manner="APPROXIMANT",
    voicing="UNKNOWN",
    articulation_class="RETROFLEX_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("j",),
    phoneme_type="CONSONANT",
    place="PALATAL",
    manner="APPROXIMANT",
    voicing="VOICED",
    articulation_class="PALATAL_GLIDE",
    viseme_id="I",
)
_register(
    ("k",),
    phoneme_type="CONSONANT",
    place="VELAR",
    manner="STOP",
    voicing="VOICELESS",
    articulation_class="VELAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("g",),
    phoneme_type="CONSONANT",
    place="VELAR",
    manner="STOP",
    voicing="VOICED",
    articulation_class="VELAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("ŋ",),
    phoneme_type="CONSONANT",
    place="VELAR",
    manner="NASAL",
    voicing="VOICED",
    articulation_class="VELAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("x",),
    phoneme_type="CONSONANT",
    place="VELAR",
    manner="FRICATIVE",
    voicing="VOICELESS",
    articulation_class="VELAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("ɣ",),
    phoneme_type="CONSONANT",
    place="VELAR",
    manner="FRICATIVE",
    voicing="VOICED",
    articulation_class="VELAR_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.2,
)
_register(
    ("w",),
    phoneme_type="CONSONANT",
    place="VELAR",
    manner="APPROXIMANT",
    voicing="VOICED",
    articulation_class="LABIAL_GLIDE",
    viseme_id="U",
    close_strength=0.1,
)
_register(
    ("h",),
    phoneme_type="CONSONANT",
    place="GLOTTAL",
    manner="FRICATIVE",
    voicing="VOICELESS",
    articulation_class="GLOTTAL_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.1,
)
_register(
    ("ʔ",),
    phoneme_type="CONSONANT",
    place="GLOTTAL",
    manner="STOP",
    voicing="UNKNOWN",
    articulation_class="GLOTTAL_CONSONANT",
    viseme_id="REST",
    vowel_suppression=0.1,
)


_ALIASES = {
    "ɡ": "g",
    "t͡ʃ": "tʃ",
    "d͡ʒ": "dʒ",
}


def _clean_symbol(symbol: str) -> str:
    cleaned = unicodedata.normalize("NFC", symbol.strip())
    cleaned = cleaned.replace("ˈ", "").replace("ˌ", "")
    cleaned = cleaned.replace("ː", "").replace("ˑ", "")
    cleaned = cleaned.replace("ʰ", "").replace("̚", "")
    cleaned = cleaned.replace("͡", "")
    return _ALIASES.get(cleaned, cleaned)


def features_for_ipa(symbol: str) -> PhonemeFeatures:
    """Return stable visual features for one IPA token.

    Unknown symbols remain visible in ``source_symbol`` and map to REST so a
    new language pack does not crash the animation pipeline.
    """

    cleaned = _clean_symbol(symbol)
    features = _PHONEME_MAP.get(cleaned)
    if features is not None:
        return features
    return PhonemeFeatures(
        source_symbol=symbol,
        canonical_ipa=cleaned,
        phoneme_type="UNKNOWN",
        place="UNKNOWN",
        manner="UNKNOWN",
        voicing="UNKNOWN",
        articulation_class="UNKNOWN",
        viseme_id="REST",
    )


__all__ = ["PhonemeFeatures", "features_for_ipa"]
