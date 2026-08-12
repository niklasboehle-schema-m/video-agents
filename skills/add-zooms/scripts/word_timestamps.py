#!/usr/bin/env python3
"""Print word timings from common Whisper JSON layouts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def collect_words(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        raise TypeError("transcript root must be an object")

    candidates = document.get("words")
    if candidates is None:
        segments = document.get("segments")
        if not isinstance(segments, list):
            raise ValueError("transcript must contain words or segments")
        candidates = []
        for segment in segments:
            if isinstance(segment, dict) and isinstance(segment.get("words"), list):
                candidates.extend(segment["words"])

    if not isinstance(candidates, list):
        raise TypeError("words must be an array")

    normalized = []
    for index, item in enumerate(candidates):
        if not isinstance(item, dict):
            raise TypeError(f"word {index} must be an object")
        text = item.get("word", item.get("text"))
        start = item.get("start")
        end = item.get("end")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"word {index} has no text")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise TypeError(f"word {index} has invalid timing")
        if float(start) < 0 or float(end) < float(start):
            raise ValueError(f"word {index} has an invalid time range")
        normalized.append(
            {
                "start": round(float(start), 3),
                "end": round(float(end), 3),
                "word": text.strip(),
            }
        )
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--json", action="store_true", help="emit normalized JSON")
    args = parser.parse_args()

    try:
        document = json.loads(args.transcript.read_text(encoding="utf-8"))
        words = collect_words(document)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        json.dump(words, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        for item in words:
            print(f"{item['start']:8.3f}  {item['end']:8.3f}  {item['word']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
