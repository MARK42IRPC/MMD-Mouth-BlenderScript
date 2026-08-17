# Development Guide

## Baseline

The add-on targets Blender 5.2. The validated Windows baseline is Blender
5.2.0 LTS, build `fbe6228777e7`. Blender 5.2 uses Python 3.13, while the
packaged recognition worker uses Python 3.11; binary speech dependencies must
remain outside Blender's Python process.

Current persisted contract versions:

| Contract | Version |
| --- | --- |
| Add-on | `0.4.2` |
| RNA / JSON schema | `5` |
| Viseme timeline | `4` |
| Worker protocol | `2` |
| Candidate scoring | `2` |
| IPA normalization | `1` |

## Architecture

```text
Blender UI / operators
  -> Scene.mmd_mouth RNA
  -> hidden one-shot worker process
  -> Vosk candidates and calibrated selection
  -> language G2P and canonical IPA
  -> consonant-aware viseme events
  -> Blender 5.2 Action / NLA / driver output
```

`mmd_mouth.core` is Blender-independent and must remain testable with normal
Python. `mmd_mouth.recognition` may import optional worker dependencies lazily.
Only Blender integration modules import `bpy`.

Recognition never touches Blender data. The worker writes JSON, and a Blender
timer imports that JSON on the main thread. `Generate Mouth` can request a bake
after import; `Recognize Only` stops at the editable RNA timeline.

The worker accepts uncompressed 16-bit PCM WAV. When another Blender-supported
audio format is selected, `mmd_mouth.transcode_audio` or the generation path
uses Blender's built-in `aud` decoder/writer to create a cached mono PCM WAV.
The source file is never overwritten, and the converted path is persisted on
the clip so later recognition and VSE preview updates reuse it.

## Language And Timeline

The worker preserves every selected Vosk word interval and converts text with:

| Language | G2P implementation |
| --- | --- |
| `zh-CN` | pypinyin to canonical IPA |
| `ja-JP` | OpenJTalk vanilla phonemes to canonical IPA |
| `en-US` | CMUdict ARPAbet to canonical IPA |

Phone intervals are estimated inside each Vosk word interval. This is weighted
G2P alignment, not acoustic forced alignment. Raw words, source phones, and
canonical phones remain persisted so a later aligner can replace timings
without changing the animation contract.

The timeline evaluates `REST/CLOSED/A/I/U/E/O`. Bilabial `p`, `b`, and `m`
create high-priority `CLOSED` envelopes; `REST` and `CLOSED` attenuate all
overlapping vowel channels. If a model has no explicit closed-mouth shape key,
vowel suppression returns it to the neutral Basis shape.

Each clip selects an easing mode and transition-in/out times. `LINEAR`
preserves the compact direct attack/release behavior. The non-linear modes
apply their curve to real wall-clock windows around every event, extend
adjacent vowel windows across their shared boundary, and normalize overlapping
vowel weights so a transition does not accumulate extra mouth opening.
`CLOSED` and `REST` remain suppression layers. Recognized event bounds stay raw
and editable; transition windows are added only while generating Blender
curves.

The panel's expandable mouth timeline is the editable generation input. Event
changes are sorted by start time and mark an already recognized/baked clip
stale. `Regenerate` intentionally uses the existing event collection even when
the clip is stale; `Generate` may start recognition when recognition inputs are
stale.

## Blender Animation

Blender 5.2 Actions are layered and slotted. Do not use the removed
`Action.fcurves` API. Curves are created with
`action.fcurve_ensure_for_datablock(...)` while the Action is assigned to its
animated ID, then the Action is placed as an NLA strip at `clip.start_frame`.

`BAKE` creates curves directly on shape-key data. `DRIVER` creates one
profile-owned Empty, animates its custom properties, and connects shape keys
with simple variable drivers. Driver expressions do not invoke add-on Python,
so saved files evaluate without the recognition runtime.

