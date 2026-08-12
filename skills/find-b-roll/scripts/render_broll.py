#!/usr/bin/env python3
"""Render approved local B-roll over a source video with FFmpeg."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from broll_manifest import (
    ManifestError,
    load_document,
    selected_beats,
    validate_document,
)


class RenderError(ValueError):
    """Raised when B-roll cannot be rendered safely."""


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    width: int
    height: int
    has_audio: bool


IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def probe_video(path: Path) -> MediaInfo:
    if shutil.which("ffprobe") is None:
        raise RenderError("ffprobe is required but was not found on PATH")
    if not path.is_file():
        raise RenderError(f"media not found: {path}")

    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height:format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(result.stdout)
        streams = payload["streams"]
        video = next(
            stream for stream in streams if stream.get("codec_type") == "video"
        )
        duration = float(payload["format"]["duration"])
        info = MediaInfo(
            duration=duration,
            width=int(video["width"]),
            height=int(video["height"]),
            has_audio=any(stream.get("codec_type") == "audio" for stream in streams),
        )
    except (
        subprocess.CalledProcessError,
        StopIteration,
        KeyError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise RenderError(f"could not probe a usable video: {path}") from exc
    if info.duration <= 0 or info.width < 2 or info.height < 2:
        raise RenderError(f"media has invalid duration or dimensions: {path}")
    return info


def verify_asset_video(path: Path) -> None:
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return
    probe_video(path)


def build_filter(
    approved: list[tuple[dict[str, Any], dict[str, Any], Path]],
    *,
    width: int,
    height: int,
    source_duration: float,
) -> str:
    chains = ["[0:v:0]setpts=PTS-STARTPTS,setsar=1[base0]"]

    for index, (beat, _candidate, _path) in enumerate(approved, start=1):
        start = float(beat["start"])
        end = float(beat["end"])
        duration = end - start
        chains.append(
            f"[{index}:v:0]trim=start=0:duration={duration:.6f},"
            "setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=increase:"
            "flags=lanczos,"
            f"crop={width}:{height},setsar=1,"
            f"setpts=PTS+{start:.6f}/TB[b{index}]"
        )
        chains.append(
            f"[base{index - 1}][b{index}]overlay=0:0:eof_action=pass:"
            f"enable='between(t,{start:.6f},{end:.6f})'[base{index}]"
        )

    final_input = f"[base{len(approved)}]"
    chains.append(
        f"{final_input}trim=start=0:duration={source_duration:.6f},"
        "setpts=PTS-STARTPTS[video]"
    )
    return ";".join(chains)


def render(
    source: Path,
    manifest_path: Path,
    output: Path,
    *,
    crf: int,
    preset: str,
    overwrite: bool,
    allow_unverified_rights: bool,
    dry_run: bool,
) -> None:
    if shutil.which("ffmpeg") is None:
        raise RenderError("ffmpeg is required but was not found on PATH")
    if source.resolve() == output.resolve():
        raise RenderError("output must be different from the source")
    if output.exists() and not overwrite:
        raise RenderError(
            f"output already exists: {output}; use --overwrite to replace it"
        )
    if not output.parent.is_dir():
        raise RenderError(f"output directory does not exist: {output.parent}")
    if not 0 <= crf <= 51:
        raise RenderError("crf must be between 0 and 51")

    manifest_path = manifest_path.resolve()
    document = load_document(manifest_path)
    validate_document(
        document,
        manifest_path,
        render_ready=True,
        verify_assets=True,
        allow_unverified_rights=allow_unverified_rights,
    )
    approved = selected_beats(document, manifest_path)
    source_info = probe_video(source)

    declared_duration = float(document["source_duration"])
    if abs(declared_duration - source_info.duration) > 0.25:
        raise RenderError(
            f"manifest source_duration is {declared_duration:.3f}s but source is "
            f"{source_info.duration:.3f}s"
        )
    target = document["target"]
    target_width = int(target["width"])
    target_height = int(target["height"])
    if (target_width, target_height) != (source_info.width, source_info.height):
        raise RenderError(
            "manifest target must match source dimensions; reframe the source first "
            f"or use {source_info.width}x{source_info.height}"
        )

    for _beat, _candidate, asset_path in approved:
        if asset_path.resolve() == output.resolve():
            raise RenderError("output must be different from every B-roll asset")
        verify_asset_video(asset_path)

    filter_graph = build_filter(
        approved,
        width=source_info.width,
        height=source_info.height,
        source_duration=source_info.duration,
    )
    command = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-v",
        "error",
        "-stats",
        "-i",
        str(source),
    ]

    for _beat, _candidate, asset_path in approved:
        if asset_path.suffix.lower() in IMAGE_EXTENSIONS:
            command.extend(["-loop", "1", "-framerate", "30", "-i", str(asset_path)])
        else:
            command.extend(["-stream_loop", "-1", "-i", str(asset_path)])

    command.extend(
        [
            "-filter_complex",
            filter_graph,
            "-map",
            "[video]",
            "-map",
            "0:a?",
            "-map_metadata",
            "0",
            "-c:v",
            "libx264",
            "-crf",
            str(crf),
            "-preset",
            preset,
            "-pix_fmt",
            "yuv420p",
        ]
    )
    if source_info.has_audio:
        command.extend(["-c:a", "aac", "-b:a", "192k"])
    command.extend(["-movflags", "+faststart", str(output)])

    if dry_run:
        print(filter_graph)
        print("Inputs:")
        print(f"  source: {source}")
        for beat, candidate, asset_path in approved:
            print(
                f"  {beat['id']} {beat['start']:.3f}-{beat['end']:.3f}: "
                f"{candidate['id']} -> {asset_path}"
            )
        return

    subprocess.run(command, check=True)
    output_info = probe_video(output)
    if (output_info.width, output_info.height) != (
        source_info.width,
        source_info.height,
    ):
        raise RenderError("rendered dimensions do not match the source")
    if abs(output_info.duration - source_info.duration) > 0.15:
        raise RenderError(
            f"rendered duration drifted by "
            f"{abs(output_info.duration - source_info.duration):.3f}s"
        )
    if source_info.has_audio and not output_info.has_audio:
        raise RenderError("rendered output lost the source audio")

    coverage = sum(float(beat["end"]) - float(beat["start"]) for beat, _, _ in approved)
    print(
        f"Rendered {len(approved)} approved beats covering {coverage:.3f}s "
        f"of the {source_info.duration:.3f}s source."
    )
    print(f"Wrote {output}")


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--crf", type=int, default=19)
    parser.add_argument(
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
        default="fast",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--allow-unverified-rights", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = argument_parser().parse_args()
    try:
        render(
            args.source,
            args.manifest,
            args.output,
            crf=args.crf,
            preset=args.preset,
            overwrite=args.overwrite,
            allow_unverified_rights=args.allow_unverified_rights,
            dry_run=args.dry_run,
        )
        return 0
    except (ManifestError, RenderError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"error: command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
