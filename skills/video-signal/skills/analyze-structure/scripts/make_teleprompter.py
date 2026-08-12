#!/usr/bin/env python3
"""Create a standalone local teleprompter from approved rewrite lines."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

from structure_manifest import (
    StructureError,
    approved_rewrites,
    load_document,
    originality_issues,
    validate_document,
)


class PrompterError(ValueError):
    """Raised when a teleprompter cannot be created safely."""


def build_html(
    document: dict,
    *,
    include_drafts: bool,
) -> str:
    selected = approved_rewrites(document, include_drafts=include_drafts)
    items = [
        {
            "id": beat["id"],
            "function": beat["function"],
            "text": rewrite["line"].strip(),
            "seconds": float(rewrite["target_duration"]),
            "status": rewrite["status"],
        }
        for beat, rewrite in selected
    ]
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    title = html.escape(document["project"])
    total_seconds = sum(item["seconds"] for item in items)
    first = items[0]
    next_text = items[1]["text"] if len(items) > 1 else "End"
    initial_dots = "".join(
        '<span class="active"></span>' if index == 0 else "<span></span>"
        for index in range(len(items))
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — teleprompter</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08090d;
      --panel: #11121a;
      --text: #fbf9fc;
      --muted: #8f8a96;
      --accent: #7dd3fc;
      --violet: #c4a7ff;
      --font-size: 64px;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ width: 100%; height: 100%; margin: 0; overflow: hidden; }}
    body {{
      background: radial-gradient(circle at top, #171526, var(--bg) 55%);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    body.mirrored .stage {{ transform: scaleX(-1); }}
    .app {{ height: 100%; display: grid; grid-template-rows: auto 1fr auto; }}
    header {{
      display: flex; justify-content: space-between; gap: 20px; align-items: center;
      padding: 18px 24px; border-bottom: 1px solid #292833; background: #0c0d13e8;
    }}
    .title {{ min-width: 0; }}
    h1 {{ margin: 0; font-size: 18px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .meta {{ color: var(--muted); font-size: 12px; margin-top: 3px; }}
    .controls {{ display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }}
    button {{
      appearance: none; border: 1px solid #3a3744; background: #171821; color: #eeeaf1;
      border-radius: 10px; padding: 9px 13px; font: inherit; font-size: 13px; font-weight: 700;
      cursor: pointer;
    }}
    button:hover {{ border-color: #6b617a; }}
    button.primary {{ border-color: #4183a1; background: #143142; color: #cdefff; }}
    .stage {{
      display: grid; place-items: center; align-content: center; text-align: center;
      padding: clamp(24px, 6vw, 90px); transition: transform .2s ease;
    }}
    .function {{
      color: var(--accent); font-size: 13px; font-weight: 800; letter-spacing: .14em;
      text-transform: uppercase; margin-bottom: 24px;
    }}
    .current {{
      max-width: 1200px; font-size: var(--font-size); line-height: 1.16; font-weight: 760;
      letter-spacing: -.035em; text-wrap: balance;
    }}
    .next {{
      max-width: 900px; margin-top: 42px; color: #75717c; font-size: calc(var(--font-size) * .34);
      line-height: 1.3; text-wrap: balance;
    }}
    footer {{ padding: 0 24px 22px; }}
    .footer-top {{ display: flex; justify-content: space-between; color: var(--muted); font-size: 13px; margin-bottom: 9px; }}
    .bar {{ height: 8px; border-radius: 999px; background: #22212a; overflow: hidden; }}
    .bar > div {{ height: 100%; width: 0; background: linear-gradient(90deg, var(--accent), var(--violet)); transition: width .08s linear; }}
    .beat-dots {{ display: flex; gap: 5px; margin-top: 10px; }}
    .beat-dots span {{ height: 3px; flex: 1; border-radius: 99px; background: #292832; }}
    .beat-dots span.done {{ background: #6a8fa3; }}
    .beat-dots span.active {{ background: var(--accent); }}
    @media (max-width: 720px) {{
      :root {{ --font-size: 42px; }}
      header {{ align-items: flex-start; }}
      .controls {{ gap: 5px; }}
      button {{ padding: 7px 9px; }}
    }}
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="title">
        <h1>{title}</h1>
        <div class="meta">{len(items)} beats · {total_seconds:.1f}s target · Space to play/pause</div>
      </div>
      <div class="controls">
        <button id="prev">← Previous</button>
        <button id="play" class="primary">Start</button>
        <button id="next">Next →</button>
        <button id="reset">Reset</button>
        <button id="slower">− Speed</button>
        <button id="faster">+ Speed</button>
        <button id="smaller">A−</button>
        <button id="larger">A+</button>
        <button id="mirror">Mirror</button>
      </div>
    </header>

    <main class="stage">
      <div id="function" class="function">{html.escape(first["function"].replace("-", " "))}</div>
      <div id="current" class="current">{html.escape(first["text"])}</div>
      <div id="nextLine" class="next">{html.escape(next_text)}</div>
    </main>

    <footer>
      <div class="footer-top">
        <span id="position">Beat 1 of {len(items)}</span>
        <span id="timer">{first["seconds"]:.1f}s</span>
        <span id="speed">1.00×</span>
      </div>
      <div class="bar"><div id="progress"></div></div>
      <div id="dots" class="beat-dots">{initial_dots}</div>
    </footer>
  </div>

  <script>
    const items = {payload};
    const els = {{
      function: document.getElementById("function"),
      current: document.getElementById("current"),
      nextLine: document.getElementById("nextLine"),
      position: document.getElementById("position"),
      timer: document.getElementById("timer"),
      speed: document.getElementById("speed"),
      progress: document.getElementById("progress"),
      dots: document.getElementById("dots"),
      play: document.getElementById("play"),
    }};
    let index = 0;
    let elapsed = 0;
    let running = false;
    let speed = 1;
    let fontSize = 64;
    let previousFrame = null;

    function duration() {{
      return items[index].seconds / speed;
    }}

    function render() {{
      const item = items[index];
      els.function.textContent = item.function.replaceAll("-", " ");
      els.current.textContent = item.text;
      els.nextLine.textContent = index + 1 < items.length ? items[index + 1].text : "End";
      els.position.textContent = `Beat ${{index + 1}} of ${{items.length}}`;
      els.timer.textContent = `${{Math.max(0, duration() - elapsed).toFixed(1)}}s`;
      els.speed.textContent = `${{speed.toFixed(2)}}×`;
      els.progress.style.width = `${{Math.min(100, elapsed / duration() * 100)}}%`;
      els.play.textContent = running ? "Pause" : (elapsed > 0 ? "Continue" : "Start");
      els.dots.innerHTML = items.map((_, dotIndex) =>
        `<span class="${{dotIndex < index ? "done" : dotIndex === index ? "active" : ""}}"></span>`
      ).join("");
      document.documentElement.style.setProperty("--font-size", `${{fontSize}}px`);
    }}

    function go(nextIndex) {{
      index = Math.max(0, Math.min(items.length - 1, nextIndex));
      elapsed = 0;
      previousFrame = null;
      render();
    }}

    function toggle() {{
      running = !running;
      previousFrame = null;
      render();
      if (running) requestAnimationFrame(tick);
    }}

    function tick(now) {{
      if (!running) return;
      if (previousFrame !== null) elapsed += (now - previousFrame) / 1000;
      previousFrame = now;
      if (elapsed >= duration()) {{
        if (index + 1 < items.length) {{
          index += 1;
          elapsed = 0;
        }} else {{
          elapsed = duration();
          running = false;
        }}
      }}
      render();
      if (running) requestAnimationFrame(tick);
    }}

    document.getElementById("play").addEventListener("click", toggle);
    document.getElementById("prev").addEventListener("click", () => go(index - 1));
    document.getElementById("next").addEventListener("click", () => go(index + 1));
    document.getElementById("reset").addEventListener("click", () => {{
      running = false; go(0);
    }});
    document.getElementById("slower").addEventListener("click", () => {{
      speed = Math.max(.5, speed - .1); render();
    }});
    document.getElementById("faster").addEventListener("click", () => {{
      speed = Math.min(2, speed + .1); render();
    }});
    document.getElementById("smaller").addEventListener("click", () => {{
      fontSize = Math.max(28, fontSize - 4); render();
    }});
    document.getElementById("larger").addEventListener("click", () => {{
      fontSize = Math.min(120, fontSize + 4); render();
    }});
    document.getElementById("mirror").addEventListener("click", () => {{
      document.body.classList.toggle("mirrored");
    }});
    document.addEventListener("keydown", event => {{
      if (event.code === "Space") {{
        event.preventDefault(); toggle();
      }} else if (event.code === "ArrowLeft") {{
        go(index - 1);
      }} else if (event.code === "ArrowRight") {{
        go(index + 1);
      }}
    }});
    render();
  </script>
</body>
</html>
"""


