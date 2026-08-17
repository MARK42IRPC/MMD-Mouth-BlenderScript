import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from mmd_mouth.recognition.model_assets import (
    _commit_extracted_model,
    ModelAssetError,
    ensure_vosk_model_directory,
    is_vosk_model_directory,
)


REQUIRED_FILES = (
    "am/final.mdl",
    "conf/mfcc.conf",
    "conf/model.conf",
    "graph/HCLr.fst",
    "graph/Gr.fst",
)


class ModelAssetTests(unittest.TestCase):
    def test_archive_is_verified_and_extracted_once(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            archive_path = root / "model.zip"
            with ZipFile(archive_path, "w") as archive:
                for relative in REQUIRED_FILES:
                    archive.writestr(f"test-model/{relative}", relative)
            checksum = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            target = root / "models" / "test-model"

            first = ensure_vosk_model_directory(
                target,
                archive_path,
                archive_sha256=checksum,
            )
            second = ensure_vosk_model_directory(
                target,
                root / "missing.zip",
            )

            self.assertEqual(first, second)
            self.assertTrue(is_vosk_model_directory(target))

    def test_archive_rejects_parent_traversal(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            archive_path = root / "unsafe.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", "unsafe")

            with self.assertRaises(ModelAssetError):
                ensure_vosk_model_directory(
                    root / "models" / "test-model",
                    archive_path,
                )

    def test_windows_commit_retries_a_transient_directory_lock(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            extracted = root / "extracted"
            target = root / "target"
            extracted.mkdir()
            original_replace = Path.replace
            attempts = 0

            def flaky_replace(path, destination):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError(5, "transient lock")
                return original_replace(path, destination)

            with (
                patch("mmd_mouth.recognition.model_assets.os.name", "nt"),
                patch.object(Path, "replace", flaky_replace),
                patch("mmd_mouth.recognition.model_assets.time.sleep"),
            ):
                _commit_extracted_model(extracted, target)

            self.assertEqual(attempts, 2)
            self.assertTrue(target.is_dir())


if __name__ == "__main__":
    unittest.main()
