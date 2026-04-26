# Subagent prompt: real audio + audio-bearing guide video fixtures

You are working in `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`. Self-contained task. Do not modify the materializer architecture, the validator, the watchdog, the model registry, or the override logic.

## Problem

The doc entry is `LTX Runexx audio extraction and audio-shape assumptions` in `docs/hiddenswitch_incompatibilities.md` (Root cause: `fixture_gap`). Workflows that extract audio from a "guide video" fixture choke because:

1. Our generated guide videos (`ltx_smoke_guide.mp4`, `wolf_interpolated.mp4`, `bubble.mp4`, `10.mp4`) are silent — see `scripts/runpod_corpus_matrix.py:111-128`. They're 5-frame H.264 at 256×256 with no audio stream. Extracting audio from them yields empty/zero-shape tensors.
2. Our smoke audio `speech_smoke.wav` is a 220Hz sine tone (`scripts/runpod_corpus_matrix.py:132-148`), not actual speech. Fine for NormalizeAudio shape, but anything that does VAD or speech embedding will silently produce garbage.
3. Both fixtures are regenerated at every matrix bootstrap via inline Python heredocs — not stored, not testable, not deterministic across `av`/`Pillow`/`wave` library versions.
4. The materializer at `scripts/materialize_ready_templates.py:312-318` already works around this for one specific case by injecting `LoadAudio("speech_smoke.wav")` for workflows whose `VHS_LoadVideo` feeds something audio-shaped — but the workaround only fires for that exact pattern. Other audio-extraction workflows still hit the silent-video problem.

The structural fix is small: ship real fixture files in the repo, mux the audio into the guide videos, and replace the inline heredoc generators with a single committed-asset path.

## Scope

1. Commit a real `speech_smoke.wav` (a short, real-speech audio clip — ~2-4 seconds, mono, 16kHz or 24kHz, ~50-100KB) to `workflow_corpus/input/`.
2. Regenerate the four guide videos with the speech audio muxed in. Commit them to `workflow_corpus/input/` alongside the existing image fixtures.
3. Replace the inline Python heredoc generators in `scripts/runpod_corpus_matrix.py` and `scripts/runpod_matrix_remote.py` with a tiny `vibecomfy/fixtures.py` module that copies the committed assets into the matrix's input dir at bootstrap. Keep generation as a fallback for environments where the committed assets are missing, but make committed-asset-copy the primary path.

Not in scope: changing the materializer's audio-injection logic, adding a per-workflow input-contract system, or generating new modality-specific fixtures (talking-head, music, etc.). Those are follow-ups.

## Files to read

- `scripts/runpod_corpus_matrix.py:95-148` — the inline guide-video and speech-audio generators.
- `scripts/runpod_matrix_remote.py:285-295` and `:413-432` — runtime-side audio fixture wiring (the LoadAudio injection path).
- `scripts/materialize_ready_templates.py:312-330` — the materializer-side audio-injection workaround.
- `workflow_corpus/input/` — where committed fixtures already live (image PNGs/JPEGs).
- `docs/hiddenswitch_incompatibilities.md` — the entry you'll update.

## What to build

### Step 1: Author and commit `speech_smoke.wav`

- Pick a short, freely-licensed speech sample (~2-4s). Suggested sources:
  - LibriSpeech sample (CC BY 4.0).
  - Mozilla Common Voice short clip (CC0).
  - Generate with a TTS engine you have available locally, then license-tag in the asset's filename or a sibling `LICENSE.fixtures` note.
- Convert to: mono, 16kHz or 24kHz, 16-bit PCM WAV.
- Target size: under 200KB.
- Place at `workflow_corpus/input/speech_smoke.wav`.
- Add a one-line entry to a new `workflow_corpus/input/FIXTURES.md` documenting source, license, and intended use ("for audio-extraction smoke; non-silent so NormalizeAudio and downstream audio nodes get realistic input").

### Step 2: Generate audio-bearing guide videos

- For each of `ltx_smoke_guide.mp4`, `wolf_interpolated.mp4`, `bubble.mp4`, `10.mp4`: regenerate with the same visual content (5 frames, 256×256, libx264) BUT add an audio stream containing `speech_smoke.wav` (loop or trim to match the video duration; for 5-frame@8fps videos that's <1s, so the speech will be truncated — that's fine).
- Use `pyav` (already a dep — see `runpod_corpus_matrix.py:112`). Mux the audio stream into the same container.
- Commit the resulting `.mp4` files to `workflow_corpus/input/`. Sanity-check sizes — they should grow modestly (audio is small relative to compressed video, but H.264 of 5 frames is tiny anyway, so the audio may dominate).
- Document each one's intended use in `FIXTURES.md`.

