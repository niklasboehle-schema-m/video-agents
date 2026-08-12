#!/usr/bin/env python3
"""Analyze a local video file with the Gemini Files API."""

from __future__ import annotations

import argparse
import mimetypes
import os
import sys
import time
from pathlib import Path

try:
    from google import genai
except ImportError:  # pragma: no cover - exercised in real user environments
    genai = None


SUPPORTED_SUFFIXES = {
    ".mp4",
    ".mov",
    ".webm",
    ".avi",
    ".mpeg",
    ".mpg",
    ".flv",
    ".wmv",
    ".3gp",
    ".3gpp",
}

DEFAULT_MODEL = os.environ.get("VIDEO_SIGNAL_MODEL", "gemini-2.5-flash")

DEFAULT_PROMPT = """You are analyzing a video file for a working professional.

Return a clear markdown report with these sections:

1. Executive Summary
   - What happens in the video
   - The likely purpose of the video
   - The most important takeaway

2. Timeline
   - Timestamped scene-by-scene breakdown
   - Include visible actions, screen changes, on-screen text, products, people, and setting changes

3. Audio and Speech
   - Summarize spoken content
   - Include a transcript-style outline if speech is understandable
   - Mark unclear audio as unclear instead of guessing

4. Visual Details
   - Describe notable objects, UI elements, gestures, camera movement, edits, and text overlays

5. Key Moments
   - List moments worth clipping, quoting, investigating, or turning into content

6. Practical Uses
   - Suggest how this video could become an SOP, ad teardown, meeting recap, creative brief, or content asset

Rules:
- Do not invent names, brands, speakers, quotes, claims, or on-screen text.
- Distinguish observation from inference.
- If a timestamp is approximate, label it as approximate.
- If the video has no useful audio or the audio is unintelligible, say so directly.
- Be specific and concise."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload a video to Gemini and produce a structured markdown analysis."
    )
    parser.add_argument("video", help="Path to a local video file")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model to use. Defaults to {DEFAULT_MODEL!r} or VIDEO_SIGNAL_MODEL.",
    )
    parser.add_argument(
        "--prompt",
        help="Custom analysis request. If omitted, a structured default report is used.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Write markdown to this file instead of stdout.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum seconds to wait for Gemini file processing. Default: 300.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Seconds between file processing checks. Default: 5.",
    )
    return parser.parse_args()


def fail(message: str, exit_code: int = 1) -> None:
    print(f"Error: {message}", file=sys.stderr)
    raise SystemExit(exit_code)


def validate_video(path_text: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.exists():
        fail(f"video file does not exist: {path}")
    if not path.is_file():
        fail(f"path is not a file: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        allowed = ", ".join(sorted(SUPPORTED_SUFFIXES))
        fail(f"unsupported video extension {path.suffix!r}. Expected one of: {allowed}")
    return path


def state_name(file_obj: object) -> str:
    state = getattr(file_obj, "state", None)
    name = getattr(state, "name", None)
    return str(name or state or "UNKNOWN")


def wait_until_active(client: object, file_obj: object, timeout: int, poll_interval: int) -> object:
    deadline = time.time() + timeout
    current = file_obj

    while True:
        state = state_name(current)
        if state == "ACTIVE":
            return current
        if state == "FAILED":
            fail("Gemini failed to process the uploaded video.")
        if time.time() >= deadline:
            fail(f"timed out after {timeout}s waiting for Gemini to process the video.")

        print(f"Processing video with Gemini... state={state}", file=sys.stderr)
        time.sleep(max(1, poll_interval))
        current = client.files.get(name=current.name)


def analyze_video(path: Path, prompt: str, model: str, timeout: int, poll_interval: int) -> str:
    if genai is None:
        fail("google-genai is not installed. Run: python -m pip install google-genai")
    if not os.environ.get("GEMINI_API_KEY"):
        fail("GEMINI_API_KEY is not set in the environment.")

    mime_type = mimetypes.guess_type(path.name)[0]
    client = genai.Client()

    print(f"Uploading {path.name}...", file=sys.stderr)
    if mime_type:
        file_obj = client.files.upload(file=path, config={"mime_type": mime_type})
    else:
        file_obj = client.files.upload(file=path)

    ready_file = wait_until_active(client, file_obj, timeout, poll_interval)

    print(f"Analyzing with {model}...", file=sys.stderr)
    response = client.models.generate_content(
        model=model,
        contents=[ready_file, prompt],
    )
    text = getattr(response, "text", None)
    if not text:
        fail("Gemini returned an empty response.")
    return text.strip() + "\n"


def main() -> int:
    args = parse_args()
    video_path = validate_video(args.video)
    prompt = args.prompt or DEFAULT_PROMPT
    report = analyze_video(
        path=video_path,
        prompt=prompt,
        model=args.model,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
    )

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.write_text(report, encoding="utf-8")
        print(f"Wrote {output_path}", file=sys.stderr)
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
