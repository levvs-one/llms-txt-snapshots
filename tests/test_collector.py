from __future__ import annotations

import unittest

from llms_txt_snapshots.collector import Target, collect_target
from llms_txt_snapshots.http import MAX_BODY_BYTES

from http_fakes import StubResponse, StubSession


class CollectorIntegrationTests(unittest.TestCase):
    def test_cross_authority_redirect_obeys_destination_robots(self) -> None:
        source = "https://source.test/"
        destination = "https://destination.test/home"
        missing_path = (
            "https://source.test/.well-known/llms-txt-snapshots-missing-7f3a9d2c"
        )
        session = StubSession(
            {
                "https://source.test/robots.txt": StubResponse(
                    "https://source.test/robots.txt",
                    body=b"User-agent: *\nAllow: /\n",
                ),
                source: StubResponse(source, 302, headers={"Location": destination}),
                "https://destination.test/robots.txt": StubResponse(
                    "https://destination.test/robots.txt",
                    body=b"User-agent: llms-txt-snapshots\nDisallow: /home\n",
                ),
                "https://source.test/llms.txt": StubResponse(
                    "https://source.test/llms.txt", status=404
                ),
                missing_path: StubResponse(missing_path, status=404),
            }
        )
        record = collect_target(
            Target("test", source, "integration test"),
            session=session,
        )
        landing = record["resources"]["landing"]
        self.assertEqual("blocked_by_robots", landing["outcome"])
        self.assertNotIn(destination, session.calls)
        self.assertEqual(
            ["https://destination.test", "https://source.test"],
            [policy["authority"] for policy in record["robots_policies"]],
        )
        self.assertNotIn("llms_root_plausible", record)
        self.assertEqual("not_found", record["llms_txt_outcome"])
        self.assertTrue(session.closed)

    def test_extracts_discovery_only_from_successful_landing(self) -> None:
        target = "https://example.test/"
        missing_path = (
            "https://example.test/.well-known/llms-txt-snapshots-missing-7f3a9d2c"
        )
        session = StubSession(
            {
                "https://example.test/robots.txt": StubResponse(
                    "https://example.test/robots.txt", status=404
                ),
                target: StubResponse(
                    target,
                    status=403,
                    body=b'<link rel="alternate" href="/page.md" type="text/markdown">',
                    headers={"Content-Type": "text/html"},
                ),
                "https://example.test/llms.txt": StubResponse(
                    "https://example.test/llms.txt", status=404
                ),
                missing_path: StubResponse(missing_path, status=404),
            }
        )
        record = collect_target(Target("test", target, "test"), session=session)
        self.assertEqual([], record["discovery_links"])
        self.assertEqual("unavailable", record["discovery_outcome"])

    def test_marks_truncated_html_without_a_closed_head_as_partial(self) -> None:
        target = "https://example.test/"
        missing_path = (
            "https://example.test/.well-known/llms-txt-snapshots-missing-7f3a9d2c"
        )
        session = StubSession(
            {
                "https://example.test/robots.txt": StubResponse(
                    "https://example.test/robots.txt", status=404
                ),
                target: StubResponse(
                    target,
                    chunks=[b"<html><head>" + b" " * MAX_BODY_BYTES],
                    headers={
                        "Content-Type": "text/html",
                        "Link": '</llms.txt>; rel="describedby"',
                    },
                ),
                "https://example.test/llms.txt": StubResponse(
                    "https://example.test/llms.txt", status=404
                ),
                missing_path: StubResponse(missing_path, status=404),
            }
        )
        record = collect_target(Target("test", target, "test"), session=session)
        self.assertEqual("partial", record["discovery_outcome"])
        self.assertEqual("describedby", record["discovery_links"][0]["relation"])
        self.assertIsNotNone(
            record["resources"]["landing"]["link_header_sha256"]
        )
        self.assertNotIn("link_header", record["resources"]["landing"])


if __name__ == "__main__":
    unittest.main()
