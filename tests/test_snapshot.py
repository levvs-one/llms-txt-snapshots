from __future__ import annotations

import csv
import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from llms_txt_snapshots.cli import _write_summary, load_targets
from llms_txt_snapshots.robots import authority_for


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "snapshots" / "2026-09-04-v0.2"


class ReleasedSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = [
            json.loads(line)
            for line in (SNAPSHOT / "observations.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]

    def test_targets_jsonl_and_csv_cover_the_same_origins(self) -> None:
        target_urls = {target.url for target in load_targets(ROOT / "targets.csv")}
        record_urls = [record["target_url"] for record in self.records]
        with (SNAPSHOT / "summary.csv").open(encoding="utf-8", newline="") as handle:
            summary_urls = {row["target_url"] for row in csv.DictReader(handle)}

        self.assertEqual(30, len(record_urls))
        self.assertEqual(sorted(record_urls), record_urls)
        self.assertEqual(30, len(set(record_urls)))
        self.assertEqual(target_urls, set(record_urls))
        self.assertEqual(target_urls, summary_urls)

    def test_summary_is_the_exact_projection_of_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "summary.csv"
            _write_summary(generated, self.records)
            self.assertEqual(
                generated.read_text(encoding="utf-8"),
                (SNAPSHOT / "summary.csv").read_text(encoding="utf-8"),
            )

    def test_reported_outcomes_match_the_records(self) -> None:
        self.assertEqual(
            Counter({"not_found": 21, "plausible": 7, "forbidden": 2}),
            Counter(record["llms_txt_outcome"] for record in self.records),
        )
        self.assertEqual(
            Counter({"complete": 27, "unavailable": 3}),
            Counter(record["discovery_outcome"] for record in self.records),
        )
        relations = Counter(
            link["relation"]
            for record in self.records
            for link in record["discovery_links"]
        )
        self.assertEqual(Counter({"alternate": 2}), relations)

    def test_every_redirect_authority_has_a_robots_policy(self) -> None:
        for record in self.records:
            authorities = {
                policy["authority"] for policy in record["robots_policies"]
            }
            for resource in record["resources"].values():
                for hop in resource["redirect_chain"]:
                    self.assertIn(authority_for(hop["to_url"]), authorities)

    def test_records_use_only_the_v02_contract(self) -> None:
        for record in self.records:
            self.assertEqual("0.2", record["schema_version"])
            self.assertEqual("0.2.0", record["collector_version"])
            self.assertTrue(record["collected_at"].startswith("2026-09-04T"))
            self.assertNotIn("llms_root_plausible", record)
            for resource in record["resources"].values():
                self.assertNotIn("link_header", resource)


if __name__ == "__main__":
    unittest.main()
