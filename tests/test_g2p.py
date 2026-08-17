import unittest

from mmd_mouth.core.schema import WordSegment
from mmd_mouth.language.g2p import phonemize_words, pronunciation_tokens


class G2PTests(unittest.TestCase):
    def test_chinese_preserves_bilabial_consonants(self):
        tokens = pronunciation_tokens("妈妈", "zh-CN")

        self.assertEqual([token.ipa for token in tokens], ["m", "a", "m", "a"])

    def test_english_uses_cmu_pronunciation(self):
        tokens = pronunciation_tokens("map", "en-US")

        self.assertEqual([token.ipa for token in tokens], ["m", "æ", "p"])

    def test_japanese_uses_openjtalk_phones(self):
        tokens = pronunciation_tokens("まま", "ja-JP")

        self.assertEqual([token.ipa for token in tokens], ["m", "a", "m", "a"])

    def test_word_interval_is_distributed_across_phones(self):
        word = WordSegment(
            text="妈",
            start_sec=1.0,
            end_sec=1.5,
            confidence=0.8,
            raw_confidence=0.8,
            language_code="zh-CN",
        )

        phonemes = phonemize_words([word], default_language_code="zh-CN")

        self.assertEqual(phonemes[0].phoneme, "m")
        self.assertEqual(phonemes[0].viseme_id, "CLOSED")
        self.assertEqual(phonemes[0].start_sec, 1.0)
        self.assertAlmostEqual(phonemes[-1].end_sec, 1.5)


if __name__ == "__main__":
    unittest.main()
