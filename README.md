# MMD Mouth

[English](README.md) | [简体中文](README.zh-CN.md)

MMD Mouth is a Blender 5.2 add-on that turns offline speech recognition into
MMD `A/I/U/E/O` mouth animation.

## Features

- One-click `Generate Mouth` workflow: recognize when needed, then bake.
- Bundled Chinese, Japanese, and US English Vosk small-model ZIP files.
- No end-user Python, `pip`, command line, or model-directory setup.
- Chinese pypinyin, Japanese OpenJTalk, and English CMUdict G2P adapters.
- Canonical IPA phonemes and consonant-aware `REST/CLOSED/A/I/U/E/O` events.
- Bilabial `p/b/m` closure that suppresses vowels before reopening the mouth.
- Automatic discovery of only the five MMD `あ/い/う/え/お` shape keys.
- Direct shape-key `BAKE` output or controller-property `DRIVER` output.
- Per-clip Actions and NLA strips with ownership-aware cleanup.
- Bake every active-model clip into editable shape-key keyframe control points for timeline editing or VMD morph-sequence export.
- Automatic owned VSE audio previews with start, trim, duration, and volume sync.
- Per-clip mouth strength, fast regeneration, and complete clip deletion.
- Per-clip adjustable transition-in/out time with smooth, clamped curve output.
- Expandable, chronologically sorted, manually editable mouth timeline.
- Blender-native conversion of common audio formats to cached 16-bit PCM WAV.
- Selectable linear, smoothstep, sine, ease-in, and ease-out vowel blending.
- English and Simplified Chinese Blender interface localization.

## Install And Use

1. In Blender 5.2, install `dist-addon/MMDmouth-0.6.2.zip` as an add-on.
2. Open `3D View > Sidebar > MMD Mouth`.
3. Select the MMD model root and add a model entry.
4. Add a mouth clip, choose a WAV file, language, start frame, and output mode.
5. Click `Generate Mouth`.
6. Expand `Mouth Timeline` to adjust viseme, start, end, or weight values.
7. Click `Regenerate` to bake the edited timeline without running recognition again.
8. Click `Bake All Keyframes` when all clips on the active model should be exposed as editable shape-key keyframes.

The audio refresh button beside `Audio` can convert common Blender-supported
formats such as MP3, OGG, FLAC, and non-PCM WAV files to a cached 16-bit PCM
WAV. `Generate Mouth` performs the same conversion automatically when needed.

`Generate Mouth` recognizes audio when the clip has no usable timeline or when
its recognition inputs are stale. `Regenerate` always uses the current editable
timeline, so manual timing corrections are preserved.

The selected Vosk model is verified and extracted on first use under Blender's
user data directory (`mmd_mouth/models`). The add-on never writes model data to
the Blender installation directory.

The worker reads uncompressed 16-bit PCM WAV. Mono and stereo are supported;
stereo is downmixed in the worker. Blender's built-in audio decoder converts
supported compressed formats to a cached mono PCM WAV before recognition.

`Auto Compare` runs every enabled language model over the whole clip and keeps
the highest-scoring candidate. It is useful when the clip language is unknown,
but it is not segment-level code-switching or language identification.

## Development

- [Data model](docs/DATA_MODEL.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Vosk models and worker](docs/VOSK.md)

Build the worker with `build_worker.ps1`, then create the normal Blender
install archive with `build_addon.ps1 -SkipWorkerBuild`.
