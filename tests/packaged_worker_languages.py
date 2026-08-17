"""Exercise all bundled model and G2P paths through the packaged worker."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
WORKER = (
    ROOT
    / "mmd_mouth"
    / "runtime"
    / "mmd_mouth_worker"
    / "mmd_mouth_worker.exe"
)
AUDIO = ROOT / "zh_vo_MAIN_YHX_2_7.wav"
CACHE = ROOT / "cache" / "packaged-languages"
MODELS = (
    (
        "vosk-model-small-cn-0.22",
        "zh-CN",
        "3af8b0e7e0f835ae9d414ce5df580237a3cfb08d586c9fbbb0f7ff29ad5b14ba",
    ),
    (
        "vosk-model-small-ja-0.22",
        "ja-JP",
        "efa092d280153a77615e9e0c7d7283e93e600de3d19d3bec686c57ef19d52eac",
    ),
    (
        "vosk-model-small-en-us-0.15",
        "en-US",
        "30f26242c4eb449f948e42cb302dd7a686cb29a3423a8367f99ff41780942498",
    ),
)


def run_model(model_id: str, language_code: str, checksum: str) -> dict:
    job_path = CACHE / "jobs" / f"{model_id}.json"
    output_path = CACHE / "results" / f"{model_id}.json"
    job_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    job = {
        "protocol_version": 2,
        "audio_path": str(AUDIO),
        "segment_id": f"packaged:{model_id}",
        "requested_language_code": language_code,
        "models": [
            {
                "model_id": model_id,
                "language_code": language_code,
                "model_path": str(CACHE / "models" / model_id),
                "archive_path": str(ROOT / f"{model_id}.zip"),
                "archive_sha256": checksum,
            }
        ],
    }
    job_path.write_text(
        json.dumps(job, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [str(WORKER), "--job", str(job_path), "--output", str(output_path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{model_id} failed with {completed.returncode}: {completed.stderr}"
        )
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    document = payload["document"]
    if document["schema_version"] != 5 or payload["protocol_version"] != 2:
        raise AssertionError(f"{model_id} returned an incompatible contract")
    if not document["words"]:
        raise AssertionError(f"{model_id} recognized no words from the fixture")
    if not document["phonemes"] or not document["events"]:
        raise AssertionError(f"{model_id} did not run its G2P timeline")
    return document


def main() -> None:
    if not WORKER.is_file():
        raise FileNotFoundError(WORKER)
    summaries = []
    for model_id, language_code, checksum in MODELS:
        document = run_model(model_id, language_code, checksum)
        summaries.append(
            {
                "model": model_id,
                "words": len(document["words"]),
                "phonemes": len(document["phonemes"]),
                "events": len(document["events"]),
                "closed": sum(
                    event["viseme_id"] == "CLOSED"
                    for event in document["events"]
                ),
            }
        )
    print(json.dumps(summaries, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"PACKAGED_LANGUAGE_TEST_ERROR: {exc}", file=sys.stderr)
        raise
