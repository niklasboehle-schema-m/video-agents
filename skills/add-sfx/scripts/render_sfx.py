#!/usr/bin/env python3
"""Validate or render a sound-effect cue sheet onto a finished video with FFmpeg."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CueError(ValueError):
    """Raised when a cue sheet or sound library is invalid."""


SAMPLE_RATE = 48000
MINIMUM_GAIN_DB = -60.0
MAXIMUM_GAIN_DB = 12.0
DEFAULT_GAIN_DB = -14.0
CROWDED_GAP_SECONDS = 0.12
BUSY_CUES_PER_SECOND = 0.85
SLOTS = ("intro_text", "overlay", "transition", "visual_example")


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    has_audio: bool


@dataclass(frozen=True)
class Sound:
    name: str
    path: Path
    gain_db: float


@dataclass(frozen=True)
class Cue:
    index: int
    at: float
    sound: Sound
    gain_db: float
    duration: float | None
    note: str


def number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise CueError(f"{label} must be finite")
    return result


def gain(value: Any, label: str) -> float:
    result = number(value, label)
    if not MINIMUM_GAIN_DB <= result <= MAXIMUM_GAIN_DB:
        raise CueError(
            f"{label} must be between {MINIMUM_GAIN_DB:.0f} and {MAXIMUM_GAIN_DB:.0f} dB"
        )
    return result


def read_document(path: Path, kind: str) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CueError(f"{kind} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CueError(
            f"invalid JSON in {path} at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(document, dict):
        raise CueError(f"{kind} root must be an object")
    if document.get("schema") != 1:
        raise CueError(f"{kind} schema must be 1")
    return document


def load_library(path: Path) -> dict[str, Sound]:
    document = read_document(path, "sound library")

    root = document.get("root", ".")
    if not isinstance(root, str):
        raise CueError("library root must be a string")
    base = (path.parent / root).resolve()

    entries = document.get("sounds")
    if not isinstance(entries, dict) or not entries:
        raise CueError("library sounds must be a non-empty object")

    library: dict[str, Sound] = {}
    for name, entry in entries.items():
        label = f"sounds.{name}"
        if not isinstance(name, str) or not name.strip():
            raise CueError("library sound names must be non-empty strings")
        if not isinstance(entry, dict):
            raise CueError(f"{label} must be an object")
        file_name = entry.get("file")
        if not isinstance(file_name, str) or not file_name.strip():
            raise CueError(f"{label}.file must be a non-empty string")
        resolved = (base / file_name).resolve()
        if not resolved.is_file():
            raise CueError(f"{label}.file not found: {resolved}")
        library[name] = Sound(name, resolved, gain(entry.get("gain_db", 0.0), f"{label}.gain_db"))
    return library


def load_cues(path: Path) -> tuple[dict[str, Any], dict[str, Sound], list[Cue]]:
    document = read_document(path, "cue sheet")

    library_name = document.get("library")
    if not isinstance(library_name, str) or not library_name.strip():
        raise CueError("library must be a path to a sound library manifest")
    library_path = (path.parent / library_name).resolve()
    library = load_library(library_path)

    bed_gain = gain(document.get("gain_db", DEFAULT_GAIN_DB), "gain_db")

    entries = document.get("cues")
    if not isinstance(entries, list) or not entries:
        raise CueError("cues must be a non-empty array")

    cues: list[Cue] = []
    for index, entry in enumerate(entries):
        label = f"cues[{index}]"
        if not isinstance(entry, dict):
            raise CueError(f"{label} must be an object")

        at = number(entry.get("at"), f"{label}.at")
        if at < 0:
            raise CueError(f"{label}.at must be non-negative")

        name = entry.get("sound")
        if not isinstance(name, str) or name not in library:
            available = ", ".join(sorted(library)) or "none"
            raise CueError(
                f"{label}.sound must name a library sound; available: {available}"
            )

        slot = entry.get("slot")
        if slot is not None and slot not in SLOTS:
            raise CueError(f"{label}.slot must be one of {', '.join(SLOTS)}")

        length: float | None = None
        if "duration" in entry:
            length = number(entry["duration"], f"{label}.duration")
            if length < 0.02:
                raise CueError(f"{label}.duration must be at least 0.02 seconds")

        sound = library[name]
        cue_gain = gain(entry.get("gain_db", bed_gain), f"{label}.gain_db")
        note = entry.get("note", "")
        cues.append(
            Cue(
                index,
                at,
                sound,
                cue_gain + sound.gain_db,
                length,
                note if isinstance(note, str) else "",
            )
        )

    cues.sort(key=lambda cue: cue.at)
    return document, library, cues


def probe_media(path: Path) -> MediaInfo:
    if shutil.which("ffprobe") is None:
        raise CueError("ffprobe is required but was not found on PATH")
    if not path.is_file():
        raise CueError(f"input video not found: {path}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        streams = payload["streams"]
        duration = float(payload["format"]["duration"])
        has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
        has_video = any(stream.get("codec_type") == "video" for stream in streams)
    except (
        subprocess.CalledProcessError,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise CueError(f"could not probe {path}") from exc

    if duration <= 0:
        raise CueError("input duration must be greater than zero")
    if not has_video:
        raise CueError("input has no video stream")
    return MediaInfo(duration, has_audio)


def validate_against_media(cues: list[Cue], info: MediaInfo) -> None:
    for cue in cues:
        if cue.at >= info.duration:
            raise CueError(
                f"cues[{cue.index}] starts at {cue.at:.3f}s, "
                f"at or after the {info.duration:.3f}s source"
            )


def restraint_warnings(cues: list[Cue], duration: float | None) -> list[str]:
    warnings: list[str] = []

    crowded = [
        (previous.at, current.at)
        for previous, current in zip(cues, cues[1:])
        if current.at - previous.at < CROWDED_GAP_SECONDS
    ]
    if crowded:
        first, second = crowded[0]
        warnings.append(
            f"{len(crowded)} cue pairs are less than {CROWDED_GAP_SECONDS:.2f}s apart "
            f"(first at {first:.3f}s and {second:.3f}s); confirm they read as separate hits"
        )

    if duration and len(cues) / duration > BUSY_CUES_PER_SECOND:
        warnings.append(
            f"{len(cues)} cues across {duration:.1f}s is dense; "
            "remove the cues that do not mark a visual event"
        )
    return warnings


def build_filter(cues: list[Cue], info: MediaInfo) -> str:
    chains: list[str] = []
    labels: list[str] = []

    if info.has_audio:
        chains.append(
            f"[0:a:0]aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:"
            "channel_layouts=stereo[base]"
        )
    else:
        chains.append(
            f"anullsrc=r={SAMPLE_RATE}:cl=stereo:d={info.duration:.6f}[base]"
        )

    for index, cue in enumerate(cues):
        parts: list[str] = []
        if cue.duration is not None:
            fade = min(0.05, cue.duration / 4)
            parts.append(f"atrim=0:{cue.duration:.6f}")
            parts.append("asetpts=PTS-STARTPTS")
            parts.append(
                f"afade=t=out:st={max(0.0, cue.duration - fade):.6f}:d={fade:.6f}"
            )
        parts.append(f"volume={cue.gain_db:.2f}dB")
        parts.append(
            f"aformat=sample_fmts=fltp:sample_rates={SAMPLE_RATE}:channel_layouts=stereo"
        )
        delay = round(cue.at * 1000)
        if delay > 0:
            parts.append(f"adelay={delay}|{delay}")
        chains.append(f"[{index + 1}:a]{','.join(parts)}[s{index}]")
        labels.append(f"[s{index}]")

    chains.append(
        f"[base]{''.join(labels)}amix=inputs={len(cues) + 1}:normalize=0:"
        f"duration=first:dropout_transition=0,"
        f"atrim=0:{info.duration:.6f},asetpts=PTS-STARTPTS,"
        "alimiter=limit=0.97[audio]"
    )
    return ";".join(chains)


def summary(cues: list[Cue], info: MediaInfo) -> str:
    names = sorted({cue.sound.name for cue in cues})
    return (
        f"Placed {len(cues)} cues from {len(names)} sounds "
        f"across {info.duration:.3f}s of video."
    )


def render(
    input_path: Path,
    cue_path: Path,
    output_path: Path,
    *,
    bitrate: str,
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

    _, _, cues = load_cues(cue_path)
    info = probe_media(input_path)
    validate_against_media(cues, info)
    filter_graph = build_filter(cues, info)

    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-v",
        "error",
        "-stats",
        "-i",
        str(input_path),
    ]
    for cue in cues:
        command.extend(["-i", str(cue.sound.path)])
    command.extend(
        [
            "-filter_complex",
            filter_graph,
            "-map",
            "0:v:0",
            "-map",
            "[audio]",
            "-map_metadata",
            "0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            bitrate,
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    subprocess.run(command, check=True)
    print(summary(cues, info))
    for warning in restraint_warnings(cues, info.duration):
        print(f"Warning: {warning}")
    print(f"Wrote {output_path}")


def argument_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="validate a cue sheet and its library")
    check.add_argument("cues", type=Path)
    check.add_argument("--input", type=Path)

    show_filter = commands.add_parser("filter", help="print the FFmpeg filter graph")
    show_filter.add_argument("input", type=Path)
    show_filter.add_argument("cues", type=Path)

    renderer = commands.add_parser("render", help="render a new video with sound effects")
    renderer.add_argument("input", type=Path)
    renderer.add_argument("cues", type=Path)
    renderer.add_argument("output", type=Path)
    renderer.add_argument("--bitrate", default="192k")
    renderer.add_argument("--overwrite", action="store_true")
    return root


def main() -> int:
    args = argument_parser().parse_args()
    try:
        if args.command == "check":
            _, library, cues = load_cues(args.cues)
            duration = None
            if args.input is not None:
                info = probe_media(args.input)
                validate_against_media(cues, info)
                duration = info.duration
            print(
                f"Valid schema 1 cue sheet with {len(cues)} cues "
                f"from a {len(library)} sound library."
            )
            for warning in restraint_warnings(cues, duration):
                print(f"Warning: {warning}")
            return 0

        if args.command == "filter":
            _, _, cues = load_cues(args.cues)
            info = probe_media(args.input)
            validate_against_media(cues, info)
            print(build_filter(cues, info))
            return 0

        render(
            args.input,
            args.cues,
            args.output,
            bitrate=args.bitrate,
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
