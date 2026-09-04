from __future__ import annotations

import unittest

from llms_txt_snapshots.models import FetchOutcome, FetchResult
from llms_txt_snapshots.signals import (
    LlmsTxtOutcome,
    classify_llms_txt,
    extract_discovery,
)


def response(
    body: bytes,
    *,
    status: int = 200,
    content_type: str = "text/plain",
    outcome: FetchOutcome = FetchOutcome.RESPONSE,
) -> FetchResult:
    return FetchResult(
        outcome=outcome,
        requested_url="https://example.test/llms.txt",
        final_url="https://example.test/llms.txt",
        http_status=status,
        content_type=content_type,
        body=body,
        body_truncated=False,
        elapsed_ms=1,
        redirect_chain=("https://example.test/llms.txt",),
    )


class DiscoveryLinkTests(unittest.TestCase):
    def test_preserves_source_and_honors_html_base(self) -> None:
        html = """
        <base href="/docs/">
        <link rel="alternate" href="guide.md" type="text/markdown">
        <link rel="describedby" href="llms.txt">
        """
        result = extract_discovery("https://example.test/start", html, None)
        links = result.links
        self.assertEqual({"html"}, {link["source"] for link in links})
        self.assertFalse(result.html_head_complete)
        self.assertEqual(
            {
                "https://example.test/docs/guide.md",
                "https://example.test/docs/llms.txt",
            },
            {link["url"] for link in links},
        )

    def test_http_parameter_names_and_values_are_case_insensitive(self) -> None:
        links = extract_discovery(
            "https://example.test/",
            None,
            '<https://example.test/a.md>; Rel=Alternate; Type=Text/Markdown',
        ).links
        self.assertEqual(1, len(links))
        self.assertEqual("http_header", links[0]["source"])

    def test_rejects_link_with_a_different_anchor_context(self) -> None:
        links = extract_discovery(
            "https://example.test/page",
            None,
            '<https://example.test/a.md>; rel=alternate; type=text/markdown; '
            'anchor="https://other.test/page"',
        ).links
        self.assertEqual([], links)

    def test_accepts_equivalent_anchor_context(self) -> None:
        links = extract_discovery(
            "https://example.test",
            None,
            '<https://example.test/a.md>; rel=alternate; type=text/markdown; '
            'anchor="https://EXAMPLE.test:443/#section"',
        ).links
        self.assertEqual(1, len(links))
        self.assertEqual("http_header", links[0]["source"])

    def test_text_plain_is_not_a_v2_markdown_alternate(self) -> None:
        links = extract_discovery(
            "https://example.test/",
            '<link rel="alternate" href="/page.txt" type="text/plain">',
            None,
        ).links
        self.assertEqual([], links)

    def test_describedby_must_point_to_llms_txt(self) -> None:
        result = extract_discovery(
            "https://example.test/",
            '<link rel="describedby" href="/metadata.json">'
            '<link rel="describedby" href="/docs/llms.txt">',
            None,
        )
        self.assertEqual(1, len(result.links))
        self.assertEqual("describedby", result.links[0]["relation"])
        self.assertEqual("https://example.test/docs/llms.txt", result.links[0]["url"])

    def test_reports_complete_html_head(self) -> None:
        result = extract_discovery(
            "https://example.test/",
            "<html><head></head><body></body></html>",
            None,
        )
        self.assertTrue(result.html_head_complete)


class LlmsTxtClassificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.probe = response(b"not found", status=404, content_type="text/html")

    def test_accepts_utf8_markdown_with_a_title(self) -> None:
        result = classify_llms_txt(
            response(b"# Example\n\n- [Documentation](https://example.test/docs)"),
            self.probe,
        )
        self.assertEqual(LlmsTxtOutcome.PLAUSIBLE, result.outcome)

    def test_rejects_binary_octet_stream(self) -> None:
        result = classify_llms_txt(
            response(bytes(range(32, 64)), content_type="application/octet-stream"),
            self.probe,
        )
        self.assertEqual(LlmsTxtOutcome.UNSUPPORTED_MEDIA_TYPE, result.outcome)

    def test_rejects_invalid_utf8(self) -> None:
        result = classify_llms_txt(response(b"# Example\n\n\xff" * 10), self.probe)
        self.assertEqual(LlmsTxtOutcome.INVALID_UTF8, result.outcome)

    def test_requires_a_level_one_title(self) -> None:
        result = classify_llms_txt(
            response(b"Documentation without the required Markdown title"),
            self.probe,
        )
        self.assertEqual(LlmsTxtOutcome.MISSING_TITLE, result.outcome)

    def test_rejects_exact_soft_404_body(self) -> None:
        body = b"# Generic response\n\nThis route does not exist."
        result = classify_llms_txt(response(body), response(body))
        self.assertEqual(LlmsTxtOutcome.MATCHES_MISSING_PATH, result.outcome)

    def test_does_not_claim_plausibility_without_a_probe(self) -> None:
        result = classify_llms_txt(
            response(b"# Example\n\n- [Documentation](https://example.test/docs)"),
            response(b"", outcome=FetchOutcome.REQUEST_ERROR, status=0),
        )
        self.assertEqual(LlmsTxtOutcome.MISSING_PATH_PROBE_UNAVAILABLE, result.outcome)

    def test_separates_not_found_forbidden_and_other_http_errors(self) -> None:
        cases = (
            (404, LlmsTxtOutcome.NOT_FOUND),
            (403, LlmsTxtOutcome.FORBIDDEN),
            (429, LlmsTxtOutcome.HTTP_ERROR),
        )
        for status, expected in cases:
            with self.subTest(status=status):
                result = classify_llms_txt(response(b"", status=status), self.probe)
                self.assertEqual(expected, result.outcome)


if __name__ == "__main__":
    unittest.main()