### Step 3: `vibecomfy/fixtures.py` module

- New file `vibecomfy/fixtures.py`. Public surface:
  - `FIXTURE_ROOT: Path` — absolute path to `workflow_corpus/input/`.
  - `copy_smoke_fixtures(target_input_dir: Path) -> list[Path]` — copies the smoke fixtures (`speech_smoke.wav`, the four guide videos, and any image fixtures relied on by smoke runs) into `target_input_dir`. Returns the list of created paths. Idempotent: if a target file already exists with matching size+mtime, skip it.
  - `regenerate_smoke_fixtures(target_input_dir: Path) -> list[Path]` — fallback path that generates synthetic fixtures using the same heredoc logic as today (sine-wave WAV, silent videos). Used only when committed fixtures are unavailable. Print a clear warning when this path is taken.
  - `available_fixtures() -> dict[str, Path]` — returns a mapping of fixture name → committed path for inspection by tests.
- Keep `vibecomfy/fixtures.py` standalone (no heavy deps; `pyav` and `wave` only used in the regenerate fallback).

### Step 4: Wire into matrix scripts

- In `scripts/runpod_corpus_matrix.py`, replace the inline heredoc generators (the `try: import av ...` block and the `try: import wave ...` block, lines ~95-148) with a single call:
  ```bash
  $PY -m vibecomfy.fixtures copy --target input
  ```
  Add a `__main__` to `vibecomfy/fixtures.py` with a small argparse: `vibecomfy.fixtures copy --target PATH` and `vibecomfy.fixtures regenerate --target PATH`. The `copy` subcommand auto-falls-back to `regenerate` with a printed warning if any committed fixture is missing.
- In `scripts/runpod_matrix_remote.py`, the runtime-side audio injection logic (`LoadAudio("speech_smoke.wav")` at ~289 and ~425) does not need to change — `speech_smoke.wav` is now a better-quality file at the same path. Verify the path resolution works from RunPod's expected cwd.

### Step 5: Update the doc entry

- In `docs/hiddenswitch_incompatibilities.md`, the entry `LTX Runexx audio extraction and audio-shape assumptions`:
  - The `fixture_gap` root cause is now substantially mitigated. Update the status to `Mitigated` (from `Open`) and add a note pointing to the committed fixtures + the `vibecomfy/fixtures.py` module.
  - Keep the entry. Do not delete. Add a "Remaining gap:" line acknowledging that workflows requiring specific speech content (talking-head lip-sync, etc.) are still untested with smoke fixtures.

## Constraints

- **Asset sizes**: total fixture commit budget under ~1MB. If videos blow past this, lower their resolution or shorten them — visual quality doesn't matter, only that they're decodable and have audio.
- **License**: every committed audio/video asset must be CC0, CC BY, public domain, or self-generated. Document license in `FIXTURES.md`. No assets of unclear provenance.
- **Reversibility**: env var `VIBECOMFY_FIXTURES_REGENERATE=1` forces the regenerate-fallback path even if committed assets exist (for testing the fallback).
- **No new top-level deps**: `pyav` and `wave` already in the matrix; `vibecomfy/fixtures.py` should import them lazily inside `regenerate_*` only.
- **Cross-platform**: `vibecomfy.fixtures` must work on macOS dev boxes and Linux RunPod containers identically. Use `pathlib`, no shelling.

## Acceptance

- A workflow that previously failed due to silent-video audio extraction (find one in `docs/hiddenswitch_incompatibilities.md` or in the matrix's archived failure logs) now extracts non-empty audio and proceeds further. (Whether it goes fully green depends on other factors; the bar here is "audio-extraction nodes no longer fail.")
- All 14 runtime-green workflows still pass.
- Unit tests in `tests/test_fixtures.py`: `copy_smoke_fixtures` is idempotent, falls back when an asset is missing, and produces files with non-zero audio streams (use `pyav` to probe).
- `git diff --stat workflow_corpus/input/` shows the new committed fixtures with sane sizes.
- `FIXTURES.md` documents each new asset's source and license.

## Out of scope

- Per-workflow input-contract declaration system (a separate, deferred brief).
- Talking-head / lip-sync fixtures (separate work; needs explicit per-workflow contracts).
- Music / instrumental fixtures.
- Any change to materializer audio-injection logic.
- Any change to the matrix's per-workflow override behavior.
- Compressing or re-encoding the existing image fixtures.

## When done

Report:
- Source and license of `speech_smoke.wav`.
- Sizes of all newly committed assets.
- Confirmation that the four guide videos now have audio streams (e.g., output of `ffprobe` or `pyav` probe).
- Updated status of the `LTX Runexx audio extraction` entry in the incompatibilities doc.
