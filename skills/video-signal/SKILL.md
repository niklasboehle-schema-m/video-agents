---
name: video-signal
description: Upload one local video to Gemini and return a customizable markdown analysis with a summary, approximate timeline, speech notes, visible details, key moments, and practical follow-up ideas. Use when the user wants to understand, summarize, inspect, or repurpose a local video; analyze an ad, demo, meeting, tutorial, screen recording, or UGC clip; or extract claims, objections, steps, and clip opportunities. This skill analyzes only—it does not edit video or guarantee a verbatim, frame-accurate transcript.
---

# Analyze Video

Turn one local video into a structured markdown report through Gemini.

## What This Skill Does

Take:

- one local video file;
- an optional question or analysis request.

Then:

1. Validate the path and video format.
2. Upload only that video to Gemini.
3. Wait for Gemini to process it.
4. Return a markdown report in the terminal or save it to a file.

By default, report:

- what happens and what the video appears to be for;
- an approximate scene-by-scene timeline;
- spoken-content and audio notes;
- visible people, actions, products, UI, text, settings, and edits;
- moments worth clipping, quoting, or investigating;
- practical ways to reuse the material.

## Use It For

- “Tell me exactly what happens in this video.”
- “Break this product demo into steps and visible UI changes.”
- “Find the strongest claims, proof, objections, and CTA in this ad.”
- “Turn this screen recording into an SOP draft.”
- “Find moments that could become short-form clips.”
- “Answer this specific question using evidence from the video.”

## Do Not Use It For

- cutting, captioning, reframing, rendering, or otherwise editing the video;
- guaranteed verbatim transcription or frame-accurate timecodes;
- analyzing a folder or video library in one run;
- local-only or offline analysis;
- media that must not be uploaded to Gemini.

Use a dedicated transcription tool when exact wording is critical. Treat reported timestamps as approximate unless independently verified.

## Privacy Boundary

Upload only the video path explicitly passed to the script. Do not upload nearby files, project folders, credentials, or environment files. Confirm that Gemini is an appropriate destination for private or client media before running the analysis.

The skill reads `GEMINI_API_KEY` from the environment. Never place the key in a command, prompt, report, or repository.

## Quick Use

Produce the default analysis:

```bash
python scripts/analyze_video.py /path/to/video.mp4
```

Ask a focused question:

```bash
python scripts/analyze_video.py /path/to/video.mp4 --prompt "Extract every product claim and timestamp it."
```

Save the result:

```bash
python scripts/analyze_video.py /path/to/video.mp4 --output report.md
```

## Requirements

- `GEMINI_API_KEY` must be available in the shell environment.
- Install the SDK with `python -m pip install google-genai`.
- Supported files depend on Gemini, but common formats include `mp4`, `mov`, `webm`, `avi`, `mpeg`, `mpg`, `flv`, `wmv`, `3gp`, and `3gpp`.

## Workflow

1. Confirm the video path exists.
2. Confirm that uploading the video to Gemini is appropriate.
3. Run `scripts/analyze_video.py`.
4. Read the markdown report and distinguish observations from inferences.
5. Rerun with `--prompt` when the user needs a narrower answer.
6. Verify exact quotes and edit points with a transcript or timeline before using them publicly.

## Reporting Standards

When presenting results to the user:

- Preserve timestamps when the model provides them.
- Separate observed visual facts from inferred intent.
- Do not invent speakers, narrators, quotes, UI text, products, or brand names.
- Say when audio is unclear, off-screen, or unavailable.
- For ads, focus on hook, offer, proof, objections, pacing, creative structure, and call to action.
- For tutorials or screen recordings, convert visible steps into an SOP only when the action is clear.

## Options

```bash
python scripts/analyze_video.py VIDEO_PATH \
  --model gemini-2.5-flash \
  --prompt "Custom analysis request" \
  --timeout 300 \
  --poll-interval 5 \
  --output report.md
```

Use `--model` when the default is unavailable in the user's region or account.
