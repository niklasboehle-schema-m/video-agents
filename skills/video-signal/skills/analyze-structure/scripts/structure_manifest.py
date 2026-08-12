#!/usr/bin/env python3
"""Validate, summarize, and originality-check a structure-transfer manifest."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class StructureError(ValueError):
    """Raised when a structure manifest is invalid or unsafe."""


FUNCTIONS = {
    "pattern-break",
    "promise",
    "context",
    "problem",
    "proof",
    "mechanism",
    "contrast",
    "open-loop",
    "step",
    "reveal",
    "application",
    "recap",
    "bridge",
    "cta",
}
RETENTION_DRIVERS = {
    "question-pressure",
    "value-ladder",
    "stakes-rise",
    "proof-chain",
    "pace-renewal",
}
TRANSCRIPT_CONFIDENCE = {"verified", "approximate", "partial"}
REWRITE_STATUSES = {"pending", "draft", "approved", "skipped"}
MINIMUM_BEAT_SECONDS = 0.08
DEFAULT_MAX_SHARED_PHRASE = 5
DEFAULT_LINE_SIMILARITY = 0.72


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StructureError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise StructureError(f"{label} must be finite")
    return result


def nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StructureError(f"{label} must be non-empty text")
    return value.strip()


def load_document(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise StructureError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise StructureError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(document, dict):
        raise StructureError("manifest root must be an object")
    return document


def word_tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)?", text.casefold(), flags=re.UNICODE)


def longest_shared_phrase(left: list[str], right: list[str]) -> list[str]:
    if not left or not right:
        return []
    previous = [0] * (len(right) + 1)
    best_length = 0
    best_end = 0
    for left_index, left_token in enumerate(left, start=1):
        current = [0] * (len(right) + 1)
        for right_index, right_token in enumerate(right, start=1):
            if left_token == right_token:
                current[right_index] = previous[right_index - 1] + 1
                if current[right_index] > best_length:
                    best_length = current[right_index]
                    best_end = left_index
        previous = current
    return left[best_end - best_length : best_end]


def rewrite_lines(document: dict[str, Any]) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    for beat in document["beats"]:
        rewrite = beat.get("rewrite")
        if not isinstance(rewrite, dict):
            continue
        line = rewrite.get("line")
        if isinstance(line, str) and line.strip():
            lines.append((beat["id"], line.strip()))
    return lines


def approved_rewrites(
    document: dict[str, Any], *, include_drafts: bool = False
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    allowed = {"approved"}
    if include_drafts:
        allowed.add("draft")
    result: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for beat in document["beats"]:
        rewrite = beat.get("rewrite")
        if isinstance(rewrite, dict) and rewrite.get("status") in allowed:
            line = rewrite.get("line")
            if isinstance(line, str) and line.strip():
                result.append((beat, rewrite))
    return result


def validate_source(source: Any) -> float:
    if not isinstance(source, dict):
        raise StructureError("source must be an object")
    nonempty_text(source.get("title"), "source.title")
    duration = finite_number(source.get("duration"), "source.duration")
    if duration <= 0:
        raise StructureError("source.duration must be greater than zero")
    confidence = nonempty_text(
        source.get("transcript_confidence"), "source.transcript_confidence"
    )
    if confidence not in TRANSCRIPT_CONFIDENCE:
        allowed = ", ".join(sorted(TRANSCRIPT_CONFIDENCE))
        raise StructureError(
            f"source.transcript_confidence must be one of: {allowed}"
        )

    url = source.get("url")
    provenance = source.get("provenance")
    if url is None and provenance is None:
        raise StructureError("source needs url or provenance")
    if url is not None:
        url = nonempty_text(url, "source.url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise StructureError("source.url must be an http or https URL")
    if provenance is not None:
        nonempty_text(provenance, "source.provenance")
    return duration


def validate_strategy(strategy: Any) -> None:
    if not isinstance(strategy, dict):
        raise StructureError("strategy must be an object")
    for field in ("audience", "opening_contract", "payoff"):
        nonempty_text(strategy.get(field), f"strategy.{field}")
    drivers = strategy.get("retention_drivers")
    if not isinstance(drivers, list) or not drivers:
        raise StructureError("strategy.retention_drivers must be a non-empty array")
    seen: set[str] = set()
    for index, driver in enumerate(drivers):
        driver = nonempty_text(driver, f"strategy.retention_drivers[{index}]")
        if driver not in RETENTION_DRIVERS:
            allowed = ", ".join(sorted(RETENTION_DRIVERS))
            raise StructureError(
                f"strategy.retention_drivers[{index}] must be one of: {allowed}"
            )
        if driver in seen:
            raise StructureError(f"duplicate retention driver: {driver}")
        seen.add(driver)
    notes = strategy.get("notes")
    if notes is not None and not isinstance(notes, str):
        raise StructureError("strategy.notes must be text")


def validate_rewrite(
    rewrite: Any,
    label: str,
    *,
    require_rewrite: bool,
) -> None:
    if rewrite is None:
        if require_rewrite:
            raise StructureError(f"{label}.rewrite is required")
        return
    if not isinstance(rewrite, dict):
        raise StructureError(f"{label}.rewrite must be an object")
    status = nonempty_text(rewrite.get("status"), f"{label}.rewrite.status")
    if status not in REWRITE_STATUSES:
        allowed = ", ".join(sorted(REWRITE_STATUSES))
        raise StructureError(f"{label}.rewrite.status must be one of: {allowed}")
    nonempty_text(rewrite.get("objective"), f"{label}.rewrite.objective")

    line = rewrite.get("line", "")
    if not isinstance(line, str):
        raise StructureError(f"{label}.rewrite.line must be text")
    if status in {"draft", "approved"} and not line.strip():
        raise StructureError(
            f"{label}.rewrite.line is required when status is {status}"
        )
    if require_rewrite and status == "pending":
        raise StructureError(
            f"{label}.rewrite cannot remain pending when rewrite is required"
        )

    target_duration = finite_number(
        rewrite.get("target_duration"), f"{label}.rewrite.target_duration"
    )
    if target_duration <= 0:
        raise StructureError(
            f"{label}.rewrite.target_duration must be greater than zero"
        )


def validate_document(
    document: dict[str, Any],
    *,
    require_rewrite: bool = False,
) -> None:
    if document.get("schema") != 1:
        raise StructureError("schema must be 1")
    nonempty_text(document.get("project"), "project")
    source_duration = validate_source(document.get("source"))
    validate_strategy(document.get("strategy"))

    beats = document.get("beats")
    if not isinstance(beats, list) or not beats:
        raise StructureError("beats must be a non-empty array")

    seen_ids: set[str] = set()
    previous_end = 0.0
    for index, beat in enumerate(beats):
        label = f"beats[{index}]"
        if not isinstance(beat, dict):
            raise StructureError(f"{label} must be an object")
        beat_id = nonempty_text(beat.get("id"), f"{label}.id")
        if beat_id in seen_ids:
            raise StructureError(f"duplicate beat id: {beat_id}")
        seen_ids.add(beat_id)

        start = finite_number(beat.get("start"), f"{label}.start")
        end = finite_number(beat.get("end"), f"{label}.end")
        if start < 0:
            raise StructureError(f"{label}.start must be non-negative")
        if end - start < MINIMUM_BEAT_SECONDS:
            raise StructureError(
                f"{label} must be at least {MINIMUM_BEAT_SECONDS:.2f} seconds"
            )
        if start < previous_end - 1e-6:
            raise StructureError("beats must be ordered and non-overlapping")
        if end > source_duration + 0.001:
            raise StructureError(f"{label}.end is after source.duration")
        previous_end = end

        nonempty_text(beat.get("source_text"), f"{label}.source_text")
        function = nonempty_text(beat.get("function"), f"{label}.function")
        if function not in FUNCTIONS:
            allowed = ", ".join(sorted(FUNCTIONS))
            raise StructureError(f"{label}.function must be one of: {allowed}")
        for field in (
            "job",
            "audience_before",
            "audience_after",
            "information_gain",
            "handoff",
        ):
            nonempty_text(beat.get(field), f"{label}.{field}")
        validate_rewrite(
            beat.get("rewrite"), label, require_rewrite=require_rewrite
        )


def originality_issues(
    document: dict[str, Any],
    *,
    max_shared_phrase: int = DEFAULT_MAX_SHARED_PHRASE,
    line_similarity: float = DEFAULT_LINE_SIMILARITY,
) -> list[str]:
    source_beats = [
        (beat["id"], word_tokens(beat["source_text"])) for beat in document["beats"]
    ]
    source_all = [
        token for _beat_id, tokens in source_beats for token in tokens
    ]
    issues: list[str] = []

    for rewrite_id, line in rewrite_lines(document):
        rewritten = word_tokens(line)
        if not rewritten:
            continue
        phrase = longest_shared_phrase(rewritten, source_all)
        if len(phrase) > max_shared_phrase:
            issues.append(
                f"{rewrite_id}: shares {len(phrase)} consecutive words with the "
                f"reference: “{' '.join(phrase)}”"
            )

        closest_ratio = 0.0
        closest_id = ""
        for source_id, source_tokens in source_beats:
            if min(len(source_tokens), len(rewritten)) < 7:
                continue
            ratio = SequenceMatcher(
                None, source_tokens, rewritten, autojunk=False
            ).ratio()
            if ratio > closest_ratio:
                closest_ratio = ratio
                closest_id = source_id
        if closest_ratio >= line_similarity:
            issues.append(
                f"{rewrite_id}: {closest_ratio:.0%} token-sequence similarity "
                f"to {closest_id}; rewrite the sentence construction"
            )

    return issues


def words_per_second(text: str, duration: float) -> float:
    return len(word_tokens(text)) / duration if duration > 0 else 0.0


def print_summary(document: dict[str, Any]) -> None:
    beats = document["beats"]
    source_duration = float(document["source"]["duration"])
    mapped_duration = sum(float(beat["end"]) - float(beat["start"]) for beat in beats)
    source_words = sum(len(word_tokens(beat["source_text"])) for beat in beats)
    function_counts = Counter(beat["function"] for beat in beats)
    rewrites = approved_rewrites(document, include_drafts=True)
    rewrite_words = sum(len(word_tokens(rewrite["line"])) for _beat, rewrite in rewrites)
    target_duration = sum(float(rewrite["target_duration"]) for _beat, rewrite in rewrites)

    print(f"Project: {document['project']}")
    print(
        f"{len(beats)} beats map {mapped_duration:.3f}s of "
        f"{source_duration:.3f}s ({mapped_duration / source_duration * 100:.1f}%)."
    )
    print(
        f"Reference: {source_words} words, "
        f"{source_words / mapped_duration:.2f} words/second across mapped beats."
    )
    print(
        "Functions: "
        + ", ".join(
            f"{function}={count}"
            for function, count in sorted(function_counts.items())
        )
    )
    print(
        "Retention drivers: "
        + ", ".join(document["strategy"]["retention_drivers"])
    )
    if rewrites:
        print(
            f"Rewrite: {len(rewrites)} drafted/approved beats, {rewrite_words} words, "
            f"{target_duration:.3f}s target "
            f"({rewrite_words / target_duration:.2f} words/second)."
        )

    for beat in beats:
        duration = float(beat["end"]) - float(beat["start"])
        source_pace = words_per_second(beat["source_text"], duration)
        rewrite = beat.get("rewrite")
        detail = ""
        if isinstance(rewrite, dict) and rewrite.get("line"):
            target = float(rewrite["target_duration"])
            rewrite_pace = words_per_second(rewrite["line"], target)
            detail = f" -> rewrite {rewrite_pace:.2f} w/s"
        print(
            f"{beat['id']} {beat['function']} {duration:.2f}s: "
            f"source {source_pace:.2f} w/s{detail}"
        )


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate a manifest")
    validate.add_argument("manifest", type=Path)
    validate.add_argument("--require-rewrite", action="store_true")
    validate.add_argument("--originality", action="store_true")

    summary = commands.add_parser("summary", help="summarize structure and pacing")
    summary.add_argument("manifest", type=Path)

    originality = commands.add_parser(
        "originality", help="check transferred lines against the reference"
    )
    originality.add_argument("manifest", type=Path)
    originality.add_argument(
        "--max-shared-phrase",
        type=int,
        default=DEFAULT_MAX_SHARED_PHRASE,
        help="maximum allowed consecutive shared words; default 5",
    )
    originality.add_argument(
        "--line-similarity",
        type=float,
        default=DEFAULT_LINE_SIMILARITY,
        help="maximum line token-sequence similarity; default 0.72",
    )
    return parser


def main() -> int:
    args = argument_parser().parse_args()
    try:
        document = load_document(args.manifest)
        validate_document(
            document,
            require_rewrite=getattr(args, "require_rewrite", False),
        )
        if args.command == "summary":
            print_summary(document)
            return 0

        if args.command == "originality" or getattr(args, "originality", False):
            issues = originality_issues(
                document,
                max_shared_phrase=getattr(
                    args, "max_shared_phrase", DEFAULT_MAX_SHARED_PHRASE
                ),
                line_similarity=getattr(
                    args, "line_similarity", DEFAULT_LINE_SIMILARITY
                ),
            )
            if issues:
                for issue in issues:
                    print(f"error: {issue}", file=sys.stderr)
                return 2
            print(
                f"Originality check passed for {len(rewrite_lines(document))} "
                "rewrite lines."
            )
            return 0

        print(
            f"Valid schema 1 manifest: {len(document['beats'])} beats, "
            f"{document['source']['duration']:.3f}s source."
        )
        return 0
    except StructureError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
