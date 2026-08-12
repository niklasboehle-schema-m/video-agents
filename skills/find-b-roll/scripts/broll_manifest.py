#!/usr/bin/env python3
"""Validate, summarize, and score an explicit B-roll manifest."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class ManifestError(ValueError):
    """Raised when a B-roll manifest is invalid or unsafe."""


ROUTES = {
    "person",
    "product-ui",
    "receipt",
    "location-action",
    "archival",
    "concept",
    "reaction",
}
STATUSES = {"planned", "candidates", "approved", "skipped"}
RIGHTS_CLEARED = {
    "owned",
    "licensed",
    "permission",
    "public-domain",
}
RIGHTS_REVIEW = {"official-media", "editorial-review", "unknown"}
SCORE_LIMITS = {
    "accuracy": 30.0,
    "authority": 20.0,
    "rights": 20.0,
    "clarity": 15.0,
    "format": 10.0,
    "freshness": 5.0,
}
MINIMUM_BEAT_SECONDS = 0.12


def finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ManifestError(f"{label} must be finite")
    return result


def nonempty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label} must be non-empty text")
    return value.strip()


def load_document(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError(f"manifest not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ManifestError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(document, dict):
        raise ManifestError("manifest root must be an object")
    return document


def candidate_total(candidate: dict[str, Any], label: str) -> float:
    scores = candidate.get("scores")
    if not isinstance(scores, dict):
        raise ManifestError(f"{label}.scores must be an object")
    missing = set(SCORE_LIMITS) - set(scores)
    extra = set(scores) - set(SCORE_LIMITS)
    if missing:
        raise ManifestError(
            f"{label}.scores is missing: {', '.join(sorted(missing))}"
        )
    if extra:
        raise ManifestError(
            f"{label}.scores has unsupported fields: {', '.join(sorted(extra))}"
        )

    total = 0.0
    for key, maximum in SCORE_LIMITS.items():
        value = finite_number(scores[key], f"{label}.scores.{key}")
        if not 0 <= value <= maximum:
            raise ManifestError(
                f"{label}.scores.{key} must be between 0 and {maximum:g}"
            )
        total += value
    return total


def validate_candidate(
    candidate: Any,
    label: str,
    manifest_path: Path,
    *,
    verify_asset: bool,
) -> tuple[str, str, float, Path | None]:
    if not isinstance(candidate, dict):
        raise ManifestError(f"{label} must be an object")

    candidate_id = nonempty_text(candidate.get("id"), f"{label}.id")
    nonempty_text(candidate.get("title"), f"{label}.title")
    url = nonempty_text(candidate.get("url"), f"{label}.url")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ManifestError(f"{label}.url must be an http or https source URL")
    nonempty_text(candidate.get("publisher"), f"{label}.publisher")

    captured_at = nonempty_text(candidate.get("captured_at"), f"{label}.captured_at")
    try:
        date.fromisoformat(captured_at)
    except ValueError as exc:
        raise ManifestError(f"{label}.captured_at must use YYYY-MM-DD") from exc

    rights = candidate.get("rights")
    if not isinstance(rights, dict):
        raise ManifestError(f"{label}.rights must be an object")
    rights_status = nonempty_text(rights.get("status"), f"{label}.rights.status")
    if rights_status not in RIGHTS_CLEARED | RIGHTS_REVIEW:
        allowed = ", ".join(sorted(RIGHTS_CLEARED | RIGHTS_REVIEW))
        raise ManifestError(f"{label}.rights.status must be one of: {allowed}")
    nonempty_text(rights.get("note"), f"{label}.rights.note")

    total = candidate_total(candidate, label)
    local_path: Path | None = None
    raw_path = candidate.get("local_path")
    if raw_path is not None:
        raw_path = nonempty_text(raw_path, f"{label}.local_path")
        local_path = Path(raw_path).expanduser()
        if not local_path.is_absolute():
            local_path = manifest_path.parent / local_path
        local_path = local_path.resolve()
        if verify_asset and not local_path.is_file():
            raise ManifestError(f"{label}.local_path not found: {local_path}")

    return candidate_id, rights_status, total, local_path


def validate_document(
    document: dict[str, Any],
    manifest_path: Path,
    *,
    render_ready: bool = False,
    verify_assets: bool = False,
    allow_unverified_rights: bool = False,
) -> None:
    if document.get("schema") != 1:
        raise ManifestError("schema must be 1")
    nonempty_text(document.get("project"), "project")
    source_duration = finite_number(document.get("source_duration"), "source_duration")
    if source_duration <= 0:
        raise ManifestError("source_duration must be greater than zero")

    target = document.get("target")
    if not isinstance(target, dict):
        raise ManifestError("target must be an object")
    for dimension in ("width", "height"):
        value = finite_number(target.get(dimension), f"target.{dimension}")
        if not value.is_integer() or value < 2:
            raise ManifestError(f"target.{dimension} must be an integer of at least 2")

    beats = document.get("beats")
    if not isinstance(beats, list):
        raise ManifestError("beats must be an array")

    seen_beat_ids: set[str] = set()
    previous_end = 0.0
    approved_count = 0

    for beat_index, beat in enumerate(beats):
        label = f"beats[{beat_index}]"
        if not isinstance(beat, dict):
            raise ManifestError(f"{label} must be an object")

        beat_id = nonempty_text(beat.get("id"), f"{label}.id")
        if beat_id in seen_beat_ids:
            raise ManifestError(f"duplicate beat id: {beat_id}")
        seen_beat_ids.add(beat_id)

        start = finite_number(beat.get("start"), f"{label}.start")
        end = finite_number(beat.get("end"), f"{label}.end")
        if start < 0:
            raise ManifestError(f"{label}.start must be non-negative")
        if end - start < MINIMUM_BEAT_SECONDS:
            raise ManifestError(
                f"{label} must be at least {MINIMUM_BEAT_SECONDS:.2f} seconds"
            )
        if start < previous_end - 1e-6:
            raise ManifestError("beats must be ordered and non-overlapping")
        if end > source_duration + 0.001:
            raise ManifestError(
                f"{label}.end is after the declared source duration"
            )
        previous_end = end

        nonempty_text(beat.get("spoken_text"), f"{label}.spoken_text")
        nonempty_text(beat.get("intent"), f"{label}.intent")
        route = nonempty_text(beat.get("route"), f"{label}.route")
        if route not in ROUTES:
            raise ManifestError(
                f"{label}.route must be one of: {', '.join(sorted(ROUTES))}"
            )

        queries = beat.get("queries")
        if not isinstance(queries, list):
            raise ManifestError(f"{label}.queries must be an array")
        for query_index, query in enumerate(queries):
            nonempty_text(query, f"{label}.queries[{query_index}]")

        status = nonempty_text(beat.get("status"), f"{label}.status")
        if status not in STATUSES:
            raise ManifestError(
                f"{label}.status must be one of: {', '.join(sorted(STATUSES))}"
            )

        candidates = beat.get("candidates")
        if not isinstance(candidates, list):
            raise ManifestError(f"{label}.candidates must be an array")

        candidate_records: dict[str, tuple[str, float, Path | None]] = {}
        for candidate_index, candidate in enumerate(candidates):
            candidate_label = f"{label}.candidates[{candidate_index}]"
            candidate_id, rights_status, total, local_path = validate_candidate(
                candidate,
                candidate_label,
                manifest_path,
                verify_asset=verify_assets,
            )
            if candidate_id in candidate_records:
                raise ManifestError(
                    f"{label} has duplicate candidate id: {candidate_id}"
                )
            candidate_records[candidate_id] = (rights_status, total, local_path)

        selected = beat.get("selected_candidate")
        if selected is not None:
            selected = nonempty_text(selected, f"{label}.selected_candidate")
            if selected not in candidate_records:
                raise ManifestError(
                    f"{label}.selected_candidate does not match a candidate"
                )

        if status == "approved":
            approved_count += 1
            if selected is None:
                raise ManifestError(
                    f"{label}.selected_candidate is required when approved"
                )
            rights_status, _total, local_path = candidate_records[selected]
            if render_ready and local_path is None:
                raise ManifestError(
                    f"{label}'s selected candidate needs local_path for rendering"
                )
            if (
                render_ready
                and rights_status not in RIGHTS_CLEARED
                and not allow_unverified_rights
            ):
                raise ManifestError(
                    f"{label}'s selected candidate has unverified rights: "
                    f"{rights_status}"
                )

    if render_ready and approved_count == 0:
        raise ManifestError("render-ready manifest needs at least one approved beat")


def selected_beats(
    document: dict[str, Any], manifest_path: Path
) -> list[tuple[dict[str, Any], dict[str, Any], Path]]:
    result: list[tuple[dict[str, Any], dict[str, Any], Path]] = []
    for beat in document["beats"]:
        if beat["status"] != "approved":
            continue
        candidate = next(
            item
            for item in beat["candidates"]
            if item["id"] == beat["selected_candidate"]
        )
        raw_path = Path(candidate["local_path"]).expanduser()
        if not raw_path.is_absolute():
            raw_path = manifest_path.parent / raw_path
        result.append((beat, candidate, raw_path.resolve()))
    return result


def print_summary(document: dict[str, Any]) -> None:
    beats = document["beats"]
    status_counts = Counter(beat["status"] for beat in beats)
    route_counts = Counter(beat["route"] for beat in beats)
    coverage = sum(beat["end"] - beat["start"] for beat in beats)
    duration = float(document["source_duration"])

    print(f"Project: {document['project']}")
    print(
        f"{len(beats)} beats cover {coverage:.3f}s of {duration:.3f}s "
        f"({coverage / duration * 100:.1f}%)."
    )
    print(
        "Statuses: "
        + ", ".join(
            f"{status}={status_counts.get(status, 0)}" for status in sorted(STATUSES)
        )
    )
    if route_counts:
        print(
            "Routes: "
            + ", ".join(
                f"{route}={count}" for route, count in sorted(route_counts.items())
            )
        )

    for beat in beats:
        if not beat["candidates"]:
            continue
        ranked = sorted(
            (
                (
                    candidate_total(candidate, f"{beat['id']}.{candidate['id']}"),
                    candidate,
                )
                for candidate in beat["candidates"]
            ),
            reverse=True,
            key=lambda item: item[0],
        )
        best_score, best = ranked[0]
        print(
            f"{beat['id']}: best {best['id']} at {best_score:.0f}/100 "
            f"({best['rights']['status']})"
        )


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate a manifest")
    validate.add_argument("manifest", type=Path)
    validate.add_argument("--render-ready", action="store_true")
    validate.add_argument("--assets", action="store_true")
    validate.add_argument("--allow-unverified-rights", action="store_true")

    summary = commands.add_parser("summary", help="summarize a manifest")
    summary.add_argument("manifest", type=Path)

    score = commands.add_parser("score", help="sum candidate score components")
    for name, maximum in SCORE_LIMITS.items():
        score.add_argument(
            f"--{name}",
            required=True,
            type=float,
            help=f"0-{maximum:g}",
        )

    return parser


def main() -> int:
    args = argument_parser().parse_args()
    try:
        if args.command == "score":
            candidate = {
                "scores": {name: getattr(args, name) for name in SCORE_LIMITS}
            }
            print(f"{candidate_total(candidate, 'candidate'):.0f}/100")
            return 0

        document = load_document(args.manifest)
        validate_document(
            document,
            args.manifest.resolve(),
            render_ready=getattr(args, "render_ready", False),
            verify_assets=getattr(args, "assets", False),
            allow_unverified_rights=getattr(
                args, "allow_unverified_rights", False
            ),
        )
        if args.command == "summary":
            print_summary(document)
        else:
            print(
                f"Valid schema 1 manifest: {len(document['beats'])} beats, "
                f"{document['source_duration']:.3f}s source."
            )
        return 0
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
