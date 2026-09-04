from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests

from .models import DiscoveryLinkRecord, FetchOutcome, FetchResult


MARKDOWN_MEDIA_TYPE = "text/markdown"
LLMS_TEXT_MEDIA_TYPES = frozenset({"text/plain", MARKDOWN_MEDIA_TYPE})


class LlmsTxtOutcome(str, Enum):
    PLAUSIBLE = "plausible"
    BLOCKED_BY_ROBOTS = "blocked_by_robots"
    REQUEST_FAILED = "request_failed"
    NOT_FOUND = "not_found"
    FORBIDDEN = "forbidden"
    HTTP_ERROR = "http_error"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    INVALID_UTF8 = "invalid_utf8"
    TOO_SHORT = "too_short"
    HTML_RESPONSE = "html_response"
    MISSING_TITLE = "missing_title"
    MATCHES_MISSING_PATH = "matches_missing_path"
    MISSING_PATH_PROBE_UNAVAILABLE = "missing_path_probe_unavailable"


@dataclass(frozen=True)
class LlmsTxtClassification:
    outcome: LlmsTxtOutcome
    reason: str


@dataclass(frozen=True)
class DiscoveryExtraction:
    links: list[DiscoveryLinkRecord]
    html_head_complete: bool | None


class LinkMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.base_href: str | None = None
        self.links: list[dict[str, str]] = []
        self.head_complete = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        item = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "base" and self.base_href is None and item.get("href"):
            self.base_href = item["href"]
        elif tag.lower() == "link" and item.get("href") and item.get("rel"):
            self.links.append(item)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "head":
            self.head_complete = True


def extract_discovery(
    base_url: str,
    html_text: str | None,
    link_header: str | None,
) -> DiscoveryExtraction:
    candidates: list[tuple[dict[str, str], str, str]] = []
    html_head_complete: bool | None = None

    if html_text is not None:
        parser = LinkMetadataParser()
        parser.feed(html_text)
        html_head_complete = parser.head_complete
        document_base = urljoin(base_url, parser.base_href or base_url)
        candidates.extend((item, "html", document_base) for item in parser.links)

    if link_header:
        parsed_links = requests.utils.parse_header_links(link_header)
        for item in parsed_links:
            normalized = {
                str(key).lower(): "" if value is None else str(value)
                for key, value in item.items()
            }
            anchor = normalized.get("anchor")
            if anchor is not None and not _same_context(
                urljoin(base_url, anchor),
                base_url,
            ):
                continue
            candidates.append((normalized, "http_header", base_url))

    found: dict[tuple[str, str, str, str], DiscoveryLinkRecord] = {}
    for item, source, resolution_base in candidates:
        rel_tokens = {token.lower() for token in item.get("rel", "").split()}
        media_type = item.get("type", "").strip().lower()
        href = item.get("href") or item.get("url") or ""
        if not href:
            continue
        absolute = urljoin(resolution_base, href)
        relations = []
        if "alternate" in rel_tokens and media_type == MARKDOWN_MEDIA_TYPE:
            relations.append("alternate")
        if "describedby" in rel_tokens and _is_llms_txt_url(absolute):
            relations.append("describedby")
        for relation in relations:
            key = (source, absolute, relation, media_type)
            found[key] = {
                "url": absolute,
                "relation": relation,
                "media_type": media_type,
                "source": source,
            }
    links = sorted(
        found.values(),
        key=lambda item: (
            item["source"],
            item["relation"],
            item["url"],
            item["media_type"],
        ),
    )
    return DiscoveryExtraction(links, html_head_complete)


def _is_llms_txt_url(url: str) -> bool:
    try:
        path = urlsplit(url).path
    except ValueError:
        return False
    return path.rstrip("/").endswith("/llms.txt")


