# Data Model

## Design goals

The data model separates speech recognition from Blender animation. Recognition produces timestamped candidates, language-specific phonemes, and a versioned viseme timeline, while a model profile describes how viseme channels reach an MMD model.

The persisted hierarchy is:

```text
Scene.mmd_mouth
  +-- model_profiles[]
        +-- bindings[]
        +-- clips[]
        +-- keyframe_assets[]
              +-- recognition_candidates[]
              +-- language_segments[]
              +-- phonemes[]
              +-- events[]
              +-- assets[]
```

All generated records have a stable UUID-like identifier. Blender object names and action names are display labels only and must not be used as durable references.

## Timebase

The canonical timebase is seconds from the beginning of the source audio.

The clip start frame is applied only when generating Blender animation:

```text
effective_fps = scene.render.fps / scene.render.fps_base
frame = start_frame + round((time_sec - audio_offset_sec) * effective_fps)
```

Each generated clip stores the Blender `render.fps` and `render.fps_base` values used for its last bake. Re-running generation samples the persisted seconds timeline at the current effective FPS.

## Scene settings

`Scene.mmd_mouth` is the single add-on-owned root property.

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Persisted RNA schema version |
| `active_model_index` | integer | Selected model profile |
| `default_backend_id` | string | Backend used for new clips; initially `vosk` |
| `default_language_code` | enum | `zh-CN`, `ja-JP`, `en-US`, or whole-clip `AUTO` comparison |
| `default_generation_mode` | enum | Direct shape-key bake or controller-driven output |
| `default_attack_ms` | float | Default transition-in time for new clips |
| `default_release_ms` | float | Default transition-out time for new clips |
| `default_hold_ratio` | float | Default hold portion of a viseme event |
| `cache_directory` | path | Optional external recognition cache directory |
| `worker_mode` | enum | Automatic, packaged, development, or custom worker selection |
| `worker_executable` | path | Optional custom worker executable |
| `worker_python` | path | Optional dedicated development Python |
| `worker_status` | enum | Last worker probe/job state |
| `worker_protocol_version` | integer | Worker contract version |
| `worker_display_name` | string | Resolved worker label |
| `worker_last_check` | string | Last health-check timestamp |
| `worker_last_error` | string | Last worker diagnostic |
| `worker_task_id` | string | Active asynchronous task identifier |
| `show_advanced_runtime` | boolean | Whether advanced worker settings are expanded |
| `show_advanced_models` | boolean | Whether recognition model controls are expanded |
| `model_profiles` | collection | MMD model profiles in this `.blend` |
| `recognizer_models` | collection | Vosk model directories and calibration settings |
| `is_busy` | boolean | UI/process state, not a recognition result |
| `last_error` | string | Last user-visible error |

## Model profile

`MMDMouthModelProfile` represents one model root selected by the user.

| Field | Type | Meaning |
| --- | --- | --- |
| `profile_id` | string | Stable profile identifier |
| `display_name` | string | UI label |
| `root_object` | object pointer | MMD root, armature, or user-selected model object |
| `adapter_id` | string | Binding adapter, initially `generic_shape_key` |
| `binding_status` | enum | `UNSCANNED`, `VALID`, `WARNING`, or `ERROR` |
| `auto_discovered` | boolean | Whether the profile came from model scanning |
| `bindings` | collection | Viseme-to-model target mappings |
| `clips` | collection | Clips belonging to this model |
| `keyframe_assets` | collection | Profile-owned mouth-only Actions or NLA strips from all-keyframe baking |
| `active_clip_index` | integer | Selected clip in the second UI list |

The object pointer is convenient inside one `.blend`, but the profile ID remains the logical identity. If the object is deleted or replaced, the profile enters a warning state instead of silently targeting a different object with the same name.

## Recognizer model registry

`MMDMouthRecognizerModel` stores a local Vosk model that can be used as a candidate for new recognition jobs.

| Field | Type | Meaning |
| --- | --- | --- |
| `model_id` | string | Stable model identifier, normally the directory/model name |
| `display_name` | string | UI label |
| `language_code` | string | Language handled by the model |
| `model_path` | path | Unpacked Vosk model directory |
| `enabled` | boolean | Include this model in candidate jobs |
| `priority` | integer | Tie-break and UI ordering hint |
| `calibration_bias` | float | Per-model confidence calibration bias |
| `calibration_temperature` | float | Per-model confidence calibration temperature |

The registry is configuration only. It does not load Vosk inside Blender. The worker receives these values as `VoskModelSpec` records.

## Binding

