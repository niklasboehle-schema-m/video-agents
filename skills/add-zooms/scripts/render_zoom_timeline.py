#!/usr/bin/env python3
"""Validate or render transcript-timed zoom cues with FFmpeg."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


class CueError(ValueError):
    """Raised when a zoom cue sheet is invalid."""


@dataclass(frozen=True)
class MediaInfo:
    width: int
    height: int
    fps: float
    duration: float


def number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise CueError(f"{label} must be finite")
    return result


def positive_time(value: Any, label: str, *, allow_zero: bool = True) -> float:
    result = number(value, label)
    if result < 0 or (not allow_zero and result == 0):
        relation = "non-negative" if allow_zero else "greater than zero"
        raise CueError(f"{label} must be {relation}")
    return result


def zoom_scale(value: Any, label: str) -> float:
    result = number(value, label)
    if not 1.0 <= result <= 2.0:
        raise CueError(f"{label} must be between 1.0 and 2.0")
    return result


def load_cues(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CueError(f"cue sheet not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CueError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(document, dict):
        raise CueError("cue sheet root must be an object")
    if document.get("schema") != 1:
        raise CueError("schema must be 1")

    focus = document.get("focus", {})
    if not isinstance(focus, dict):
        raise CueError("focus must be an object")
    for axis, default in (("x", 0.5), ("y", 0.38)):
        value = number(focus.get(axis, default), f"focus.{axis}")
        if not 0.0 <= value <= 1.0:
            raise CueError(f"focus.{axis} must be between 0 and 1")

    events = document.get("events")
    if not isinstance(events, list):
        raise CueError("events must be an array")

    for index, event in enumerate(events):
        validate_event(event, index)
    return document


def validate_event(event: Any, index: int) -> None:
    label = f"events[{index}]"
    if not isinstance(event, dict):
        raise CueError(f"{label} must be an object")

    kind = event.get("kind")
    if kind == "punch":
        positive_time(event.get("start"), f"{label}.start")
        positive_time(event.get("duration"), f"{label}.duration", allow_zero=False)
        zoom_scale(event.get("scale"), f"{label}.scale")
        return

    if kind == "steps":
        beats = event.get("beats")
        if not isinstance(beats, list) or len(beats) < 2:
            raise CueError(f"{label}.beats must contain at least two steps")
        prior = -1.0
        for beat_index, beat in enumerate(beats):
            beat_label = f"{label}.beats[{beat_index}]"
            if not isinstance(beat, dict):
                raise CueError(f"{beat_label} must be an object")
            start = positive_time(beat.get("start"), f"{beat_label}.start")
            zoom_scale(beat.get("scale"), f"{beat_label}.scale")
            if start <= prior:
                raise CueError(f"{label}.beats starts must increase")
            prior = start
        end = positive_time(event.get("end"), f"{label}.end", allow_zero=False)
        if end <= prior:
            raise CueError(f"{label}.end must be after the final step")
        return

    if kind == "push":
        start = positive_time(event.get("start"), f"{label}.start")
        end = positive_time(event.get("end"), f"{label}.end", allow_zero=False)
        if end <= start:
            raise CueError(f"{label}.end must be after its start")
        zoom_scale(event.get("from", 1.0), f"{label}.from")
        zoom_scale(event.get("to"), f"{label}.to")
        return

    raise CueError(f"{label}.kind must be punch, steps, or push")


def event_end(event: dict[str, Any]) -> float:
    if event["kind"] == "punch":
        return float(event["start"]) + float(event["duration"])
    return float(event["end"])


def probe_media(path: Path) -> MediaInfo:
    if shutil.which("ffprobe") is None:
        raise CueError("ffprobe is required but was not found on PATH")
    if not path.is_file():
        raise CueError(f"input video not found: {path}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        stream = payload["streams"][0]
        rate_text = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
        fps = float(Fraction(rate_text))
        duration = float(payload["format"]["duration"])
        info = MediaInfo(int(stream["width"]), int(stream["height"]), fps, duration)
    except (
        subprocess.CalledProcessError,
        KeyError,
        IndexError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise CueError(f"could not probe the first video stream in {path}") from exc

    if info.width < 2 or info.height < 2 or info.fps <= 0 or info.duration <= 0:
        raise CueError("input video has invalid dimensions, frame rate, or duration")
    return info


def frame_at(seconds: float, fps: float) -> int:
    return max(0, math.floor(seconds * fps + 1e-9))


def last_frame(seconds: float, fps: float) -> int:
    return max(0, math.ceil(seconds * fps - 1e-9) - 1)


def bounded_segment(first: int, last: int, active: str) -> str:
    return f"if(between(on\\,{first}\\,{last})\\,{active}\\,1)"


def event_expression(event: dict[str, Any], fps: float) -> str:
    kind = event["kind"]
    if kind == "punch":
        first = frame_at(float(event["start"]), fps)
        final = max(first, last_frame(event_end(event), fps))
        return bounded_segment(first, final, f"{float(event['scale']):.6f}")

    if kind == "steps":
        beats = event["beats"]
        boundaries = [frame_at(float(beat["start"]), fps) for beat in beats]
        end = max(boundaries[-1], last_frame(float(event["end"]), fps))
        expression = "1"
        for index in range(len(beats) - 1, -1, -1):
            first = boundaries[index]
            final = (
                end
                if index == len(beats) - 1
                else max(first, boundaries[index + 1] - 1)
            )
            value = float(beats[index]["scale"])
            expression = (
                f"if(between(on\\,{first}\\,{final})\\,{value:.6f}\\,{expression})"
            )
        return expression

    first = frame_at(float(event["start"]), fps)
    final = max(first + 1, last_frame(float(event["end"]), fps))
    start_scale = float(event.get("from", 1.0))
    delta = float(event["to"]) - start_scale
    progress = f"clip((on-{first})/{final - first}\\,0\\,1)"
    active = f"{start_scale:.6f}+({delta:.6f})*{progress}"
    return bounded_segment(first, final, active)


def combined_expression(events: list[dict[str, Any]], fps: float) -> str:
    result = "1"
    for event in events:
        result = f"max({result}\\,{event_expression(event, fps)})"
    return result


def build_filter(document: dict[str, Any], info: MediaInfo) -> str:
    focus = document.get("focus", {})
    focus_x = float(focus.get("x", 0.5))
    focus_y = float(focus.get("y", 0.38))
    motion = combined_expression(document["events"], info.fps)
    crop_x = f"clip(iw*{focus_x:.6f}-iw/(2*zoom)\\,0\\,iw-iw/zoom)"
    crop_y = f"clip(ih*{focus_y:.6f}-ih/(2*zoom)\\,0\\,ih-ih/zoom)"
    return (
        f"[0:v]scale=iw*2:ih*2:flags=lanczos,"
        f"zoompan=z='{motion}':x='{crop_x}':y='{crop_y}':"
        f"d=1:s={info.width}x{info.height}:fps={info.fps:.8f},"
        "setsar=1,format=yuv420p[zoomed]"
    )


def validate_duration(document: dict[str, Any], duration: float) -> None:
    for index, event in enumerate(document["events"]):
        if event_end(event) > duration + 0.001:
            raise CueError(
                f"events[{index}] ends at {event_end(event):.3f}s, "
                f"after the {duration:.3f}s source"
            )


def render(
    input_path: Path,
    cue_path: Path,
    output_path: Path,
    *,
    crf: int,
    preset: str,
    overwrite: bool,
) -> None:
    if shutil.which("ffmpeg") is None:
        raise CueError("ffmpeg is required but was not found on PATH")
    if input_path.resolve() == output_path.resolve():
        raise CueError("output must be different from the input video")
    if output_path.exists() and not overwrite:
        raise CueError(
            f"output already exists: {output_path}; pass --overwrite to replace it"
        )
    if not output_path.parent.is_dir():
        raise CueError(f"output directory does not exist: {output_path.parent}")

    document = load_cues(cue_path)
    info = probe_media(input_path)
    validate_duration(document, info.duration)
    filter_graph = build_filter(document, info)

    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-v",
        "error",
        "-stats",
        "-i",
        str(input_path),
        "-filter_complex",
        filter_graph,
        "-map",
        "[zoomed]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-crf",
        str(crf),
        "-preset",
        preset,
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    subprocess.run(command, check=True)
    print(
        f"Wrote {output_path} with {len(document['events'])} cues "
        f"at {info.width}x{info.height}, {info.fps:.3f} fps."
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="validate a cue sheet")
    check.add_argument("cues", type=Path)

    show_filter = commands.add_parser("filter", help="print the FFmpeg filter")
    show_filter.add_argument("input", type=Path)
    show_filter.add_argument("cues", type=Path)

    renderer = commands.add_parser("render", help="render a new video")
    renderer.add_argument("input", type=Path)
    renderer.add_argument("cues", type=Path)
    renderer.add_argument("output", type=Path)
    renderer.add_argument("--crf", type=int, default=19)
    renderer.add_argument(
        "--preset",
        choices=(
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ),
        default="medium",
    )
    renderer.add_argument("--overwrite", action="store_true")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        document = load_cues(args.cues)
        if args.command == "check":
            print(f"Valid schema 1 cue sheet with {len(document['events'])} events.")
            return 0

        info = probe_media(args.input)
        validate_duration(document, info.duration)
        if args.command == "filter":
            print(build_filter(document, info))
            return 0

        render(
            args.input,
            args.cues,
            args.output,
            crf=args.crf,
            preset=args.preset,
            overwrite=args.overwrite,
        )
        return 0
    except CueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"error: command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
