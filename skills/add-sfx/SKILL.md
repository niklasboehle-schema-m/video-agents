---
name: add-sfx
description: Place whooshes, pops, clicks, and impacts under a finished video so text, overlays, transitions, and visual examples land with sound, rendered locally with FFmpeg from a user-supplied sound library. Use when the user asks to add sound effects, SFX, whooshes, swooshes, pops, or clicks, to sound-design a talking head, or to make an edit feel less flat and more engaging. Run after the spoken edit and after any motion work: use cut-video first for dead-air, filler, false-start, or retake removal, add-zooms first for transcript-timed motion, and palmier-editing first when the source is still in a Palmier Pro timeline.
---

# Add Sound Effects

Create a separate sound-designed video from an existing export. Place one short sound under each visual event, mix it beneath the voice, and render locally with FFmpeg. Video is stream-copied, so only the audio is re-encoded.

Use the bundled tools:

- `scripts/suggest_sfx_cues.py`: detect scene changes and read an `$add-zooms` cue sheet to propose transition candidates.
- `scripts/render_sfx.py`: validate a cue sheet, print its FFmpeg filter graph, or render it.

## Guardrails

- Keep the source unchanged. Choose a new output path; the renderer refuses to overwrite files unless `--overwrite` is explicit.
- Sound effects come last. Cutting and zooming both change timestamps, so finish those first.
- This skill ships no audio. The user supplies a sound library folder and a manifest. Never download, generate, or substitute sounds without explicit approval, and never add a library to this repository.
- Never raise or compress the voice. Only the effects are attenuated; the spoken track passes through untouched.
- Keep secrets and client media out of the skill folder. Use a temporary working directory beside the project or under the system temp directory.

## The sound library

Point the skill at a folder the user owns, with a `library.json` manifest beside the files:

```json
{
  "schema": 1,
  "root": ".",
  "sounds": {
    "pop_soft": {"file": "pops/pop-soft.wav"},
    "whoosh_short": {"file": "whoosh/whoosh-short.wav", "gain_db": -3.0}
  }
}
```

`root` is relative to the manifest. Per-sound `gain_db` trims one hot or quiet file so every cue starts from the same perceived level; leave it out when the pack is already balanced.

Use these role names so cue sheets stay portable between packs:

| Role | Family | Use for |
|---|---|---|
| `pop_soft` | pop | one word or a small element appearing |
| `pop_hard` | pop | a heavier element landing |
| `click` | pop | a cursor, icon, checkbox, or UI action |
| `whoosh_in` | whoosh | an element sweeping into frame |
| `whoosh_out` | whoosh | an element leaving frame |
| `whoosh_short` | whoosh | a fast cut or quick camera move |
| `swipe` | whoosh | a horizontal slide between panels |
| `riser` | movement | a build into a reveal |
| `thud` | impact | a hard landing at the end of a move |

A pack missing a role is fine. Choose the nearest available name and say which substitution you made.

## Placement

Sound belongs on four kinds of moment, and nowhere else:

- **Intro text:** each word or line that animates on. Small pops, or a whoosh when the text sweeps rather than appears.
- **Overlays:** graphics, emoji, screenshots, and callouts that pop onto the frame.
- **Transitions:** cuts, whip pans, and location changes, only when the cut is meant to be felt.
- **Visual examples:** an app icon, a split screen, or a diagram arriving to illustrate a point.

Record the slot on each cue so the sheet stays reviewable.

Rules that keep it invisible:

- One sound per visual event. Stacking two on the same frame reads as a mistake.
- Match the family to the motion. Something that moves gets a whoosh, something that appears gets a pop. Never both.
- Whooshes peak late in the file, so start them roughly `0.10`–`0.20` seconds before the visual lands. Pops peak immediately, so start them on the exact frame.
- Leave silent stretches. A cue every second is noise; the effect only works when it marks something.
- Do not sound every cut. Hard cuts inside continuous speech usually want nothing.

Starting levels, before adjusting by ear:

- Pops and clicks: `-16` to `-12` dB.
- Whooshes and swipes: `-18` to `-14` dB.
- Impacts and risers: `-12` to `-8` dB.

## Workflow

### 1. Preflight

Confirm that `python3`, `ffmpeg`, and `ffprobe` are available. Probe the source for duration and audio. Confirm the library path and read its manifest. Watch the video once and note every visual event with its timestamp and slot.

```bash
mkdir -p sfx_work
```

### 2. Propose transition candidates

Scene detection finds cuts. It cannot see text, overlays, or graphics, so it only ever produces a partial sheet:

```bash
python3 scripts/suggest_sfx_cues.py \
  input.mp4 sfx_work/cues.json \
  --library /path/to/sfx/library.json \
  --zooms zoom_work/cues.json \
  --threshold 0.35
```

Pass `--zooms` when the video came from `$add-zooms` so each punch, step, and push gets a candidate. Read the reported scene count and warning. Raise `--threshold` when high-motion footage returns a change per second.

### 3. Author the cue sheet

Add the intro text, overlay, and visual example cues by hand, then delete every proposed cue that does not mark a real event:

```json
{
  "schema": 1,
  "library": "../sfx/library.json",
  "gain_db": -14,
  "cues": [
    {"at": 0.94, "sound": "pop_soft", "slot": "intro_text", "note": "word 'boring' lands"},
    {"at": 3.31, "sound": "whoosh_short", "slot": "transition", "gain_db": -16, "note": "cut to the car"},
    {"at": 6.12, "sound": "pop_hard", "slot": "overlay", "duration": 0.40, "note": "emoji stack"}
  ]
}
```

`library` resolves relative to the cue sheet. `at` is where the sound file starts, not where the visual lands. `gain_db` on a cue overrides the sheet default. `duration` shortens a long file and fades it out; leave it out to play the file whole. Cues may be written in any order.

### 4. Validate and render

Resolve the script path from this skill directory, then run:

```bash
python3 scripts/render_sfx.py check sfx_work/cues.json --input input.mp4
python3 scripts/render_sfx.py render \
  input.mp4 sfx_work/cues.json output-with-sfx.mp4
```

`check` verifies every sound resolves to a real file and warns when cues are crowded or dense. Use `filter` instead of `render` to inspect the generated graph without modifying media:

```bash
python3 scripts/render_sfx.py filter input.mp4 sfx_work/cues.json
```

### 5. Verify

Listen to the complete output once at normal volume, then once at low volume. Confirm that:

- every cue lands on its visual frame, with no sound arriving early or late;
- the voice is never buried, ducked, or clipped;
- no two effects collide on the same moment;
- the same sound does not repeat so often that it becomes a pattern;
- silent stretches remain between cues;
- the output duration matches the source and the picture is unchanged.

Then watch once with the sound off. If the edit reads the same, the placement is right. Revise only the cue sheet and render again.
