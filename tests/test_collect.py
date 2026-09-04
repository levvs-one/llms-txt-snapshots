from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from collect import extract_discovery_links, plausible_llms, robots_decisions


class DiscoveryLinkTests(unittest.TestCase):
    def test_extracts_html_and_http_discovery_links(self) -> None:
        html = """
        <html><head>
          <link rel="describedby" href="/docs/llms.txt" type="text/plain">
          <link rel="alternate" href="/guide.md" type="text/markdown">
          <link rel="stylesheet" href="/style.css">
        </head></html>
        """
        links = extract_discovery_links(
            "https://example.test/start",
            html,
            '<https://example.test/api.md>; rel="alternate"; type="text/markdown"',
        )
        self.assertEqual(3, len(links))
        self.assertEqual(
            {
                "https://example.test/api.md",
                "https://example.test/docs/llms.txt",
                "https://example.test/guide.md",
            },
            {link["url"] for link in links},
        )


class LlmsClassificationTests(unittest.TestCase):
    def test_accepts_plausible_markdown(self) -> None:
        body = b"# Example\n\n- [Documentation](https://example.test/docs)"
        plausible, reason = plausible_llms(
            {"status": 200, "content_type": "text/markdown", "sha256": "one"},
            body,
            {"status": 404, "content_type": "text/html", "sha256": "two"},
            b"not found",
        )
        self.assertTrue(plausible)
        self.assertIn("plausible", reason)

    def test_rejects_soft_404_body(self) -> None:
        body = b"This generic response is long enough to pass the size check."
        plausible, reason = plausible_llms(
            {"status": 200, "content_type": "text/plain", "sha256": "same"},
            body,
            {"status": 200, "content_type": "text/plain", "sha256": "same"},
            body,
        )
        self.assertFalse(plausible)
        self.assertIn("soft-404", reason)


class RobotsTests(unittest.TestCase):
    def test_reports_named_agent_policy(self) -> None:
        body = b"User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
        decisions = robots_decisions(body, "https://example.test/")
        self.assertIsNotNone(decisions)
        self.assertFalse(decisions["GPTBot"])
        self.assertTrue(decisions["ClaudeBot"])


if __name__ == "__main__":
    unittest.main()