`MMDMouthBinding` maps one internal channel to one model target.

The recognition/output shape-key set is exactly:

```text
A, I, U, E, O
```

`REST` and `CLOSED` remain internal timeline suppression channels. They never
target a model shape key or another morph channel.

| Field | Type | Meaning |
| --- | --- | --- |
| `viseme_id` | enum | Internal channel identifier |
| `enabled` | boolean | Whether this mapping is active |
| `target_kind` | enum | `SHAPE_KEY`, `CUSTOM_PROPERTY`, or `DATA_PATH` |
| `target_object` | object pointer | Object containing the target |
| `target_key_name` | string | Shape-key datablock name, when applicable |
| `target_property_name` | string | Custom property name, when applicable |
| `target_data_path` | string | Explicit RNA data path, when applicable |
| `scale` | float | Output multiplier |
| `offset` | float | Output offset |
| `minimum` | float | Output clamp minimum |
| `maximum` | float | Output clamp maximum |
| `invert` | boolean | Invert normalized input before mapping |

The adapter must validate the target before generation. Missing targets, duplicate mappings, locked animation data, and invalid data paths are warnings or errors, never silent fallbacks.

## Clip

`MMDMouthClip` is the user-facing generated fragment.

| Field | Type | Meaning |
| --- | --- | --- |
| `clip_id` | string | Stable clip identifier |
| `display_name` | string | UI label |
| `audio_path` | path | Original audio source |
| `audio_hash` | string | Cache key component for the source audio |
| `transcoded_audio_path` | path | Cached 16-bit PCM WAV used by recognition when needed |
| `audio_transcode_error` | string | Last audio conversion error |
| `start_frame` | integer | Blender frame at which the clip begins |
| `audio_offset_sec` | float | Offset applied within the source audio |
| `duration_sec` | float | Audio or recognized duration |
| `audio_volume` | float | Playback volume of the owned VSE preview strip |
| `audio_strip_name` | string | Last known display name of the owned VSE strip |
| `audio_preview_error` | string | Last non-fatal VSE synchronization error |
| `mouth_strength` | float | Output multiplier applied during animation generation |
| `attack_ms` | float | Transition-in time used when generating this clip |
| `release_ms` | float | Transition-out time used when generating this clip |
| `hold_ratio` | float | Preferred full-strength portion of an event |
| `easing_mode` | enum | Attack/release curve and adjacent-vowel crossfade mode |
| `language_code` | enum | Explicit language or whole-clip `AUTO` model comparison |
| `backend_id` | string | Recognition backend, initially `vosk` |
| `recognizer_model_id` | string | Exact local model identifier |
| `recognizer_model_filter` | string | Optional input model ID filter; blank runs all enabled models |
| `selected_candidate_id` | string | Candidate selected after score normalization |
| `candidate_scoring_version` | integer | Version of the cross-model score policy |
| `status` | enum | Generation lifecycle state |
| `generation_mode` | enum | `BAKE` or `DRIVER` |
| `timeline_version` | integer | Timeline algorithm version |
| `ipa_normalization_version` | integer | Canonical IPA/articulation table version |
| `render_fps` | integer | Blender render FPS snapshot |
| `render_fps_base` | float | Blender render FPS base snapshot |
| `event_count` | integer | Cached event count for UI display |
| `source_transcript` | string | Optional recognized text |
| `cache_path` | path | Optional external JSON cache |
| `last_error` | string | Last generation error for this clip |
| `phoneme_count` | integer | Cached normalized phoneme count |
| `show_timeline` | boolean | Whether the editable mouth timeline is expanded in the panel |
| `active_event_index` | integer | Selected event in the editable timeline list |
| `recognition_candidates` | collection | Candidate results from configured language models |
| `phonemes` | collection | Canonical IPA phoneme timeline |
| `events` | collection | Editable, chronologically sorted viseme timeline |
| `language_segments` | collection | Optional future per-segment language/model routing |
| `assets` | collection | Generated actions, NLA strips, or controllers |

The initial Vosk flow records one selected language segment for the whole clip. A future language router may create several segments, each with its own language and model. A mixed-language clip must never pretend that one language-specific model handled the entire source.

A new clip may exist without recognition data. Generation updates the same record and owns only the animation assets listed in `assets`. Event start/end, viseme, and weight values are editable in the Blender panel; changing them marks a recognized/baked clip stale while preserving the edited timeline.

Selecting `audio_path` creates a VSE Sound Strip tagged with `clip_id`. The tag,
not `audio_strip_name`, establishes ownership. Start frame, source offset,
duration, and preview volume remain synchronized. Deleting a clip removes that
tagged strip together with the clip's recorded animation assets.

