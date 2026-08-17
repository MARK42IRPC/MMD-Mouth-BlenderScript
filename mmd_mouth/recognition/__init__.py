"""Speech-recognition backends and candidate selection.

The worker entry point should not eagerly import Blender-process management.
Runtime helpers remain available through lazy attribute access for callers
that used the package-level convenience exports.
"""

from .pipeline import RecognitionBatchResult, VoskPipelineError, run_vosk_pipeline
from .scoring import CandidateScoreConfig, select_candidates
from .vosk_backend import VoskBackendError, VoskModelSpec, VoskRecognizer


def __getattr__(name):
    if name in {
        "WorkerManager",
        "WorkerPollResult",
        "WorkerResolution",
        "WorkerRuntimeError",
        "WorkerTask",
        "probe_worker",
        "resolve_worker",
    }:
        from . import runtime

        return getattr(runtime, name)
    raise AttributeError(name)

__all__ = [
    "CandidateScoreConfig",
    "RecognitionBatchResult",
    "VoskBackendError",
    "VoskModelSpec",
    "VoskPipelineError",
    "VoskRecognizer",
    "WorkerManager",
    "WorkerPollResult",
    "WorkerResolution",
    "WorkerRuntimeError",
    "WorkerTask",
    "probe_worker",
    "resolve_worker",
    "run_vosk_pipeline",
    "select_candidates",
]
