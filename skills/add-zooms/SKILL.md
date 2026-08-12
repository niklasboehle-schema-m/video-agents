---
name: add-zooms
description: Add transcript-timed punch zooms, stepped zoom sequences, and slow camera pushes to finished videos exported from any editor with a local FFmpeg renderer. Use when the user asks to add zooms, punch in on stressed words, build deeper zooms across a spoken list, add a gradual push over a key idea, or add energy to an already-cut video file. If a file still needs dead-air, filler, false-start, or retake removal, use cut-video first; if the source is still inside a Palmier Pro timeline, use palmier-editing first.
---

# Video Zooms

Create a separate motion-enhanced video from an existing export. Time every move from word-level transcript data and render locally with FFmpeg.

Use the bundled tools:

- `scripts/word_timestamps.py`: normalize Whisper-style word timestamps for review.
- `scripts/render_zoom_timeline.py`: validate a cue sheet, print its FFmpeg filter, or render it.

## Guardrails

- Keep the source unchanged. Choose a new output path; the renderer refuses to overwrite files unless `--overwrite` is explicit.
- Finish the spoken-content edit before adding motion. Use `$cut-video` first for file-based dead-air, filler, false-start, or retake removal. For Palmier timeline work, complete and export through `$palmier-editing` first.
- Keep secrets and client media out of the skill folder. Use a temporary working directory beside the project or under the system temp directory.
- Process locally unless the user explicitly authorizes an external transcription service.

## Motion language

Use restraint so each change has contrast:

- **Punch:** cut immediately to a closer crop on one stressed word or payoff, hold briefly, then cut back.
- **Steps:** move through two to four increasingly close crops across a list or repeated phrase, then return to the full frame.
- **Push:** drift gradually from one scale to another across a thesis, reveal, or closing thought.

Start with these ranges and adapt to the footage:

- Punch scale: `1.16`–`1.28`; duration: `0.18`–`0.55` seconds.
- Step scales: begin near `1.10` and add roughly `0.04`–`0.07` per spoken beat.
- Push scale: usually end between `1.08` and `1.14`.
- Talking-head focus: begin around `x=0.50`, `y=0.38`; inspect the actual frame and adjust.
- Leave full-frame gaps between cues. Do not animate filler, every sentence, or b-roll by default.

## Workflow

### 1. Preflight

Confirm that `python3`, `ffmpeg`, and `ffprobe` are available. Probe the source dimensions, frame rate, duration, and audio. Inspect a representative frame to place the focal point.

### 2. Obtain word timings

Reuse verified word timestamps from the editing system when available. Otherwise, run a local transcription tool that emits word timings. For example:

```bash
mkdir -p zoom_work
ffmpeg -y -i input.mp4 -vn -ac 1 -ar 16000 zoom_work/speech.wav
whisper zoom_work/speech.wav --word_timestamps True --output_format json --output_dir zoom_work
python3 scripts/word_timestamps.py zoom_work/speech.json > zoom_work/words.txt
```

Read the normalized table alongside the video. Treat transcript timing as a guide and confirm cue landings by ear.

### 3. Author the cue sheet

Create JSON with a focus point and a list of events:

```json
{
  "schema": 1,
  "focus": {"x": 0.50, "y": 0.38},
  "events": [
    {"kind": "punch", "start": 2.40, "duration": 0.34, "scale": 1.23, "note": "payoff"},
    {
      "kind": "steps",
      "beats": [
        {"start": 5.10, "scale": 1.12},
        {"start": 5.55, "scale": 1.18},
        {"start": 6.02, "scale": 1.25}
      ],
      "end": 6.52,
      "note": "three-part list"
    },
    {"kind": "push", "start": 9.20, "end": 12.00, "from": 1.00, "to": 1.12, "note": "main idea"}
  ]
}
```

Use transcript word starts for `start`. Set a punch `duration` to cover the word, not the entire sentence. Set each step at the first word of its beat. Span a push across the complete thought. When events overlap, the closer crop wins.

### 4. Validate and render

Resolve the script path from this skill directory, then run:

```bash
python3 scripts/render_zoom_timeline.py check zoom_work/cues.json
python3 scripts/render_zoom_timeline.py render \
  input.mp4 zoom_work/cues.json output-with-zooms.mp4
```

Use `--crf 18` for higher quality or `--preset fast` for a quicker draft. Use `filter` instead of `render` to inspect the generated filter without modifying media:

```bash
python3 scripts/render_zoom_timeline.py filter input.mp4 zoom_work/cues.json
```

### 5. Verify

Watch the complete output once with sound. Then compare frames at:

- a full-frame rest moment;
- the first frame of each punch;
- every step transition;
- the beginning and end of each push.

Confirm that the subject remains framed, cuts land on the intended syllables, pushes do not feel like accidental drift, audio stays synchronized, and the output duration matches the source within one frame. Revise only the cue sheet and render again; do not retranscribe unless the timestamps are wrong.
