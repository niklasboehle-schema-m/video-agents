#!/usr/bin/env python3
"""Create a standalone local HTML report from a structure manifest."""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path
from typing import Any

from structure_manifest import (
    StructureError,
    load_document,
    originality_issues,
    validate_document,
    word_tokens,
)


class ReportError(ValueError):
    """Raised when a report cannot be created safely."""


FUNCTION_COLORS = {
    "pattern-break": "#7DD3FC",
    "promise": "#67E8F9",
    "context": "#94A3B8",
    "problem": "#FB7185",
    "proof": "#4ADE80",
    "mechanism": "#C4A7FF",
    "contrast": "#F59E0B",
    "open-loop": "#F472B6",
    "step": "#60A5FA",
    "reveal": "#A78BFA",
    "application": "#2DD4BF",
    "recap": "#A3E635",
    "bridge": "#CBD5E1",
    "cta": "#FF8A70",
}


def esc(value: Any) -> str:
    return html.escape(str(value))


def pace(text: str, duration: float) -> float:
    return len(word_tokens(text)) / duration if duration > 0 else 0.0


def source_link(source: dict[str, Any]) -> str:
    if source.get("url"):
        return (
            f'<a href="{html.escape(source["url"], quote=True)}">'
            f"{esc(source['title'])} ↗</a>"
        )
    return esc(source.get("provenance", source["title"]))


def timeline(document: dict[str, Any]) -> str:
    duration = float(document["source"]["duration"])
    parts: list[str] = []
    cursor = 0.0
    for beat in document["beats"]:
        start = float(beat["start"])
        end = float(beat["end"])
        if start > cursor:
            parts.append(
                f'<div class="gap" style="width:{(start - cursor) / duration * 100:.4f}%"></div>'
            )
        color = FUNCTION_COLORS[beat["function"]]
        parts.append(
            f'<div class="timeline-beat" title="{esc(beat["id"])} · '
            f'{esc(beat["function"])} · {start:.2f}–{end:.2f}s" '
            f'style="width:{(end - start) / duration * 100:.4f}%;'
            f'background:{color}"></div>'
        )
        cursor = end
    if cursor < duration:
        parts.append(
            f'<div class="gap" style="width:{(duration - cursor) / duration * 100:.4f}%"></div>'
        )
    return "".join(parts)


def beat_card(beat: dict[str, Any]) -> str:
    duration = float(beat["end"]) - float(beat["start"])
    source_pace = pace(beat["source_text"], duration)
    rewrite = beat.get("rewrite")
    rewrite_html = '<p class="missing">No transferred line yet.</p>'
    if isinstance(rewrite, dict):
        line = rewrite.get("line", "")
        target = float(rewrite["target_duration"])
        rewrite_pace = pace(line, target) if line else 0.0
        rewrite_html = f"""
          <div class="rewrite-meta">
            <span>{esc(rewrite["status"])}</span>
            <span>{target:.2f}s target</span>
            <span>{rewrite_pace:.2f} words/s</span>
          </div>
          <p class="objective">{esc(rewrite["objective"])}</p>
          <blockquote>{esc(line) if line else "—"}</blockquote>
        """

    return f"""
      <section class="beat">
        <div class="beat-top">
          <div>
            <span class="time">{float(beat["start"]):.2f}–{float(beat["end"]):.2f}s</span>
            <span class="function" style="--beat-color:{FUNCTION_COLORS[beat["function"]]}">{esc(beat["function"])}</span>
          </div>
          <span class="pace">{source_pace:.2f} source words/s</span>
        </div>
        <h2>{esc(beat["job"])}</h2>
        <div class="state-grid">
          <div><strong>Before</strong><p>{esc(beat["audience_before"])}</p></div>
          <div><strong>After</strong><p>{esc(beat["audience_after"])}</p></div>
        </div>
        <div class="source-line">
          <span>REFERENCE TRANSCRIPT</span>
          <p>{esc(beat["source_text"])}</p>
        </div>
        <div class="logic-grid">
          <div><strong>Information gain</strong><p>{esc(beat["information_gain"])}</p></div>
          <div><strong>Handoff</strong><p>{esc(beat["handoff"])}</p></div>
        </div>
        <div class="rewrite">
          <span class="section-label">ORIGINAL TRANSFER</span>
          {rewrite_html}
        </div>
      </section>
    """


