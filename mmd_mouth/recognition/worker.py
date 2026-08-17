"""Command-line worker used by Blender through a JSON job file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import os
import tempfile
from typing import Any, Dict, Sequence

from ..constants import CANDIDATE_SCORING_VERSION, WORKER_PROTOCOL_VERSION
from .pipeline import VoskPipelineError, run_vosk_pipeline
from .scoring import CandidateScoreConfig
from .vosk_backend import VoskModelSpec


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON job: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("job JSON must contain an object")
    return value


def _write_json_atomic(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def _load_score_config(value: Dict[str, Any]) -> CandidateScoreConfig:
    return CandidateScoreConfig(
        version=int(value.get("version", CANDIDATE_SCORING_VERSION)),
        confidence_weight=float(value.get("confidence_weight", 0.70)),
        coverage_weight=float(value.get("coverage_weight", 0.20)),
        presence_weight=float(value.get("presence_weight", 0.10)),
        preferred_language_weight=float(
            value.get("preferred_language_weight", 0.35)
        ),
    )


def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    protocol_version = int(job.get("protocol_version", WORKER_PROTOCOL_VERSION))
    if protocol_version != WORKER_PROTOCOL_VERSION:
        raise ValueError(
            "worker protocol mismatch: "
            f"expected {WORKER_PROTOCOL_VERSION}, got {protocol_version}"
        )
    audio_path = str(job.get("audio_path", ""))
    if not audio_path:
        raise ValueError("job.audio_path is required")
    raw_models = job.get("models", [])
    if not isinstance(raw_models, list) or not raw_models:
        raise ValueError("job.models must be a non-empty list")
    specs = [VoskModelSpec.from_dict(value) for value in raw_models]
    score_config = _load_score_config(job.get("score_config", {}))
    timeline_config = job.get("timeline_config", {})
    if not isinstance(timeline_config, dict):
        raise ValueError("job.timeline_config must be an object")
    result = run_vosk_pipeline(
        audio_path,
        specs,
        segment_id=str(job.get("segment_id", "segment-0001")),
        start_sec=float(job.get("start_sec", 0.0)),
        end_sec=(
            None
            if job.get("end_sec") is None
            else float(job["end_sec"])
        ),
        preferred_language_code=str(
            job.get("requested_language_code", "")
        ),
        attack_ms=float(timeline_config.get("attack_ms", 35.0)),
        release_ms=float(timeline_config.get("release_ms", 45.0)),
        score_config=score_config,
    )
    return {
        "ok": True,
        "protocol_version": WORKER_PROTOCOL_VERSION,
        "document": result.document.to_dict(),
        "errors": result.errors,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--health",
        action="store_true",
        help="return the worker protocol without loading a model",
    )
    args = parser.parse_args(argv)

    if args.health:
        print(
            json.dumps(
                {
                    "ok": True,
                    "protocol_version": WORKER_PROTOCOL_VERSION,
                    "worker": "mmd_mouth.vosk",
                }
            )
        )
        return 0
    if args.job is None or args.output is None:
        parser.error("--job and --output are required unless --health is used")

    try:
        result = run_job(_read_json(args.job))
        _write_json_atomic(args.output, result)
    except (ValueError, VoskPipelineError) as exc:
        error = {"ok": False, "error": str(exc)}
        _write_json_atomic(args.output, error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
