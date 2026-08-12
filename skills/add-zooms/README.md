# Add Zooms

A portable AI skill for adding transcript-timed punch zooms, stepped zoom sequences, and slow camera pushes to finished videos.

Give a skill-compatible agent a local video. The agent reads word-level transcript timings, chooses the moments where motion supports the delivery, writes a reviewable cue sheet, renders a separate output with FFmpeg, and verifies every transition.

The source video stays unchanged and all processing can remain local.

## What it does

- Punches in on an important word, number, contrast, or payoff.
- Builds deeper crops across spoken lists or escalating sequences.
- Adds restrained slow pushes over key ideas and closing thoughts.
- Keeps full-frame gaps between moves so the motion retains contrast.
- Uses explicit JSON cues, so every decision can be reviewed or changed.
- Refuses to overwrite the source unless overwrite behavior is explicitly enabled.

## Included files

- `SKILL.md` — the complete agent workflow and timing guidance.
- `scripts/word_timestamps.py` — normalizes Whisper-style word timestamps.
- `scripts/render_zoom_timeline.py` — validates cue sheets, prints FFmpeg filters, and renders the result.
- `examples/map.example.json` — example punch, steps, and push cues.
- `agents/openai.yaml` — optional UI metadata for OpenAI-compatible skill hosts.

## Requirements

- Python 3.10 or newer
- `ffmpeg` and `ffprobe`
- Word-level transcript timestamps from a local or authorized transcription tool

The bundled scripts make no network requests, install no packages, and read no credentials.

## Install

Clone the repository:

```bash
git clone https://github.com/RBYHNDRDS/add-zooms.git
```

For Codex and other agents that scan `~/.agents/skills`:

```bash
mkdir -p "${HOME}/.agents/skills"
ln -s "${PWD}/add-zooms" "${HOME}/.agents/skills/add-zooms"
```

For Claude Code:

```bash
mkdir -p "${HOME}/.claude/skills"
ln -s "${PWD}/add-zooms" "${HOME}/.claude/skills/add-zooms"
```

## Use it

Ask in normal language:

```text
Use $add-zooms on this finished video.
Punch the strongest payoff words, build one stepped zoom across the list,
and add a restrained push over the final idea.
```

The agent should inspect the video and transcript before authoring the cue sheet. Transcript timing is a guide; final landings are confirmed by ear and frame review.

## Manual renderer

Validate and render an approved cue sheet:

```bash
python3 scripts/render_zoom_timeline.py check examples/map.example.json

python3 scripts/render_zoom_timeline.py render \
  input.mp4 examples/map.example.json output-with-zooms.mp4
```

Use `filter` instead of `render` to inspect the generated FFmpeg expression without modifying media:

```bash
python3 scripts/render_zoom_timeline.py filter \
  input.mp4 examples/map.example.json
```

## Privacy and safety

- Video, audio, transcript data, and cue sheets stay local unless the user explicitly authorizes another service.
- Source files are not replaced.
- Outputs are written to a separate path.
- Media, transcripts, work folders, environment files, keys, and tokens are excluded from Git.
- No telemetry or credential reader is included.

## License

MIT. See `LICENSE`.
