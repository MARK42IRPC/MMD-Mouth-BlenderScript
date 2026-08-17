"""Bundled Vosk model catalog and safe first-run extraction."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import os
import shutil
import tempfile
import time
from typing import Iterable
from zipfile import BadZipFile, ZipFile


class ModelAssetError(RuntimeError):
    """Raised when a bundled model cannot be verified or prepared."""


@dataclass(frozen=True)
class BundledModelAsset:
    model_id: str
    language_code: str
    display_name: str
    archive_name: str
    archive_sha256: str


BUNDLED_MODEL_ASSETS = (
    BundledModelAsset(
        model_id="vosk-model-small-cn-0.22",
        language_code="zh-CN",
        display_name="Chinese (Small)",
        archive_name="vosk-model-small-cn-0.22.zip",
        archive_sha256=(
            "3af8b0e7e0f835ae9d414ce5df580237"
            "a3cfb08d586c9fbbb0f7ff29ad5b14ba"
        ),
    ),
    BundledModelAsset(
        model_id="vosk-model-small-ja-0.22",
        language_code="ja-JP",
        display_name="Japanese (Small)",
        archive_name="vosk-model-small-ja-0.22.zip",
        archive_sha256=(
            "efa092d280153a77615e9e0c7d7283e"
            "93e600de3d19d3bec686c57ef19d52eac"
        ),
    ),
    BundledModelAsset(
        model_id="vosk-model-small-en-us-0.15",
        language_code="en-US",
        display_name="English US (Small)",
        archive_name="vosk-model-small-en-us-0.15.zip",
        archive_sha256=(
            "30f26242c4eb449f948e42cb302dd7a6"
            "86cb29a3423a8367f99ff41780942498"
        ),
    ),
)

_ASSET_BY_ID = {asset.model_id: asset for asset in BUNDLED_MODEL_ASSETS}


def bundled_asset(model_id: str) -> BundledModelAsset | None:
    return _ASSET_BY_ID.get(model_id)


def is_vosk_model_directory(path: Path) -> bool:
    required = (
        Path("am") / "final.mdl",
        Path("conf") / "mfcc.conf",
        Path("conf") / "model.conf",
        Path("graph") / "HCLr.fst",
        Path("graph") / "Gr.fst",
    )
    return path.is_dir() and all((path / relative).is_file() for relative in required)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_members(names: Iterable[str]) -> None:
    for name in names:
        value = PurePosixPath(name.replace("\\", "/"))
        if value.is_absolute() or ".." in value.parts:
            raise ModelAssetError(f"unsafe path in model archive: {name}")
        if value.parts and ":" in value.parts[0]:
            raise ModelAssetError(f"unsafe drive path in model archive: {name}")


def _commit_extracted_model(extracted: Path, target: Path) -> None:
    delay_sec = 0.05
    for attempt in range(8):
        try:
            extracted.replace(target)
            return
        except OSError as exc:
            if is_vosk_model_directory(target):
                return
            is_transient_windows_lock = (
                os.name == "nt"
                and isinstance(exc, PermissionError)
                and not target.exists()
            )
            if not is_transient_windows_lock or attempt == 7:
                raise ModelAssetError(
                    f"could not commit extracted Vosk model: {target}"
                ) from exc
            time.sleep(delay_sec)
            delay_sec *= 2.0


def ensure_vosk_model_directory(
    model_path: str | os.PathLike[str],
    archive_path: str | os.PathLike[str],
    *,
    archive_sha256: str = "",
) -> Path:
    """Return a verified model directory, extracting its bundled ZIP once."""

    target = Path(model_path).expanduser().resolve()
    if is_vosk_model_directory(target):
        return target
    if target.exists():
        raise ModelAssetError(
            f"model target exists but is incomplete: {target}"
        )

    source = Path(archive_path).expanduser().resolve()
    if not source.is_file():
        raise ModelAssetError(f"bundled model archive does not exist: {source}")
    expected_hash = archive_sha256.strip().lower()
    if expected_hash and _sha256(source) != expected_hash:
        raise ModelAssetError(f"bundled model archive checksum failed: {source.name}")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{target.name}-",
            suffix=".extracting",
            dir=str(target.parent),
        )
    )
    try:
        try:
            with ZipFile(source, "r") as archive:
                _safe_members(info.filename for info in archive.infolist())
                archive.extractall(temporary)
        except (BadZipFile, OSError) as exc:
            raise ModelAssetError(
                f"could not extract bundled model archive: {source.name}"
            ) from exc

        candidates = [temporary / target.name]
        candidates.extend(
            child for child in temporary.iterdir() if child.is_dir()
        )
        extracted = next(
            (candidate for candidate in candidates if is_vosk_model_directory(candidate)),
            None,
        )
        if extracted is None:
            raise ModelAssetError(
                f"archive does not contain a valid Vosk model: {source.name}"
            )

        _commit_extracted_model(extracted, target)
        return target
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


__all__ = [
    "BUNDLED_MODEL_ASSETS",
    "BundledModelAsset",
    "ModelAssetError",
    "bundled_asset",
    "ensure_vosk_model_directory",
    "is_vosk_model_directory",
]
