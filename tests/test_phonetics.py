import unittest

from mmd_mouth.core.phonetics import features_for_ipa


class PhoneticsTests(unittest.TestCase):
    def test_bilabial_consonants_create_full_closure(self):
        for symbol in ("p", "b", "m"):
            with self.subTest(symbol=symbol):
                features = features_for_ipa(symbol)
                self.assertEqual(features.articulation_class, "BILABIAL_CLOSURE")
                self.assertEqual(features.viseme_id, "CLOSED")
                self.assertEqual(features.close_strength, 1.0)
                self.assertEqual(features.vowel_suppression, 1.0)

    def test_labiodental_consonants_are_partial_closure(self):
        features = features_for_ipa("v")

        self.assertEqual(features.articulation_class, "LABIODENTAL")
        self.assertEqual(features.viseme_id, "CLOSED")
        self.assertGreater(features.close_strength, 0.0)
        self.assertLess(features.close_strength, 1.0)

    def test_glides_target_vowel_transitions(self):
        self.assertEqual(features_for_ipa("j").viseme_id, "I")
        self.assertEqual(features_for_ipa("w").viseme_id, "U")

    def test_aspiration_is_ignored_for_visual_consonant_class(self):
        features = features_for_ipa("pʰ")

        self.assertEqual(features.canonical_ipa, "p")
        self.assertEqual(features.articulation_class, "BILABIAL_CLOSURE")
        self.assertEqual(features.close_strength, 1.0)

    def test_unknown_symbols_are_safe(self):
        features = features_for_ipa("ʕ")

        self.assertEqual(features.articulation_class, "UNKNOWN")
        self.assertEqual(features.viseme_id, "REST")


if __name__ == "__main__":
    unittest.main()
