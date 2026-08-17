# MMD Mouth

MMD Mouth is a Blender 5.2 add-on that turns offline speech recognition into
MMD `A/I/U/E/O` mouth animation.

## Features

- One-click `Generate Mouth` workflow: recognize when needed, then bake.
- Bundled Chinese, Japanese, and US English Vosk small-model ZIP files.
- No end-user Python, `pip`, command line, or model-directory setup.
- Chinese pypinyin, Japanese OpenJTalk, and English CMUdict G2P adapters.
- Canonical IPA phonemes and consonant-aware `REST/CLOSED/A/I/U/E/O` events.
- Bilabial `p/b/m` closure that suppresses vowels before reopening the mouth.
- Automatic discovery of MMD `あ/い/う/え/お` shape keys and optional `口閉じ`.
- Direct shape-key `BAKE` output or controller-property `DRIVER` output.
- Per-clip Actions and NLA strips with ownership-aware cleanup.
- Automatic owned VSE audio previews with start, trim, duration, and volume sync.
- Per-clip mouth strength, fast regeneration, and complete clip deletion.
- Selectable linear, smoothstep, sine, ease-in, and ease-out vowel blending.
- English and Simplified Chinese Blender interface localization.

## Install And Use

1. In Blender 5.2, install `dist-addon/MMDmouth-0.4.2.zip` as an add-on.
2. Open `3D View > Sidebar > MMD Mouth`.
3. Select the MMD model root and add a model entry.
4. Add a mouth clip, choose a WAV file, language, start frame, and output mode.
5. Click `Generate Mouth`.

The selected Vosk model is verified and extracted on first use under Blender's
user data directory (`mmd_mouth/models`). The add-on never writes model data to
the Blender installation directory.

The current audio reader accepts uncompressed 16-bit PCM WAV. Mono and stereo
are supported; stereo is downmixed in the worker. Compressed audio conversion
is not part of version 0.4.2.

`Auto Compare` runs every enabled language model over the whole clip and keeps
the highest-scoring candidate. It is useful when the clip language is unknown,
but it is not segment-level code-switching or language identification.

## Development

- [Data model](docs/DATA_MODEL.md)
- [Development guide](docs/DEVELOPMENT.md)
- [Vosk models and worker](docs/VOSK.md)

Build the worker with `build_worker.ps1`, then create the normal Blender
install archive with `build_addon.ps1 -SkipWorkerBuild`.