def _same_context(left: str, right: str) -> bool:
    try:
        left_parts = urlsplit(left)
        right_parts = urlsplit(right)
        left_port = left_parts.port
        right_port = right_parts.port
    except ValueError:
        return False

    def normalized_port(scheme: str, port: int | None) -> int | None:
        if port is not None:
            return port
        return {"http": 80, "https": 443}.get(scheme.lower())

    return (
        left_parts.scheme.lower() == right_parts.scheme.lower()
        and (left_parts.hostname or "").lower()
        == (right_parts.hostname or "").lower()
        and normalized_port(left_parts.scheme, left_port)
        == normalized_port(right_parts.scheme, right_port)
        and (left_parts.path or "/") == (right_parts.path or "/")
        and left_parts.query == right_parts.query
    )


def classify_llms_txt(
    llms_txt: FetchResult,
    missing_path_probe: FetchResult,
) -> LlmsTxtClassification:
    if llms_txt.outcome is FetchOutcome.BLOCKED_BY_ROBOTS:
        return LlmsTxtClassification(
            LlmsTxtOutcome.BLOCKED_BY_ROBOTS,
            "root llms.txt was blocked by robots.txt",
        )
    if llms_txt.outcome is not FetchOutcome.RESPONSE:
        return LlmsTxtClassification(
            LlmsTxtOutcome.REQUEST_FAILED,
            f"root llms.txt request ended as {llms_txt.outcome.value}",
        )
    if llms_txt.http_status in {404, 410}:
        return LlmsTxtClassification(
            LlmsTxtOutcome.NOT_FOUND,
            f"root llms.txt returned HTTP {llms_txt.http_status}",
        )
    if llms_txt.http_status in {401, 403}:
        return LlmsTxtClassification(
            LlmsTxtOutcome.FORBIDDEN,
            f"root llms.txt returned HTTP {llms_txt.http_status}",
        )
    if llms_txt.http_status != 200:
        return LlmsTxtClassification(
            LlmsTxtOutcome.HTTP_ERROR,
            f"root llms.txt returned HTTP {llms_txt.http_status}",
        )

    media_type = llms_txt.content_type.partition(";")[0].strip().lower()
    if media_type not in LLMS_TEXT_MEDIA_TYPES:
        return LlmsTxtClassification(
            LlmsTxtOutcome.UNSUPPORTED_MEDIA_TYPE,
            f"root llms.txt used unsupported media type {media_type or '(missing)'}",
        )
    try:
        text = llms_txt.body.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        return LlmsTxtClassification(
            LlmsTxtOutcome.INVALID_UTF8,
            "root llms.txt was not valid UTF-8",
        )
    stripped = text.strip()
    if len(stripped) < 20:
        return LlmsTxtClassification(
            LlmsTxtOutcome.TOO_SHORT,
            "root llms.txt body was too short",
        )
    prefix = stripped[:512].lower()
    if "<html" in prefix or "<!doctype html" in prefix:
        return LlmsTxtClassification(
            LlmsTxtOutcome.HTML_RESPONSE,
            "root llms.txt looked like an HTML page",
        )
    first_line = next((line for line in text.splitlines() if line.strip()), "")
    leading_spaces = len(first_line) - len(first_line.lstrip(" "))
    if leading_spaces > 3 or not first_line[leading_spaces:].startswith("# "):
        return LlmsTxtClassification(
            LlmsTxtOutcome.MISSING_TITLE,
            "root llms.txt did not start with a level-one Markdown title",
        )

    if (
        missing_path_probe.outcome is not FetchOutcome.RESPONSE
        or missing_path_probe.http_status is None
        or missing_path_probe.http_status >= 500
    ):
        return LlmsTxtClassification(
            LlmsTxtOutcome.MISSING_PATH_PROBE_UNAVAILABLE,
            "the missing-path probe could not rule out a soft 404",
        )
    if (
        missing_path_probe.http_status == 200
        and llms_txt.body == missing_path_probe.body
    ):
        return LlmsTxtClassification(
            LlmsTxtOutcome.MATCHES_MISSING_PATH,
            "root llms.txt matched the deterministic missing-path response",
        )
    return LlmsTxtClassification(
        LlmsTxtOutcome.PLAUSIBLE,
        "plausible textual llms.txt observed",
    )


def decode_html(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    for parameter in content_type.split(";")[1:]:
        key, separator, value = parameter.strip().partition("=")
        if separator and key.lower() == "charset" and value:
            charset = value.strip('"\'')
            break
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")
