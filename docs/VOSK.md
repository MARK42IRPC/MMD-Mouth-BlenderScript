# Vosk Worker And Models

## Official Model Links

- Catalog: <https://alphacephei.com/vosk/models>
- Chinese small: <https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip>
- Japanese small: <https://alphacephei.com/vosk/models/vosk-model-small-ja-0.22.zip>
- US English small: <https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip>

Vosk publishes language-specific models. It does not publish one general
Chinese/Japanese/English mixed model. `vosk-model-cn-kaldi-multicn-0.15` is a
Chinese model variant, not a multilingual model.

## Release Behavior

All three official small-model ZIPs are included in the add-on archive. The
user installs one normal Blender add-on and does not select model directories.
On first use of a language, the worker verifies the archive SHA-256 and extracts
it to Blender's user data path:

```text
<Blender user DATAFILES>/mmd_mouth/models/<model-id>/
```

The ZIP remains part of the installed add-on. Extracted models are reusable
across `.blend` files and can be rebuilt from the verified archive if the user
cache is removed.

The PyInstaller `onedir` worker contains Vosk, pypinyin, CMUdict, OpenJTalk,
native DLLs, and language data. Blender starts it without a console window.
Blender's Python never imports these third-party binary packages.

## Audio Contract

Version 0.4.2 accepts uncompressed 16-bit PCM WAV. Mono is passed through;
multi-channel input is downmixed to mono. Vosk receives the original sample
rate. `audio_offset_sec` and optional duration select a WAV region, while all
persisted word/phone/event timestamps stay in source-audio seconds.

## Candidate Selection

For an explicit clip language, Blender sends only models from that language
family. `Auto Compare` sends every enabled model for the same whole-audio
segment. Each candidate keeps:

- raw Vosk word confidence;
- calibrated word confidence;
- duration-weighted model score;
- speech coverage and text presence;
- final versioned selection score.

Raw Vosk confidence is not a calibrated probability across independent
language models. Auto comparison is therefore best-effort and emits a warning.
Losing candidates remain in worker JSON for diagnostics.

This is not mixed-language routing. A future router must first split audio into
language segments, then reuse the same candidate contract per segment.

## Worker Job

Development jobs use a JSON input and output file:

```powershell
.\.venv-worker\Scripts\python.exe -m mmd_mouth.recognition.worker `
  --job configs\vosk_job.example.json `
  --output cache\recognition.json
```

The result contains candidate words, selected language segments, canonical IPA
phones, viseme events, stage errors, schema version, and worker protocol. One
model may fail without failing the whole job, but at least one recognition
candidate must complete.

## Windows Paths

Vosk 0.3.45's native Windows loader can reject non-ASCII model arguments. The
worker temporarily enters the model directory and passes `.` to the native
loader, while a process lock prevents concurrent working-directory changes.
This keeps localized Windows user paths usable without changing user files.
