from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llms_txt_snapshots.cli import load_targets, write_snapshot
from llms_txt_snapshots.models import ObservationRecord, ResourceRecord


def record() -> ObservationRecord:
    resource: ResourceRecord = {
        "outcome": "response",
        "requested_url": "https://example.test/",
        "final_url": "https://example.test/",
        "http_status": 200,
        "content_type": "text/html",
        "observed_body_bytes": 0,
        "body_truncated": False,
        "observed_body_sha256": None,
        "elapsed_ms": 1,
        "redirect_count": 0,
        "redirect_chain": [],
        "content_signal": None,
        "x_robots_tag": None,
        "link_header_sha256": None,
        "error": None,
    }
    return {
        "schema_version": "0.2",
        "collector_version": "0.2.0",
        "collected_at": "2026-09-04T00:00:00+00:00",
        "category": "test",
        "target_url": "https://example.test/",
        "rationale": "test fixture",
        "llms_txt_outcome": "plausible",
        "llms_txt_reason": "plausible textual llms.txt observed",
        "discovery_outcome": "complete",
        "discovery_links": [
            {
                "url": "https://example.test/page.md",
                "relation": "alternate",
                "media_type": "text/markdown",
                "source": "html",
            }
        ],
        "robots_policies": [],
        "resources": {
            "landing": resource,
            "llms_txt": resource,
            "missing_path_probe": resource,
        },
    }


class TargetFileTests(unittest.TestCase):
    def test_rejects_duplicate_canonical_urls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "targets.csv"
            path.write_text(
                "category,url,rationale\n"
                "one,https://EXAMPLE.test,first\n"
                "two,https://example.test/,second\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicates URL"):
                load_targets(path)

    def test_rejects_credentials_and_fragments(self) -> None:
        cases = (
            "https://user:secret@example.test/",
            "https://example.test/#section",
        )
        for url in cases:
            with self.subTest(url=url), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "targets.csv"
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(("category", "url", "rationale"))
                    writer.writerow(("test", url, "test"))
                with self.assertRaises(ValueError):
                    load_targets(path)

    def test_rejects_rows_with_the_wrong_number_of_fields(self) -> None:
        rows = (
            "test,https://example.test/\n",
            "test,https://example.test/,test,unexpected\n",
        )
        for row in rows:
            with self.subTest(row=row), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "targets.csv"
                path.write_text(
                    "category,url,rationale\n" + row,
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(ValueError, "exactly three fields"):
                    load_targets(path)


class SnapshotWriterTests(unittest.TestCase):
    def test_writes_complete_directory_and_refuses_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "snapshot"
            observations, summary = write_snapshot(output, [record()])
            parsed = json.loads(observations.read_text(encoding="utf-8"))
            self.assertEqual("0.2", parsed["schema_version"])
            self.assertIn("markdown_alternates", summary.read_text(encoding="utf-8"))
            with self.assertRaises(FileExistsError):
                write_snapshot(output, [record()])

    def test_failed_write_leaves_no_output_or_staging_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            output = parent / "snapshot"
            with patch(
                "llms_txt_snapshots.cli._write_summary",
                side_effect=OSError("disk full"),
            ), self.assertRaisesRegex(OSError, "disk full"):
                write_snapshot(output, [record()])
            self.assertFalse(output.exists())
            self.assertEqual([], list(parent.iterdir()))


if __name__ == "__main__":
    unittest.main()