## Recognition candidate

`RecognitionCandidate` preserves one model's result for one audio segment. The selector must keep all candidates until the selection decision is complete, and the selected candidate ID must be recorded in the clip or language segment.

| Field | Type | Meaning |
| --- | --- | --- |
| `candidate_id` | string | Stable candidate identifier |
| `segment_id` | string | Audio segment being compared |
| `language_code` | string | Language of the model |
| `model_id` | string | Exact Vosk model ID |
| `start_sec` | float | Segment start |
| `end_sec` | float | Segment end |
| `raw_score` | float | Backend/model score before calibration |
| `normalized_score` | float | Score normalized for comparison |
| `selection_score` | float | Final score used by the selector |
| `selected` | boolean | Whether this candidate won selection |
| `word_count` | integer | Number of recognized words |
| `words` | list | Normalized word segments for this candidate |
| `cache_path` | path | Optional full candidate JSON |

Vosk word `conf` values are model-local signals. They must not be compared directly across Chinese, Japanese, and English models. The selector should retain the raw value, apply a versioned calibration or normalization step, and compare segment-level scores using coverage and language-model validity. A single high-confidence word must not win an entire segment by itself.

## Canonical phoneme segment

`MMDMouthPhonemeSegment` is the language-independent articulation layer between recognition and Viseme generation.

The conversion path is:

```text
Vosk word + timestamp
  -> language-specific G2P
  -> canonical IPA token
  -> articulatory features
  -> close/open and vowel-suppression controls
  -> Viseme events
```

The `phoneme` field stores a visually normalized canonical IPA token. `source_phoneme` stores the language-pack output before normalization, including useful diacritics such as aspiration or length. For example, `pʰ` may normalize to the same visual closure class as `p` while remaining auditable as `pʰ` in `source_phoneme`. IPA is an interchange format; it is not itself a shape-key name.

| Field | Type | Meaning |
| --- | --- | --- |
| `phoneme` | string | Canonical IPA token |
| `source_phoneme` | string | Original language-pack phoneme |
| `start_sec` | float | Phoneme start |
| `end_sec` | float | Phoneme end |
| `phoneme_type` | enum | `VOWEL`, `CONSONANT`, `SILENCE`, or `UNKNOWN` |
| `place` | enum | Bilabial, labiodental, alveolar, velar, and so on |
| `manner` | enum | Stop, nasal, fricative, glide, and so on |
| `voicing` | enum | Voiced, voiceless, or unknown |
| `articulation_class` | string | Stable visual grouping, such as `BILABIAL_CLOSURE` |
| `viseme_id` | enum | Primary output channel or transition target |
| `close_strength` | float | Lip-closure influence from 0 to 1 |
| `vowel_suppression` | float | Local attenuation of overlapping vowel curves |
| `confidence` | float | Confidence after normalization |
| `source_text` | string | Word or syllable that produced the phoneme |
| `language_code` | string | Language pack that produced it |

The initial articulation rules are:

| IPA examples | Articulation class | Default mouth behavior |
| --- | --- | --- |
| `p`, `b`, `m` | `BILABIAL_CLOSURE` | Full `CLOSED`; suppress the nearby vowel and reopen toward the following vowel |
| `ɸ` | `BILABIAL_FRICATIVE` | Partial closure; do not use the full bilabial stop envelope |
| `f`, `v` | `LABIODENTAL` | Weak closure/lip contact and partial vowel suppression |
| `t`, `d`, `n`, `s`, `z`, `l` | `ALVEOLAR_CONSONANT` | No full lip closure; briefly reduce the vowel if needed |
| `k`, `g`, `ŋ` | `VELAR_CONSONANT` | Keep the lip shape mostly from the surrounding vowel |
| `j` | `PALATAL_GLIDE` | Transition toward `I` |
| `w` | `LABIAL_GLIDE` | Transition toward `U` or `O` |

For `p`, `b`, and `m`, the timeline evaluator creates an overlapping `CLOSED` event. It must not simply replace the vowel label for the entire word. The preceding vowel is faded locally before closure, held closed for the consonant interval, and reopened toward the next vowel. This prevents the mouth from remaining open through bilabial consonants. Transition windows are applied during generation rather than baked into the recognized event bounds, so manual timeline edits and transition changes can be regenerated without rerunning recognition.

The raw phoneme interval remains unchanged; envelope expansion and vowel suppression happen in the timeline evaluator so alignment data stays auditable.

## Viseme event

