import unittest
from unittest.mock import patch

from mmd_mouth.core.schema import RecognitionCandidate, WordSegment
from mmd_mouth.recognition.pipeline import run_vosk_pipeline
from mmd_mouth.recognition.scoring import (
    CandidateScoreConfig,
    score_candidate,
    select_candidates,
)
from mmd_mouth.recognition.vosk_backend import VoskModelSpec


def make_candidate(model_id, confidence, text="hello", segment_id="segment-1"):
    return RecognitionCandidate(
        candidate_id=f"{segment_id}:{model_id}",
        segment_id=segment_id,
        language_code="en-US",
        model_id=model_id,
        start_sec=0.0,
        end_sec=1.0,
        words=[
            WordSegment(
                text=text,
                start_sec=0.1,
                end_sec=0.8,
                confidence=confidence,
                raw_confidence=confidence,
            )
        ],
    )


class RecognitionTests(unittest.TestCase):
    def test_model_spec_round_trips(self):
        spec = VoskModelSpec.from_dict(
            {
                "model_id": "cn",
                "language_code": "zh-CN",
                "model_path": "D:/models/cn",
                "calibration_bias": 0.2,
                "calibration_temperature": 1.4,
            }
        )

        self.assertEqual(spec.to_dict()["language_code"], "zh-CN")
        self.assertEqual(spec.to_dict()["calibration_temperature"], 1.4)

    def test_selection_keeps_loser_and_marks_winner(self):
        winner = make_candidate("cn", 0.9)
        loser = make_candidate("ja", 0.4)

        selected = select_candidates([winner, loser])

        self.assertEqual([item.model_id for item in selected], ["cn"])
        self.assertTrue(winner.selected)
        self.assertFalse(loser.selected)
        self.assertGreater(winner.selection_score, loser.selection_score)

    def test_score_uses_model_calibration(self):
        candidate = make_candidate("model", 0.5)

        score_candidate(
            candidate,
            calibration_bias=2.0,
            calibration_temperature=1.0,
            config=CandidateScoreConfig(),
        )

        self.assertGreater(candidate.normalized_score, 0.5)
        self.assertGreater(candidate.words[0].confidence, 0.5)
        self.assertEqual(candidate.words[0].raw_confidence, 0.5)

    def test_preferred_language_breaks_cross_model_confidence_tie(self):
        chinese = make_candidate("cn", 0.76, text="你好")
        chinese.language_code = "zh-CN"
        english = make_candidate("en", 0.80, text="hello")
        english.language_code = "en-US"

        selected = select_candidates(
            [chinese, english],
            preferred_language_code="zh-CN",
        )

        self.assertEqual([item.model_id for item in selected], ["cn"])
        self.assertTrue(chinese.selected)
        self.assertFalse(english.selected)

    def test_auto_selection_records_cross_language_warning(self):
        class FakeRecognizer:
            def recognize_wav(self, audio_path, spec, **kwargs):
                candidate = make_candidate(
                    spec.model_id,
                    0.8,
                    segment_id=kwargs["segment_id"],
                )
                candidate.language_code = spec.language_code
                return candidate

        specs = [
            VoskModelSpec("cn", "zh-CN", "D:/models/cn"),
            VoskModelSpec("en", "en-US", "D:/models/en"),
        ]
        with patch(
            "mmd_mouth.recognition.pipeline.VoskRecognizer",
            FakeRecognizer,
        ):
            result = run_vosk_pipeline(
                "D:/audio/sample.wav",
                specs,
                preferred_language_code="AUTO",
            )

        self.assertIn("selection_warning", result.document.metadata)

    def test_pipeline_merges_selected_candidate_document(self):
        class FakeRecognizer:
            def recognize_wav(self, audio_path, spec, **kwargs):
                return make_candidate(
                    spec.model_id,
                    0.9 if spec.model_id == "cn" else 0.3,
                    segment_id=kwargs["segment_id"],
                )

        specs = [
            VoskModelSpec("cn", "zh-CN", "D:/models/cn"),
            VoskModelSpec("ja", "ja-JP", "D:/models/ja"),
        ]

        with patch(
            "mmd_mouth.recognition.pipeline.VoskRecognizer",
            FakeRecognizer,
        ):
            result = run_vosk_pipeline("D:/audio/sample.wav", specs)

        self.assertEqual(result.document.selected_candidate_id, "segment-0001:cn")
        self.assertEqual(result.document.language_segments[0].model_id, "cn")
        self.assertEqual(len(result.document.candidates), 2)


if __name__ == "__main__":
    unittest.main()
