#!/usr/bin/env python3
"""Create a local HTML review sheet for B-roll manifest candidates."""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from broll_manifest import (
    ManifestError,
    candidate_total,
    load_document,
    validate_document,
)


class SheetError(ValueError):
    """Raised when a contact sheet cannot be created safely."""


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


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
    return cleaned or "candidate"


def local_candidate_path(
    candidate: dict[str, Any], manifest_path: Path
) -> Path | None:
    raw_path = candidate.get("local_path")
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path.resolve()


def video_midpoint(path: Path) -> float:
    if shutil.which("ffprobe") is None:
        raise SheetError("ffprobe is required to preview video candidates")
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        duration = float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as exc:
        raise SheetError(f"could not probe candidate video: {path}") from exc
    return max(0.0, duration / 2)


def create_thumbnail(source: Path, output: Path, *, overwrite: bool) -> None:
    if shutil.which("ffmpeg") is None:
        raise SheetError("ffmpeg is required to create candidate thumbnails")
    if output.exists() and not overwrite:
        return

    command = ["ffmpeg", "-y" if overwrite else "-n", "-v", "error"]
    if source.suffix.lower() not in IMAGE_EXTENSIONS:
        command.extend(["-ss", f"{video_midpoint(source):.3f}"])
    command.extend(
        [
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-vf",
            "scale=480:270:force_original_aspect_ratio=decrease,"
            "pad=480:270:(ow-iw)/2:(oh-ih)/2:color=0x12131A",
            "-q:v",
            "3",
            str(output),
        ]
    )
    subprocess.run(command, check=True)


def score_rows(candidate: dict[str, Any]) -> str:
    labels = {
        "accuracy": "Accuracy",
        "authority": "Authority",
        "rights": "Rights",
        "clarity": "Clarity",
        "format": "Format",
        "freshness": "Freshness",
    }
    return "".join(
        f"<span>{labels[key]} {value:g}</span>"
        for key, value in candidate["scores"].items()
    )


def candidate_card(
    beat: dict[str, Any],
    candidate: dict[str, Any],
    thumbnail: Path | None,
    output_dir: Path,
) -> str:
    score = candidate_total(candidate, f"{beat['id']}.{candidate['id']}")
    rights_status = html.escape(candidate["rights"]["status"])
    selected = beat.get("selected_candidate") == candidate["id"]
    selected_badge = '<span class="selected">SELECTED</span>' if selected else ""
    if thumbnail is not None:
        preview = (
            f'<img src="{html.escape(thumbnail.relative_to(output_dir).as_posix())}" '
            f'alt="Preview of {html.escape(candidate["title"])}">'
        )
    else:
        preview = (
            '<div class="placeholder">No local preview<br>'
            "Open the original source link</div>"
        )

    return f"""
      <article class="candidate">
        {preview}
        <div class="card-body">
          <div class="score">{score:.0f}/100 {selected_badge}</div>
          <h3>{html.escape(candidate["title"])}</h3>
          <p class="publisher">{html.escape(candidate["publisher"])}</p>
          <div class="score-grid">{score_rows(candidate)}</div>
          <p><strong>Rights:</strong> {rights_status} — {html.escape(candidate["rights"]["note"])}</p>
          <a href="{html.escape(candidate["url"], quote=True)}">Open original source ↗</a>
        </div>
      </article>
    """


