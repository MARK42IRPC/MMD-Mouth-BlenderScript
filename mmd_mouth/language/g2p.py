"""Chinese, Japanese, and English text to canonical IPA tokens."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from functools import lru_cache
import io
import re
from typing import Any, Iterable, Sequence

from ..core.phonetics import features_for_ipa
from ..core.schema import PhonemeSegment, WordSegment


class G2PError(RuntimeError):
    """Raised when a requested language adapter is unavailable."""


@dataclass(frozen=True)
class PhoneToken:
    source: str
    ipa: str


_PINYIN_INITIALS = (
    "zh",
    "ch",
    "sh",
    "b",
    "p",
    "m",
    "f",
    "d",
    "t",
    "n",
    "l",
    "g",
    "k",
    "h",
    "j",
    "q",
    "x",
    "r",
    "z",
    "c",
    "s",
)

_PINYIN_INITIAL_IPA = {
    "b": "p",
    "p": "pʰ",
    "m": "m",
    "f": "f",
    "d": "t",
    "t": "tʰ",
    "n": "n",
    "l": "l",
    "g": "k",
    "k": "kʰ",
    "h": "x",
    "j": "tɕ",
    "q": "tɕʰ",
    "x": "ɕ",
    "zh": "tʃ",
    "ch": "tʃʰ",
    "sh": "ʂ",
    "r": "ɻ",
    "z": "ts",
    "c": "tsʰ",
    "s": "s",
}

_PINYIN_FINAL_IPA = {
    "a": ("a",),
    "o": ("o",),
    "e": ("ɤ",),
    "i": ("i",),
    "u": ("u",),
    "v": ("y",),
    "ai": ("a", "i"),
    "ei": ("e", "i"),
    "ao": ("a", "o"),
    "ou": ("o", "u"),
    "an": ("a", "n"),
    "en": ("ə", "n"),
    "ang": ("a", "ŋ"),
    "eng": ("ə", "ŋ"),
    "ong": ("o", "ŋ"),
    "ia": ("j", "a"),
    "ie": ("j", "e"),
    "iao": ("j", "a", "o"),
    "iu": ("j", "o", "u"),
    "ian": ("j", "e", "n"),
    "in": ("i", "n"),
    "iang": ("j", "a", "ŋ"),
    "ing": ("i", "ŋ"),
    "iong": ("j", "o", "ŋ"),
    "ua": ("w", "a"),
    "uo": ("w", "o"),
    "uai": ("w", "a", "i"),
    "ui": ("w", "e", "i"),
    "uan": ("w", "a", "n"),
    "un": ("w", "ə", "n"),
    "uang": ("w", "a", "ŋ"),
    "ueng": ("w", "ə", "ŋ"),
    "ve": ("y", "e"),
    "van": ("y", "e", "n"),
    "vn": ("y", "n"),
    "er": ("ə", "r"),
}

_PINYIN_Y_W = {
    "yi": ("i",),
    "ya": ("j", "a"),
    "yo": ("j", "o"),
    "ye": ("j", "e"),
    "yai": ("j", "a", "i"),
    "yao": ("j", "a", "o"),
    "you": ("j", "o", "u"),
    "yan": ("j", "a", "n"),
    "yin": ("i", "n"),
    "yang": ("j", "a", "ŋ"),
    "ying": ("i", "ŋ"),
    "yong": ("j", "o", "ŋ"),
    "yu": ("y",),
    "yue": ("y", "e"),
    "yuan": ("y", "e", "n"),
    "yun": ("y", "n"),
    "wu": ("u",),
    "wa": ("w", "a"),
    "wo": ("w", "o"),
    "wai": ("w", "a", "i"),
    "wei": ("w", "e", "i"),
    "wan": ("w", "a", "n"),
    "wen": ("w", "ə", "n"),
    "wang": ("w", "a", "ŋ"),
    "weng": ("w", "ə", "ŋ"),
}

_ARPABET_IPA = {
    "AA": ("ɑ",),
    "AE": ("æ",),
    "AH": ("ə",),
    "AO": ("ɔ",),
    "AW": ("a", "u"),
    "AY": ("a", "i"),
    "EH": ("ɛ",),
    "ER": ("ɜ", "ɹ"),
    "EY": ("e", "i"),
    "IH": ("ɪ",),
    "IY": ("i",),
    "OW": ("o", "u"),
    "OY": ("o", "i"),
    "UH": ("ʊ",),
    "UW": ("u",),
    "B": ("b",),
    "CH": ("tʃ",),
    "D": ("d",),
    "DH": ("ð",),
    "F": ("f",),
    "G": ("g",),
    "HH": ("h",),
    "JH": ("dʒ",),
    "K": ("k",),
    "L": ("l",),
    "M": ("m",),
    "N": ("n",),
    "NG": ("ŋ",),
    "P": ("p",),
    "R": ("ɹ",),
    "S": ("s",),
    "SH": ("ʃ",),
    "T": ("t",),
    "TH": ("θ",),
    "V": ("v",),
    "W": ("w",),
    "Y": ("j",),
    "Z": ("z",),
    "ZH": ("ʒ",),
}

_ENGLISH_FALLBACK = {
    "sh": ("ʃ",),
    "ch": ("tʃ",),
    "th": ("θ",),
    "ph": ("f",),
    "ng": ("ŋ",),
    "qu": ("k", "w"),
    "a": ("æ",),
    "e": ("e",),
    "i": ("ɪ",),
    "o": ("o",),
    "u": ("ʌ",),
    "b": ("b",),
    "c": ("k",),
    "d": ("d",),
    "f": ("f",),
    "g": ("g",),
    "h": ("h",),
    "j": ("dʒ",),
    "k": ("k",),
    "l": ("l",),
    "m": ("m",),
    "n": ("n",),
    "p": ("p",),
    "q": ("k",),
    "r": ("ɹ",),
    "s": ("s",),
    "t": ("t",),
    "v": ("v",),
    "w": ("w",),
    "x": ("k", "s"),
    "y": ("j",),
    "z": ("z",),
}

_JAPANESE_IPA = {
    "a": "a",
    "i": "i",
    "u": "ɯ",
    "e": "e",
    "o": "o",
    "k": "k",
    "g": "g",
    "s": "s",
    "sh": "ɕ",
    "z": "z",
    "j": "dʑ",
    "t": "t",
    "ch": "tɕ",
    "ts": "ts",
    "d": "d",
    "n": "n",
    "h": "h",
    "f": "ɸ",
    "b": "b",
    "p": "p",
    "m": "m",
    "y": "j",
    "r": "ɾ",
    "w": "w",
    "v": "v",
    "cl": "ʔ",
}


def _tokens(source: str, symbols: Iterable[str]) -> list[PhoneToken]:
    return [PhoneToken(source=source, ipa=symbol) for symbol in symbols if symbol]


@lru_cache(maxsize=4096)
def _chinese_tokens(text: str) -> tuple[PhoneToken, ...]:
    try:
        from pypinyin import Style, lazy_pinyin
    except ImportError as exc:
        raise G2PError("Chinese G2P dependency pypinyin is unavailable") from exc

    syllables = lazy_pinyin(text, style=Style.NORMAL, errors="ignore")
    result: list[PhoneToken] = []
    for raw_syllable in syllables:
        syllable = re.sub(r"[1-5]$", "", raw_syllable.lower()).replace("ü", "v")
        if not syllable:
            continue
        direct = _PINYIN_Y_W.get(syllable)
        if direct is not None:
            result.extend(_tokens(syllable, direct))
            continue
        initial = next(
            (value for value in _PINYIN_INITIALS if syllable.startswith(value)),
            "",
        )
        final = syllable[len(initial) :]
        if initial in {"j", "q", "x"} and final.startswith("u"):
            final = "v" + final[1:]
        if initial in {"zh", "ch", "sh", "r", "z", "c", "s"} and final == "i":
            final_symbols = ("ɯ",)
        else:
            final_symbols = _PINYIN_FINAL_IPA.get(final, ())
        if initial:
            result.extend(_tokens(initial, (_PINYIN_INITIAL_IPA[initial],)))
        result.extend(_tokens(final or syllable, final_symbols))
    return tuple(result)


@lru_cache(maxsize=1)
def _cmu_dictionary() -> dict[str, list[list[str]]]:
    try:
        import cmudict
    except ImportError as exc:
        raise G2PError("English G2P dependency cmudict is unavailable") from exc
    return cmudict.dict()


def _english_fallback(word: str) -> list[PhoneToken]:
    result: list[PhoneToken] = []
    index = 0
    while index < len(word):
        pair = word[index : index + 2]
        source = pair if pair in _ENGLISH_FALLBACK else word[index]
        symbols = _ENGLISH_FALLBACK.get(source, ())
        result.extend(_tokens(source, symbols))
        index += len(source)
    return result


@lru_cache(maxsize=4096)
def _english_tokens(text: str) -> tuple[PhoneToken, ...]:
    words = re.findall(r"[a-z']+", text.lower())
    result: list[PhoneToken] = []
    dictionary = _cmu_dictionary()
    for word in words:
        pronunciations = dictionary.get(word)
        if not pronunciations and word.endswith("'s"):
            pronunciations = dictionary.get(word[:-2])
        if not pronunciations:
            result.extend(_english_fallback(word))
            continue
        for arpabet in pronunciations[0]:
            base = re.sub(r"\d", "", arpabet)
            result.extend(_tokens(arpabet, _ARPABET_IPA.get(base, ())))
    return tuple(result)


@lru_cache(maxsize=1)
def _pyopenjtalk() -> Any:
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            import pyopenjtalk
    except ImportError as exc:
        raise G2PError(
            "Japanese G2P dependency pyopenjtalk-plus is unavailable: "
            f"{exc}"
        ) from exc
    return pyopenjtalk


@lru_cache(maxsize=4096)
def _japanese_tokens(text: str) -> tuple[PhoneToken, ...]:
    phones = _pyopenjtalk().g2p(
        text,
        kana=False,
        use_vanilla=True,
        use_sudachi_kanji_yomi=False,
        predict_nani=False,
    ).split()
    result: list[PhoneToken] = []
    for index, raw_phone in enumerate(phones):
        if raw_phone in {"sil", "pau"}:
            continue
        if raw_phone == "N":
            following = phones[index + 1] if index + 1 < len(phones) else ""
            ipa = "m" if following in {"p", "b", "m"} else "n"
        else:
            ipa = _JAPANESE_IPA.get(raw_phone.lower(), raw_phone.lower())
        result.append(PhoneToken(source=raw_phone, ipa=ipa))
    return tuple(result)


def pronunciation_tokens(text: str, language_code: str) -> list[PhoneToken]:
    family = language_code.strip().replace("_", "-").lower().split("-", 1)[0]
    if family == "zh":
        return list(_chinese_tokens(text))
    if family == "ja":
        return list(_japanese_tokens(text))
    if family == "en":
        return list(_english_tokens(text))
    return _english_fallback(text.lower())


def _phone_weight(token: PhoneToken) -> float:
    features = features_for_ipa(token.ipa)
    if features.phoneme_type == "VOWEL":
        return 1.6
    if features.articulation_class == "BILABIAL_CLOSURE":
        return 0.55
    return 0.75


def _align_word(
    word: WordSegment,
    tokens: Sequence[PhoneToken],
    language_code: str,
) -> list[PhonemeSegment]:
    if not tokens or word.end_sec <= word.start_sec:
        return []
    weights = [_phone_weight(token) for token in tokens]
    total_weight = sum(weights)
    duration = word.end_sec - word.start_sec
    cursor = word.start_sec
    segments: list[PhonemeSegment] = []
    for index, (token, weight) in enumerate(zip(tokens, weights)):
        end_sec = (
            word.end_sec
            if index == len(tokens) - 1
            else cursor + duration * weight / total_weight
        )
        features = features_for_ipa(token.ipa)
        segments.append(
            PhonemeSegment(
                phoneme=features.canonical_ipa,
                source_phoneme=token.source,
                start_sec=cursor,
                end_sec=max(cursor, end_sec),
                source_text=word.text,
                confidence=word.confidence,
                phoneme_type=features.phoneme_type,
                place=features.place,
                manner=features.manner,
                voicing=features.voicing,
                articulation_class=features.articulation_class,
                viseme_id=features.viseme_id,
                close_strength=features.close_strength,
                vowel_suppression=features.vowel_suppression,
                language_code=language_code,
            )
        )
        cursor = end_sec
    return segments


def phonemize_words(
    words: Sequence[WordSegment],
    *,
    default_language_code: str,
) -> list[PhonemeSegment]:
    phonemes: list[PhonemeSegment] = []
    for word in words:
        language_code = word.language_code or default_language_code
        tokens = pronunciation_tokens(word.text, language_code)
        phonemes.extend(_align_word(word, tokens, language_code))
    return sorted(phonemes, key=lambda value: (value.start_sec, value.end_sec))


__all__ = ["G2PError", "PhoneToken", "phonemize_words", "pronunciation_tokens"]
