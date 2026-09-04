from __future__ import annotations

import unittest

import requests

from llms_txt_snapshots.http import HttpClient
from llms_txt_snapshots.robots import AGENT_TOKENS, RobotsCache, authority_for

from http_fakes import StubResponse, StubSession


class RobotsPolicyTests(unittest.TestCase):
    def test_uses_collector_product_token_not_full_user_agent(self) -> None:
        robots_url = "https://example.test/robots.txt"
        body = b"User-agent: github\nDisallow: /\n\nUser-agent: *\nAllow: /\n"
        cache = RobotsCache(
            HttpClient(StubSession({robots_url: StubResponse(robots_url, body=body)}))
        )
        self.assertTrue(cache.can_fetch("https://example.test/page"))
        records = cache.to_records()
        self.assertEqual(set(AGENT_TOKENS), set(records[0]["checks"][0]["agents"]))

    def test_caches_one_policy_per_authority(self) -> None:
        robots_url = "https://example.test/robots.txt"
        session = StubSession({robots_url: StubResponse(robots_url, body=b"")})
        cache = RobotsCache(HttpClient(session))
        self.assertTrue(cache.can_fetch("https://example.test/one"))
        self.assertTrue(cache.can_fetch("https://example.test/two"))
        self.assertEqual([robots_url], session.calls)

    def test_4xx_means_unavailable_and_allows_access(self) -> None:
        robots_url = "https://example.test/robots.txt"
        cache = RobotsCache(
            HttpClient(StubSession({robots_url: StubResponse(robots_url, status=404)}))
        )
        self.assertTrue(cache.can_fetch("https://example.test/page"))
        record = cache.to_records()[0]
        self.assertEqual("unavailable", record["state"])
        self.assertIn("HTTP 404", record["reason"])

    def test_5xx_means_unreachable_and_denies_access(self) -> None:
        robots_url = "https://example.test/robots.txt"
        cache = RobotsCache(
            HttpClient(StubSession({robots_url: StubResponse(robots_url, status=503)}))
        )
        self.assertFalse(cache.can_fetch("https://example.test/page"))
        record = cache.to_records()[0]
        self.assertEqual("unreachable", record["state"])
        self.assertIn("access denied", record["reason"])

    def test_network_error_means_unreachable_and_denies_access(self) -> None:
        robots_url = "https://example.test/robots.txt"
        cache = RobotsCache(
            HttpClient(StubSession({robots_url: requests.Timeout("timed out")}))
        )
        self.assertFalse(cache.can_fetch("https://example.test/page"))
        record = cache.to_records()[0]
        self.assertEqual("unreachable", record["state"])
        self.assertEqual("request_error", record["resource"]["outcome"])
        self.assertIn("request_error", record["reason"])

    def test_preserves_ipv6_brackets_in_authority(self) -> None:
        self.assertEqual("https://[::1]:8443", authority_for("https://[::1]:8443/path"))


if __name__ == "__main__":
    unittest.main()