def build_html(document: dict[str, Any]) -> str:
    strategy = document["strategy"]
    source = document["source"]
    issues = originality_issues(document)
    issue_html = (
        "".join(f"<li>{esc(issue)}</li>" for issue in issues)
        if issues
        else "<li>No mechanical similarity warnings.</li>"
    )
    beats = "".join(beat_card(beat) for beat in document["beats"])
    drivers = "".join(
        f"<span>{esc(driver)}</span>" for driver in strategy["retention_drivers"]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(document["project"])} — structure report</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0e0f16;
      --panel: #171821;
      --line: #33313e;
      --text: #f7f5f9;
      --muted: #aaa5b2;
      --blue: #7dd3fc;
      --violet: #c4a7ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: radial-gradient(circle at top right, #24192b, var(--bg) 42rem);
      color: var(--text);
      font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 68px 0 100px; }}
    a {{ color: #bde9ff; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .eyebrow, .section-label, .source-line span {{
      color: var(--blue); font-size: 11px; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
    }}
    h1 {{ margin: 9px 0 6px; font-size: clamp(38px, 7vw, 72px); letter-spacing: -.05em; line-height: 1; }}
    .source {{ color: var(--muted); font-size: 16px; }}
    .strategy {{
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px;
      margin: 38px 0 24px;
    }}
    .strategy > div, .originality {{
      background: color-mix(in srgb, var(--panel) 92%, transparent);
      border: 1px solid var(--line); border-radius: 16px; padding: 18px;
    }}
    .strategy strong {{ display: block; margin-bottom: 6px; color: #d9d4df; }}
    .strategy p {{ margin: 0; color: var(--muted); }}
    .drivers {{ display: flex; flex-wrap: wrap; gap: 7px; margin-top: 12px; }}
    .drivers span, .rewrite-meta span {{
      border: 1px solid var(--line); border-radius: 999px; padding: 3px 9px; color: #d8d3dd; font-size: 12px;
    }}
    .timeline {{ display: flex; height: 30px; gap: 3px; margin: 30px 0 55px; }}
    .timeline-beat, .gap {{ min-width: 2px; border-radius: 7px; }}
    .gap {{ background: #292731; }}
    .beat {{ border-top: 1px solid var(--line); padding: 34px 0 44px; }}
    .beat-top {{ display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; }}
    .time {{ color: var(--blue); font-weight: 800; }}
    .function {{
      margin-left: 9px; border: 1px solid color-mix(in srgb, var(--beat-color) 45%, transparent);
      border-radius: 999px; padding: 3px 9px; color: var(--beat-color);
      font-size: 12px; font-weight: 800; text-transform: uppercase;
    }}
    .pace {{ color: var(--muted); font-size: 13px; }}
    h2 {{ margin: 14px 0 22px; font-size: clamp(24px, 4vw, 36px); letter-spacing: -.03em; }}
    .state-grid, .logic-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
    .state-grid > div, .logic-grid > div, .source-line, .rewrite {{
      border: 1px solid var(--line); border-radius: 15px; padding: 17px; background: #15161e;
    }}
    .state-grid strong, .logic-grid strong {{ color: #d8d3dd; }}
    .state-grid p, .logic-grid p, .objective {{ color: var(--muted); margin: 5px 0 0; }}
    .source-line {{ margin: 14px 0; }}
    .source-line p {{ margin: 7px 0 0; font-size: 17px; }}
    .rewrite {{ margin-top: 14px; border-color: #4a3d61; background: #191622; }}
    .rewrite-meta {{ display: flex; gap: 7px; flex-wrap: wrap; margin: 10px 0; }}
    blockquote {{ margin: 13px 0 0; font-size: 22px; line-height: 1.4; color: #f2eaff; }}
    .missing {{ color: var(--muted); }}
    .originality {{ margin-top: 36px; }}
    .originality h2 {{ margin-top: 5px; }}
    .originality li {{ color: var(--muted); margin: 6px 0; }}
    @media (max-width: 760px) {{
      .strategy, .state-grid, .logic-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">Functional structure analysis</div>
      <h1>{esc(document["project"])}</h1>
      <p class="source">{source_link(source)} · {float(source["duration"]):.2f}s · transcript {esc(source["transcript_confidence"])}</p>
    </header>

    <div class="strategy">
      <div><strong>Audience</strong><p>{esc(strategy["audience"])}</p></div>
      <div><strong>Opening contract</strong><p>{esc(strategy["opening_contract"])}</p></div>
      <div><strong>Payoff</strong><p>{esc(strategy["payoff"])}</p></div>
    </div>
    <div class="drivers">{drivers}</div>
    <div class="timeline">{timeline(document)}</div>

    {beats}

    <section class="originality">
      <div class="eyebrow">Originality guard</div>
      <h2>Mechanical similarity check</h2>
      <ul>{issue_html}</ul>
    </section>
  </main>
</body>
</html>
"""


def make_report(
    manifest_path: Path, output_path: Path, *, overwrite: bool
) -> None:
    document = load_document(manifest_path)
    validate_document(document)
    if output_path.exists() and not overwrite:
        raise ReportError(
            f"output already exists: {output_path}; use --overwrite to replace it"
        )
    if not output_path.parent.is_dir():
        raise ReportError(f"output directory does not exist: {output_path.parent}")
    output_path.write_text(build_html(document), encoding="utf-8")
    print(f"Wrote {output_path}")


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = argument_parser().parse_args()
    try:
        make_report(args.manifest, args.output, overwrite=args.overwrite)
        return 0
    except (StructureError, ReportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