`MMDMouthVisemeEvent` is the editable intermediate representation.

| Field | Type | Meaning |
| --- | --- | --- |
| `viseme_id` | enum | `REST`, `CLOSED`, `A`, `I`, `U`, `E`, or `O` |
| `start_sec` | float | Event start in audio seconds |
| `end_sec` | float | Event end in audio seconds |
| `weight` | float | Normalized mouth strength, from 0 to 1 |
| `confidence` | float | Recognition confidence, from 0 to 1 |
| `source` | enum | `ASR`, `G2P`, `ALIGNER`, or `MANUAL` |
| `source_index` | integer | Index in the originating recognition result |
| `source_text` | string | Word or syllable that produced the event |
| `phoneme` | string | Canonical IPA phoneme |
| `language_code` | string | Language that produced this event, when known |
| `source_phoneme` | string | Original language-pack phoneme |
| `articulation_class` | string | Phonetic grouping that generated the event |
| `priority` | integer | Conflict-resolution priority; closure events take precedence |

Invariants:

- `start_sec >= 0`.
- `end_sec >= start_sec`.
- `0 <= weight <= 1`.
- `0 <= confidence <= 1`.
- Events are sorted by `start_sec` before baking.
- Overlapping events are allowed and resolved by the timeline evaluator.

## Generated asset

`MMDMouthGeneratedAsset` records Blender data generated by one clip.

| Field | Type | Meaning |
| --- | --- | --- |
| `asset_id` | string | Stable asset record identifier |
| `asset_kind` | enum | `ACTION`, `NLA_STRIP`, or `CONTROLLER` |
| `owner_object` | object pointer | Object owning the animation data |
| `action_name` | string | Generated Action name, if any |
| `strip_name` | string | Generated NLA Strip name, if any |
| `controller_object` | object pointer | Controller object in driver mode |
| `generated_at_schema` | integer | Schema version used to create it |

Direct shape-key animation may require more than one Action because Blender animation data belongs to individual ID owners. The clip therefore stores an asset collection instead of one single action field. `keyframe_assets` stores profile-owned mouth-only Actions created by `Bake All Keyframes`. When another Action or NLA track already owns unrelated shape-key channels, the profile Action is applied through its own NLA strip and the existing animation remains untouched.

## Word segment

Word timestamps are the direct ASR output. They are not phoneme timestamps and must be expanded by a language-specific G2P/duration step before the phoneme layer is created.

| Field | Type | Meaning |
| --- | --- | --- |
| `text` | string | Recognized word or token |
| `start_sec` | float | Word start |
| `end_sec` | float | Word end |
| `confidence` | float | Calibrated project confidence |
| `raw_confidence` | float | Original Vosk `conf` value |
| `language_code` | string | Candidate language |
| `model_id` | string | Candidate model |

## Vosk result contract

The Vosk adapter must normalize its output before it reaches the timeline layer:

```json
{
  "schema_version": 5,
  "timebase": "seconds",
  "backend_id": "vosk",
  "model_id": "vosk-model-small-cn-0.22",
  "language_code": "zh-CN",
  "audio_duration_sec": 12.4,
  "selected_candidate_id": "cand-0001",
  "candidate_scoring_version": 2,
  "candidates": [
    {
      "candidate_id": "cand-0001",
      "segment_id": "seg-0001",
      "language_code": "zh-CN",
      "model_id": "vosk-model-small-cn-0.22",
      "start_sec": 0.0,
      "end_sec": 12.4,
      "raw_score": 0.81,
      "normalized_score": 0.76,
      "selection_score": 0.79,
      "selected": true
    }
  ],
  "words": [
    {
      "text": "你好",
      "start_sec": 0.12,
      "end_sec": 0.68,
      "confidence": 0.91,
      "raw_confidence": 0.93,
      "language_code": "zh-CN",
      "model_id": "vosk-model-small-cn-0.22"
    }
  ]
}
```

The recognition layer must not write Blender keyframes. It produces normalized JSON or domain objects only.

## Language segment

`LanguageSegment` is reserved for future mixed-language routing. It is intentionally separate from a clip's default `language_code` and `recognizer_model_id`.

| Field | Type | Meaning |
| --- | --- | --- |
| `start_sec` | float | Segment start in audio seconds |
| `end_sec` | float | Segment end in audio seconds |
| `language_code` | string | Language model used for this segment |
| `model_id` | string | Exact recognizer model used for this segment |
| `confidence` | float | Language identification confidence |
| `source` | enum | Clip default, automatic language ID, or manual |
| `candidate_id` | string | Candidate selected for this language segment |
