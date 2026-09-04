from __future__ import annotations

from hashlib import sha256
import unittest

from llms_txt_snapshots.http import MAX_BODY_BYTES, HttpClient, build_session
from llms_txt_snapshots.models import FetchOutcome

from http_fakes import StubResponse, StubSession


class SessionTests(unittest.TestCase):
    def test_session_does_not_use_netrc_or_environment_proxies(self) -> None:
        session = build_session()
        try:
            self.assertFalse(session.trust_env)
            retry = session.get_adapter("https://").max_retries
            self.assertEqual(2, retry.retry_after_max)
            self.assertNotIn(429, retry.status_forcelist)
        finally:
            session.close()


class BodyLimitTests(unittest.TestCase):
    def test_exact_limit_is_not_marked_truncated(self) -> None:
        url = "https://example.test/data"
        session = StubSession({url: StubResponse(url, chunks=[b"a" * MAX_BODY_BYTES])})
        result = HttpClient(session).fetch(url)
        self.assertEqual(MAX_BODY_BYTES, len(result.body))
        self.assertFalse(result.body_truncated)

    def test_one_byte_over_limit_is_truncated_exactly(self) -> None:
        url = "https://example.test/data"
        session = StubSession(
            {url: StubResponse(url, chunks=[b"a" * MAX_BODY_BYTES, b"b"])}
        )
        result = HttpClient(session).fetch(url)
        self.assertEqual(MAX_BODY_BYTES, len(result.body))
        self.assertTrue(result.body_truncated)

    def test_resource_record_uses_explicit_observation_metadata(self) -> None:
        url = "https://example.test/data"
        session = StubSession({url: StubResponse(url, body=b"observed")})
        result = HttpClient(session).fetch(url)
        observed_digest = sha256(b"observed").hexdigest()
        self.assertEqual(
            observed_digest,
            result.to_record()["observed_body_sha256"],
        )
        record = result.to_record()
        self.assertEqual(8, record["observed_body_bytes"])
        self.assertEqual(0, record["redirect_count"])
        self.assertEqual([], record["redirect_chain"])


class RedirectTests(unittest.TestCase):
    def test_checks_policy_before_each_redirect_hop(self) -> None:
        start = "https://one.test/start"
        destination = "https://two.test/final"
        session = StubSession(
            {
                start: StubResponse(start, 302, headers={"Location": destination}),
                destination: StubResponse(destination, body=b"not fetched"),
            }
        )
        checked: list[str] = []

        def can_fetch(url: str) -> bool:
            checked.append(url)
            return url != destination

        result = HttpClient(session).fetch(start, can_fetch)
        self.assertEqual(FetchOutcome.BLOCKED_BY_ROBOTS, result.outcome)
        self.assertEqual([start, destination], checked)
        self.assertEqual([start], session.calls)
        self.assertEqual(
            (
                {
                    "from_url": start,
                    "http_status": 302,
                    "to_url": destination,
                },
            ),
            result.redirect_chain,
        )

    def test_follows_five_redirects_and_rejects_the_sixth(self) -> None:
        urls = [f"https://example.test/{index}" for index in range(7)]
        responses = {
            url: StubResponse(url, 302, headers={"Location": urls[index + 1]})
            for index, url in enumerate(urls[:-1])
        }
        responses[urls[-1]] = StubResponse(urls[-1], body=b"final")
        result = HttpClient(StubSession(responses)).fetch(urls[0])
        self.assertEqual(FetchOutcome.REDIRECT_ERROR, result.outcome)
        self.assertEqual(5, result.to_record()["redirect_count"])
        self.assertIn("redirect limit", result.error or "")

    def test_follows_exactly_five_redirects(self) -> None:
        urls = [f"https://example.test/{index}" for index in range(6)]
        responses = {
            url: StubResponse(url, 302, headers={"Location": urls[index + 1]})
            for index, url in enumerate(urls[:-1])
        }
        responses[urls[-1]] = StubResponse(urls[-1], body=b"final")
        result = HttpClient(StubSession(responses)).fetch(urls[0])
        self.assertEqual(FetchOutcome.RESPONSE, result.outcome)
        self.assertEqual(5, result.to_record()["redirect_count"])
        self.assertEqual(b"final", result.body)

    def test_strips_fragment_from_redirect_target(self) -> None:
        start = "https://example.test/start"
        destination = "https://example.test/final"
        session = StubSession(
            {
                start: StubResponse(
                    start,
                    302,
                    headers={"Location": f"{destination}#section"},
                ),
                destination: StubResponse(destination, body=b"final"),
            }
        )
        result = HttpClient(session).fetch(start)
        self.assertEqual(FetchOutcome.RESPONSE, result.outcome)
        self.assertEqual([start, destination], session.calls)

    def test_rejects_https_to_http_downgrade(self) -> None:
        url = "https://example.test/start"
        session = StubSession(
            {url: StubResponse(url, 302, headers={"Location": "http://example.test/"})}
        )
        result = HttpClient(session).fetch(url)
        self.assertEqual(FetchOutcome.REDIRECT_ERROR, result.outcome)
        self.assertIn("absolute HTTPS", result.error or "")


if __name__ == "__main__":
    unittest.main()
