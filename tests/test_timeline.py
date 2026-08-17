import unittest

from mmd_mouth.core.phonetics import features_for_ipa
from mmd_mouth.core.schema import PhonemeSegment
from mmd_mouth.core.timeline import (
    build_viseme_events,
    evaluate_viseme_channels,
    sample_viseme_channels,
)


def make_phoneme(symbol, start_sec, end_sec):
    features = features_for_ipa(symbol)
    return PhonemeSegment(
        phoneme=features.canonical_ipa,
        source_phoneme=symbol,
        start_sec=start_sec,
        end_sec=end_sec,
        phoneme_type=features.phoneme_type,
        place=features.place,
        manner=features.manner,
        voicing=features.voicing,
        articulation_class=features.articulation_class,
        viseme_id=features.viseme_id,
        close_strength=features.close_strength,
        vowel_suppression=features.vowel_suppression,
        confidence=1.0,
        language_code="zh-CN",
    )


class TimelineTests(unittest.TestCase):
    def test_bilabial_closure_suppresses_following_vowel_opening(self):
        events = build_viseme_events(
            [make_phoneme("m", 0.0, 0.1), make_phoneme("a", 0.1, 0.4)]
        )

        during_closure = evaluate_viseme_channels(events, 0.08)
        after_release = evaluate_viseme_channels(events, 0.2)

        self.assertGreater(during_closure["CLOSED"], 0.9)
        self.assertEqual(during_closure["A"], 0.0)
        self.assertGreater(after_release["A"], 0.9)
        self.assertEqual(after_release["CLOSED"], 0.0)

    def test_frame_sampling_keeps_neutral_boundaries(self):
        events = build_viseme_events([make_phoneme("a", 0.1, 0.4)])

        sampled = sample_viseme_channels(events, duration_sec=0.5, fps=30.0)

        self.assertEqual(sampled["A"][0][1], 0.0)
        self.assertEqual(sampled["A"][-1][1], 0.0)
        self.assertLess(len(sampled["A"]), 16)

    def test_non_linear_mode_crossfades_adjacent_vowels(self):
        events = build_viseme_events(
            [make_phoneme("a", 0.0, 0.2), make_phoneme("i", 0.2, 0.4)]
        )

        values = evaluate_viseme_channels(
            events,
            0.19,
            attack_ms=50.0,
            release_ms=50.0,
            easing_mode="SMOOTHSTEP",
        )

        self.assertGreater(values["A"], 0.0)
        self.assertGreater(values["I"], 0.0)
        self.assertAlmostEqual(
            values["A"] + values["I"],
            1.0,
            places=6,
        )

    def test_linear_mode_keeps_adjacent_vowels_discrete(self):
        events = build_viseme_events(
            [make_phoneme("a", 0.0, 0.2), make_phoneme("i", 0.2, 0.4)]
        )

        values = evaluate_viseme_channels(
            events,
            0.19,
            attack_ms=50.0,
            release_ms=50.0,
            easing_mode="LINEAR",
        )

        self.assertGreater(values["A"], 0.0)
        self.assertEqual(values["I"], 0.0)

    def test_easing_modes_produce_distinct_transition_curves(self):
        events = build_viseme_events([make_phoneme("a", 0.2, 0.5)])
        values = {
            mode: evaluate_viseme_channels(
                events,
                0.18,
                attack_ms=50.0,
                release_ms=50.0,
                easing_mode=mode,
            )["A"]
            for mode in ("SMOOTHSTEP", "SINE", "EASE_IN", "EASE_OUT")
        }

        self.assertGreater(values["EASE_OUT"], values["SMOOTHSTEP"])
        self.assertGreater(values["SMOOTHSTEP"], values["EASE_IN"])
        self.assertNotAlmostEqual(values["SMOOTHSTEP"], values["SINE"], places=4)

    def test_smooth_transition_is_not_shortened_for_a_short_phone(self):
        events = build_viseme_events([make_phoneme("a", 0.2, 0.22)])

        value = evaluate_viseme_channels(
            events,
            0.15,
            attack_ms=120.0,
            release_ms=120.0,
            easing_mode="SMOOTHSTEP",
        )["A"]

        self.assertGreater(value, 0.0)
        self.assertLess(value, 1.0)

    def test_recognized_events_keep_raw_phone_bounds(self):
        events = build_viseme_events([make_phoneme("m", 0.2, 0.3)])

        self.assertEqual(events[0].start_sec, 0.2)
        self.assertEqual(events[0].end_sec, 0.3)


if __name__ == "__main__":
    unittest.main()
