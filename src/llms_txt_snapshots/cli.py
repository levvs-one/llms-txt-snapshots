from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence
from urllib.parse import urlsplit, urlunsplit

from .collector import Target, collect_targets
from .models import ObservationRecord


TARGET_FIELDS = ("category", "url", "rationale")
SUMMARY_FIELDS = (
    "category",
    "target_url",
    "landing_outcome",
    "landing_http_status",
    "discovery_outcome",
    "llms_txt_http_status",
    "llms_txt_outcome",
    "describedby_links",
    "markdown_alternates",
    "content_signal",
    "x_robots_tag",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="llms-txt-snapshots",
        description="Collect a robots-aware snapshot of public llms.txt signals.",
    )
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    return parser.parse_args(argv)


def load_targets(path: Path) -> list[Target]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != TARGET_FIELDS:
            raise ValueError(
                f"targets must contain exactly these columns: {TARGET_FIELDS}"
            )
        rows = list(reader)
    if not rows:
        raise ValueError("targets file must contain at least one row")

    targets = []
    canonical_urls: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        category_value = row.get("category")
        url_value = row.get("url")
        rationale_value = row.get("rationale")
        if (
            set(row) != set(TARGET_FIELDS)
            or not isinstance(category_value, str)
            or not isinstance(url_value, str)
            or not isinstance(rationale_value, str)
        ):
            raise ValueError(
                f"targets row {line_number} must contain exactly three fields"
            )
        category = category_value.strip()
        url = url_value.strip()
        rationale = rationale_value.strip()
        if not category or not url or not rationale:
            raise ValueError(f"targets row {line_number} contains an empty field")
        canonical_url = _canonical_target_url(url)
        if canonical_url in canonical_urls:
            raise ValueError(f"targets row {line_number} duplicates URL {url}")
        canonical_urls.add(canonical_url)
        targets.append(Target(category=category, url=url, rationale=rationale))
    return targets


def write_snapshot(
    output_dir: Path,
    records: list[ObservationRecord],
) -> tuple[Path, Path]:
    destination = output_dir.resolve(strict=False)
    if destination.exists():
        raise FileExistsError(f"output directory already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}.tmp-",
        dir=destination.parent,
    ) as staging_name:
        staging = Path(staging_name)
        observations = staging / "observations.jsonl"
        summary = staging / "summary.csv"
        _write_jsonl(observations, records)
        _write_summary(summary, records)
        if destination.exists():
            raise FileExistsError(f"output directory already exists: {destination}")
        staging.rename(destination)

    return destination / "observations.jsonl", destination / "summary.csv"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        targets = load_targets(args.targets)
        records = collect_targets(targets, workers=args.workers)
        observations, summary = write_snapshot(args.output_dir, records)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {len(records)} observations to {observations}")
    print(f"wrote summary to {summary}")
    return 0


def _canonical_target_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"target URL is malformed: {url}") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError(f"target must be an absolute HTTPS URL: {url}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"target must not contain credentials: {url}")
    if parsed.fragment:
        raise ValueError(f"target must not contain a fragment: {url}")
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    host_literal = f"[{host}]" if ":" in host else host
    netloc = host_literal if port in (None, 443) else f"{host_literal}:{port}"
    path = parsed.path or "/"
    return urlunsplit(("https", netloc, path, parsed.query, ""))


def _write_jsonl(path: Path, records: list[ObservationRecord]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _write_summary(path: Path, records: list[ObservationRecord]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        for record in records:
            resources = record["resources"]
            links = record["discovery_links"]
            landing = resources["landing"]
            llms_txt = resources["llms_txt"]
            writer.writerow(
                {
                    "category": record["category"],
                    "target_url": record["target_url"],
                    "landing_outcome": landing["outcome"],
                    "landing_http_status": landing["http_status"],
                    "discovery_outcome": record["discovery_outcome"],
                    "llms_txt_http_status": llms_txt["http_status"],
                    "llms_txt_outcome": record["llms_txt_outcome"],
                    "describedby_links": sum(
                        link["relation"] == "describedby" for link in links
                    ),
                    "markdown_alternates": sum(
                        link["relation"] == "alternate"
                        and link["media_type"] == "text/markdown"
                        for link in links
                    ),
                    "content_signal": landing["content_signal"],
                    "x_robots_tag": landing["x_robots_tag"],
                }
            )