def build_html(
    document: dict[str, Any],
    manifest_path: Path,
    output_dir: Path,
    thumbnails: dict[tuple[str, str], Path],
) -> str:
    beat_sections: list[str] = []
    for beat in document["beats"]:
        cards = "".join(
            candidate_card(
                beat,
                candidate,
                thumbnails.get((beat["id"], candidate["id"])),
                output_dir,
            )
            for candidate in beat["candidates"]
        )
        if not cards:
            cards = '<p class="empty">No candidates have been added yet.</p>'
        queries = " · ".join(html.escape(query) for query in beat["queries"])
        beat_sections.append(
            f"""
            <section class="beat">
              <div class="beat-head">
                <span class="time">{beat["start"]:.2f}–{beat["end"]:.2f}s</span>
                <span class="route">{html.escape(beat["route"])}</span>
                <span class="status">{html.escape(beat["status"])}</span>
              </div>
              <h2>{html.escape(beat["spoken_text"])}</h2>
              <p class="intent">{html.escape(beat["intent"])}</p>
              <p class="queries"><strong>Search:</strong> {queries or "—"}</p>
              <div class="cards">{cards}</div>
            </section>
            """
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(document["project"])} — B-roll review</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0f1017;
      --panel: #191922;
      --line: #34313d;
      --text: #f8f6fa;
      --muted: #aaa5b2;
      --accent: #ff7a66;
      --gold: #f3b36a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top right, #2b1a28, var(--bg) 38rem);
      color: var(--text);
      font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; padding: 64px 0 100px; }}
    header {{ margin-bottom: 42px; }}
    h1 {{ margin: 8px 0; font-size: clamp(34px, 6vw, 64px); letter-spacing: -0.045em; }}
    .eyebrow, .time, .route, .status {{
      color: var(--accent); font-size: 12px; font-weight: 750; letter-spacing: .08em; text-transform: uppercase;
    }}
    .summary, .intent, .queries, .publisher {{ color: var(--muted); }}
    .beat {{ border-top: 1px solid var(--line); padding: 36px 0 46px; }}
    .beat-head {{ display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }}
    .route, .status {{ border: 1px solid var(--line); border-radius: 999px; padding: 3px 9px; color: #d7d2dc; }}
    h2 {{ margin: 14px 0 4px; font-size: clamp(22px, 3vw, 34px); letter-spacing: -.025em; }}
    .intent {{ font-size: 17px; max-width: 780px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; margin-top: 24px; }}
    .candidate {{ overflow: hidden; background: color-mix(in srgb, var(--panel) 92%, transparent); border: 1px solid var(--line); border-radius: 18px; }}
    .candidate img, .placeholder {{ width: 100%; aspect-ratio: 16/9; object-fit: cover; background: #12131a; }}
    .placeholder {{ display: grid; place-content: center; text-align: center; color: #77717e; }}
    .card-body {{ padding: 19px; }}
    h3 {{ margin: 6px 0 0; font-size: 19px; }}
    .publisher {{ margin: 2px 0 14px; }}
    .score {{ color: var(--gold); font-weight: 800; }}
    .selected {{ margin-left: 8px; border: 1px solid var(--accent); border-radius: 999px; padding: 2px 7px; color: #ffd2cb; font-size: 10px; }}
    .score-grid {{ display: flex; flex-wrap: wrap; gap: 5px 10px; color: #c6c0ca; font-size: 12px; }}
    a {{ color: #ffb09f; text-decoration: none; font-weight: 700; }}
    a:hover {{ text-decoration: underline; }}
    .empty {{ color: var(--muted); }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">B-roll candidate review</div>
      <h1>{html.escape(document["project"])}</h1>
      <p class="summary">{len(document["beats"])} planned beats · {document["source_duration"]:.2f}s source · generated locally</p>
    </header>
    {"".join(beat_sections)}
  </main>
</body>
</html>
"""


def create_sheet(
    manifest_path: Path, output_dir: Path, *, overwrite: bool
) -> None:
    manifest_path = manifest_path.resolve()
    document = load_document(manifest_path)
    validate_document(document, manifest_path)

    if output_dir.exists() and not output_dir.is_dir():
        raise SheetError(f"output is not a directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.html"
    if index_path.exists() and not overwrite:
        raise SheetError(
            f"review already exists: {index_path}; use --overwrite to replace it"
        )
    thumbnail_dir = output_dir / "thumbnails"
    thumbnail_dir.mkdir(exist_ok=True)

    thumbnails: dict[tuple[str, str], Path] = {}
    for beat in document["beats"]:
        for candidate in beat["candidates"]:
            local_path = local_candidate_path(candidate, manifest_path)
            if local_path is None or not local_path.is_file():
                continue
            thumbnail = thumbnail_dir / (
                f"{slug(beat['id'])}--{slug(candidate['id'])}.jpg"
            )
            create_thumbnail(local_path, thumbnail, overwrite=overwrite)
            thumbnails[(beat["id"], candidate["id"])] = thumbnail

    index_path.write_text(
        build_html(document, manifest_path, output_dir, thumbnails),
        encoding="utf-8",
    )
    print(
        f"Wrote {index_path} with {len(thumbnails)} local candidate previews."
    )


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = argument_parser().parse_args()
    try:
        create_sheet(args.manifest, args.output, overwrite=args.overwrite)
        return 0
    except (ManifestError, SheetError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"error: command failed with exit code {exc.returncode}", file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