Every generated Action and NLA strip is recorded in `clip.assets`. Cleanup may
remove only those recorded assets. A shape key with an unrelated user driver is
an error and must never be overwritten. The last driver clip removes its owned
controller and drivers; clips that still share that controller keep it alive.

Selecting clip audio creates one top-level VSE Sound Strip tagged with the
clip's stable ID. Path, start frame, source offset, duration, and preview volume
updates synchronize that owned strip. Clip deletion removes only matching
tagged strips; display names are never treated as ownership. Changing a clip's
start frame also moves its recorded NLA strips.

Undo and redo do not restore Python subprocess state. Runtime handlers cancel
the active worker before history changes, then reconcile orphaned `RUNNING`
flags afterward. Operator availability is based on the actual in-process task,
not only persisted RNA flags.

## Bundled Runtime And Models

The install archive contains:

```text
mmd_mouth/
  runtime/mmd_mouth_worker/
  resources/vosk/
    vosk-model-small-cn-0.22.zip
    vosk-model-small-ja-0.22.zip
    vosk-model-small-en-us-0.15.zip
```

Model archives have pinned SHA-256 values. Extraction rejects absolute paths,
parent traversal, invalid model layouts, and checksum mismatches. It extracts
to a temporary sibling directory and atomically moves a valid model into the
Blender user data directory.

OpenJTalk's own dictionary is bundled. The optional 207 MB Sudachi core
dictionary is intentionally excluded because mouth G2P uses OpenJTalk's vanilla
path. `packaging-hooks/hook-sudachipy.py` prevents the generic PyInstaller hook
from collecting that unused dictionary.

## Build

```powershell
py -3.11 -m venv .venv-worker
.\.venv-worker\Scripts\python.exe -m pip install -r requirements-worker.txt
.\build_worker.ps1
.\build_addon.ps1 -SkipWorkerBuild
```

`build_worker.ps1` replaces only `build-worker` output and the add-on-owned
`mmd_mouth/runtime/mmd_mouth_worker` directory. `build_addon.ps1` stages source,
worker, and model ZIPs into `dist-addon/MMDmouth-0.4.2.zip`.

## Verification

```powershell
ruff check mmd_mouth tests packaging-hooks
.\.venv-worker\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv-worker\Scripts\python.exe tests\packaged_worker_languages.py
$blender = $env:MMD_MOUTH_BLENDER
if (-not $blender) { throw "Set MMD_MOUTH_BLENDER to the Blender 5.2 executable" }
& $blender --background --factory-startup --python tests\blender_animation_smoke.py
& $blender --background --factory-startup --python tests\blender_clip_lifecycle.py
& $blender --background --factory-startup --python tests\blender_undo_runtime.py
& $blender --background --factory-startup --python tests\blender_generate_e2e.py
```

The packaged-language test exercises all three model ZIPs and all three G2P
paths. The Blender E2E test covers bundled worker discovery, first-use model
extraction, asynchronous recognition, RNA import, binding scan, and NLA bake.

## Versioning And Migration

`SCHEMA_VERSION` covers persisted RNA and JSON meanings. `TIMELINE_VERSION`
covers event-generation behavior. `WORKER_PROTOCOL_VERSION` rejects worker and
add-on binaries that cannot exchange the same result shape.

The clip-level transition and easing fields are output-sampling options. They
do not change the worker protocol, and migration supplies defaults for existing
clips. Regenerating applies the selected curve and timing.

`mmd_mouth.migrations` assigns missing stable IDs and marks old populated
timelines `STALE`. It does not reinterpret old events as current output. A
stale clip is recognized again on the next `Generate Mouth` action.

## Current Boundaries

- Vosk timestamps are word-level; phoneme timing is estimated by weighted G2P.
- `Auto Compare` selects one model for one whole segment. True code-switching
  requires a language router that creates several segments first.
- Blender-supported source formats are converted to cached mono 16-bit PCM WAV
  before the worker reads them.
- Binding generation currently targets shape keys; custom RNA targets remain
  represented in the schema but are not generated by the first adapter.
