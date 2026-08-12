#!/usr/bin/env python3
"""Propose a conservative sound-effect cue sheet from scene changes and zoom cues."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIRECTORY))

from render_sfx import CueError, load_library, probe_media  # noqa: E402

PREFERRED_SOUNDS = {
    "transition": ("whoosh_short", "whoosh_in", "swipe"),
    "punch": ("whoosh_short", "whoosh_in", "pop_hard"),
    "step": ("pop_hard", "pop_soft", "click"),
    "push": ("riser", "whoosh_in", "whoosh_short"),
}
DEFAULT_GAIN_DB = -14.0


def choose_sound(role: str, library: dict[str, Any], missing: set[str]) -> str:
    for name in PREFERRED_SOUNDS[role]:
        if name in library:
            return name
    missing.add(role)
    return PREFERRED_SOUNDS[role][0]


def scene_changes(path: Path, threshold: float) -> list[float]:
    if shutil.which("ffmpeg") is None:
        raise CueError("ffmpeg is required but was not found on PATH")
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-i",
        str(path),
        "-filter:v",
        f"select='gt(scene,{threshold:.4f})',metadata=print:file=-",
        "-an",
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)

    times: list[float] = []
    for line in result.stdout.splitlines():
        marker = "pts_time:"
        if not line.startswith("frame:") or marker not in line:
            continue
        try:
            times.append(float(line.split(marker, 1)[1].split()[0]))
        except (IndexError, ValueError):
            continue
    return times


def zoom_moments(path: Path) -> list[tuple[float, str, str]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CueError(f"zoom cue sheet not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CueError(
            f"invalid JSON in {path} at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(document, dict) or not isinstance(document.get("events"), list):
        raise CueError(f"{path} is not an add-zooms cue sheet")

    moments: list[tuple[float, str, str]] = []
    for event in document["events"]:
        if not isinstance(event, dict):
            continue
        kind = event.get("kind")
        if kind == "punch" and isinstance(event.get("start"), (int, float)):
            moments.append((float(event["start"]), "punch", "zoom punch"))
        elif kind == "steps" and isinstance(event.get("beats"), list):
            for beat in event["beats"]:
                if isinstance(beat, dict) and isinstance(beat.get("start"), (int, float)):
                    moments.append((float(beat["start"]), "step", "zoom step"))
        elif kind == "push" and isinstance(event.get("start"), (int, float)):
            moments.append((float(event["start"]), "push", "zoom push"))
    return moments


def thin(
    proposals: list[tuple[float, str, str, float]], minimum_gap: float
) -> list[tuple[float, str, str, float]]:
    kept: list[tuple[float, str, str, float]] = []
    for proposal in sorted(proposals, key=lambda item: item[0]):
        if kept and proposal[0] - kept[-1][0] < minimum_gap:
            continue
        kept.append(proposal)
    return kept


def library_reference(library_path: Path, output_path: Path) -> str:
    try:
        return os.path.relpath(library_path, output_path.parent.resolve())
    except ValueError:
        return str(library_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--zooms", type=Path)
    parser.add_argument("--threshold", type=float, default=0.35)
    parser.add_argument("--lead", type=float, default=0.12)
    parser.add_argument("--min-gap", dest="minimum_gap", type=float, default=0.25)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        if args.output.exists() and not args.overwrite:
            raise CueError(
                f"output already exists: {args.output}; use --overwrite to replace it"
            )
        if not args.output.parent.is_dir():
            raise CueError(f"output directory does not exist: {args.output.parent}")
        if not 0.0 < args.threshold < 1.0:
            raise CueError("threshold must be between 0 and 1")
        if args.lead < 0:
            raise CueError("lead must be non-negative")
        if args.minimum_gap < 0:
            raise CueError("min-gap must be non-negative")

        library_path = args.library.resolve()
        library = load_library(library_path)
        info = probe_media(args.input)

        missing: set[str] = set()
        proposals: list[tuple[float, str, str, float]] = []

        cuts = scene_changes(args.input, args.threshold)
        for moment in cuts:
            proposals.append(
                (
                    max(0.0, moment - args.lead),
                    choose_sound("transition", library, missing),
                    "candidate scene change",
                    moment,
                )
            )

        zooms: list[tuple[float, str, str]] = []
        if args.zooms is not None:
            zooms = zoom_moments(args.zooms)
            for moment, role, note in zooms:
                proposals.append(
                    (
                        max(0.0, moment - args.lead),
                        choose_sound(role, library, missing),
                        f"candidate {note}",
                        moment,
                    )
                )

        kept = thin(proposals, args.minimum_gap)
        kept = [proposal for proposal in kept if proposal[0] < info.duration]

        warning = ""
        if missing:
            wanted = ", ".join(
                f"{role} -> {PREFERRED_SOUNDS[role][0]}" for role in sorted(missing)
            )
            warning = (
                f"The library has no sound for: {wanted}. "
                "Add those names to the library or edit the cue sheet before rendering."
            )
        elif cuts and len(cuts) / info.duration > 1.0:
            warning = (
                f"Scene detection returned {len(cuts)} changes in {info.duration:.1f}s. "
                "Raise --threshold; this footage is probably high-motion, not fast-cut."
            )

        document = {
            "schema": 1,
            "library": library_reference(library_path, args.output),
            "gain_db": DEFAULT_GAIN_DB,
            "cues": [
                {
                    "at": round(at, 3),
                    "sound": sound,
                    "slot": "transition",
                    "note": note,
                    "visual_at": round(visual_at, 3),
                }
                for at, sound, note, visual_at in kept
            ],
            "analysis": {
                "source_duration": round(info.duration, 3),
                "scene_threshold": args.threshold,
                "scene_changes": len(cuts),
                "zoom_moments": len(zooms),
                "lead_seconds": args.lead,
                "minimum_gap_seconds": args.minimum_gap,
                "proposed": len(proposals),
                "kept": len(kept),
                "warning": warning,
            },
        }
        args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

        print(
            f"Analyzed {info.duration:.3f}s: {len(cuts)} scene changes, "
            f"{len(zooms)} zoom moments."
        )
        print(f"Proposed {len(proposals)} cues and kept {len(kept)} after thinning.")
        if warning:
            print(f"Warning: {warning}")
        print(f"Wrote candidate cue sheet to {args.output}")
        print(
            "These are transition candidates only. "
            "Add intro text, overlay, and visual example cues by watching the video."
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
