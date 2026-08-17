import json
import sys
import tempfile
import types
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from mmd_mouth.recognition.vosk_backend import (
    VoskModelSpec,
    VoskRecognizer,
    _vosk_model_argument,
)


class FakeModel:
    def __init__(self, path):
        self.path = path


class FakeRecognizer:
    def __init__(self, model, sample_rate):
        self.model = model
        self.sample_rate = sample_rate
        self.words_enabled = False

    def SetWords(self, enabled):
        self.words_enabled = enabled

    def AcceptWaveform(self, raw):
        return False

    def FinalResult(self):
        return json.dumps(
            {
                "text": "test",
                "result": [
                    {
                        "conf": 0.84,
                        "start": 0.01,
                        "end": 0.05,
                        "word": "test",
                    }
                ],
            }
        )


class VoskBackendTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows path behavior")
    def test_unicode_model_path_uses_ascii_native_argument(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            model_path = Path(temporary_dir) / "模型目录"
            model_path.mkdir()
            previous = Path.cwd()

            with _vosk_model_argument(model_path) as argument:
                self.assertEqual(argument, ".")
                self.assertEqual(Path.cwd(), model_path.resolve())

            self.assertEqual(Path.cwd(), previous)

    def test_wav_region_and_word_timestamps_are_normalized(self):
        fake_vosk = types.SimpleNamespace(
            Model=FakeModel,
            KaldiRecognizer=FakeRecognizer,
        )
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            audio_path = root / "sample.wav"
            model_path = root / "model"
            model_path.mkdir()
            with wave.open(str(audio_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(b"\x00\x00" * 3200)

            spec = VoskModelSpec(
                model_id="test-model",
                language_code="en-US",
                model_path=str(model_path),
            )
            with patch.dict(sys.modules, {"vosk": fake_vosk}):
                candidate = VoskRecognizer().recognize_wav(
                    str(audio_path),
                    spec,
                    start_sec=0.1,
                    end_sec=0.15,
                )

        self.assertEqual(candidate.language_code, "en-US")
        self.assertEqual(candidate.words[0].text, "test")
        self.assertAlmostEqual(candidate.words[0].start_sec, 0.11, places=4)
        self.assertAlmostEqual(candidate.words[0].end_sec, 0.15, places=4)
        self.assertEqual(candidate.words[0].raw_confidence, 0.84)


if __name__ == "__main__":
    unittest.main()
