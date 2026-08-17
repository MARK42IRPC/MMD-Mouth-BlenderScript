import unittest

from mmd_mouth.core.schema import (
    LanguageSegment,
    RecognitionCandidate,
    RecognitionDocument,
    TimelineDocument,
    VisemeEvent,
)


class TimelineSchemaTests(unittest.TestCase):
    def test_timeline_serializes_with_seconds_timebase(self):
        document = TimelineDocument(
            backend_id="vosk",
            model_id="vosk-model-small-cn-0.22",
            language_code="zh-CN",
            events=[
                VisemeEvent(
                    viseme_id="A",
                    start_sec=0.1,
                    end_sec=0.2,
                    weight=0.8,
                    confidence=0.9,
                )
            ],
        )

        result = document.to_dict()

        self.assertEqual(result["timebase"], "seconds")
        self.assertEqual(result["events"][0]["viseme_id"], "A")

    def test_events_must_be_sorted(self):
        document = TimelineDocument(
            backend_id="vosk",
            model_id="model",
            language_code="ja-JP",
            events=[
                VisemeEvent("I", 0.4, 0.5),
                VisemeEvent("A", 0.1, 0.2),
            ],
        )

        with self.assertRaises(ValueError):
            document.validate()

    def test_invalid_event_weight_is_rejected(self):
        document = TimelineDocument(
            backend_id="vosk",
            model_id="model",
            language_code="en-US",
            events=[VisemeEvent("O", 0.0, 0.1, weight=1.1)],
        )

        with self.assertRaises(ValueError):
            document.validate()

    def test_recognition_document_keeps_language_segments(self):
        document = RecognitionDocument(
            backend_id="vosk",
            model_id="vosk-model-small-cn-0.22",
            language_code="zh-CN",
            language_segments=[
                LanguageSegment(
                    start_sec=0.0,
                    end_sec=1.0,
                    language_code="zh-CN",
                    model_id="vosk-model-small-cn-0.22",
                )
            ],
        )

        result = document.to_dict()

        self.assertEqual(result["language_segments"][0]["language_code"], "zh-CN")

    def test_recognition_document_keeps_candidate_scores(self):
        candidate = RecognitionCandidate(
            candidate_id="candidate-1",
            segment_id="segment-1",
            language_code="ja-JP",
            model_id="vosk-model-small-ja-0.22",
            start_sec=0.0,
            end_sec=1.0,
            raw_score=0.72,
            normalized_score=0.68,
            selection_score=0.70,
            selected=True,
        )
        document = RecognitionDocument(
            backend_id="vosk",
            model_id=candidate.model_id,
            language_code=candidate.language_code,
            selected_candidate_id=candidate.candidate_id,
            candidates=[candidate],
        )

        result = document.to_dict()

        self.assertEqual(result["selected_candidate_id"], "candidate-1")
        self.assertEqual(result["candidates"][0]["selection_score"], 0.70)


if __name__ == "__main__":
    unittest.main()