def make_prompter(
    manifest_path: Path,
    output_path: Path,
    *,
    include_drafts: bool,
    allow_similarity_warnings: bool,
    overwrite: bool,
) -> None:
    document = load_document(manifest_path)
    validate_document(document, require_rewrite=True)
    selected = approved_rewrites(document, include_drafts=include_drafts)
    if not selected:
        raise PrompterError("no approved rewrite lines found")
    issues = originality_issues(document)
    if issues and not allow_similarity_warnings:
        raise PrompterError(
            "originality warnings must be resolved before export: " + issues[0]
        )
    if output_path.exists() and not overwrite:
        raise PrompterError(
            f"output already exists: {output_path}; use --overwrite to replace it"
        )
    if not output_path.parent.is_dir():
        raise PrompterError(f"output directory does not exist: {output_path.parent}")
    output_path.write_text(
        build_html(document, include_drafts=include_drafts),
        encoding="utf-8",
    )
    print(f"Wrote {output_path} with {len(selected)} script beats.")


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--include-drafts", action="store_true")
    parser.add_argument("--allow-similarity-warnings", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> int:
    args = argument_parser().parse_args()
    try:
        make_prompter(
            args.manifest,
            args.output,
            include_drafts=args.include_drafts,
            allow_similarity_warnings=args.allow_similarity_warnings,
            overwrite=args.overwrite,
        )
        return 0
    except (StructureError, PrompterError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
