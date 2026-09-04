from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from protego import Protego
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


COLLECTOR_VERSION = "0.1.0"
USER_AGENT = (
    "agentic-web-signals/0.1 "
    "(+https://github.com/levvs-one/agentic-web-signals)"
)
MAX_BODY_BYTES = 512 * 1024
TIMEOUT = (4, 10)
PROBE_PATH = "/.well-known/agentic-web-signals-probe-not-found-7f3a9d2c"
POLICY_AGENTS = ("GPTBot", "ClaudeBot", "Google-Extended", "CCBot", USER_AGENT)


class LinkMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return
        item = {key.lower(): value or "" for key, value in attrs}
        if item.get("href") and item.get("rel"):
            self.links.append(item)


def build_session() -> requests.Session:
    retry = Retry(
        total=1,
        connect=1,
        read=1,
        status=1,
        backoff_factor=0.5,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch(session: requests.Session, url: str) -> tuple[dict[str, object], bytes]:
    started = datetime.now(timezone.utc)
    try:
        with session.get(url, timeout=TIMEOUT, stream=True, allow_redirects=True) as response:
            chunks: list[bytes] = []
            size = 0
            truncated = False
            for chunk in response.iter_content(chunk_size=16 * 1024):
                if not chunk:
                    continue
                remaining = MAX_BODY_BYTES - size
                if len(chunk) > remaining:
                    chunks.append(chunk[:remaining])
                    size += remaining
                    truncated = True
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size == MAX_BODY_BYTES:
                    truncated = True
                    break
            body = b"".join(chunks)
            elapsed_ms = round(
                (datetime.now(timezone.utc) - started).total_seconds() * 1000
            )
            headers = {key.lower(): value for key, value in response.headers.items()}
            metadata: dict[str, object] = {
                "requested_url": url,
                "final_url": response.url,
                "status": response.status_code,
                "content_type": headers.get("content-type", ""),
                "bytes_read": len(body),
                "truncated": truncated,
                "sha256": hashlib.sha256(body).hexdigest(),
                "elapsed_ms": elapsed_ms,
                "redirects": len(response.history),
                "content_signal": headers.get("content-signal"),
                "x_robots_tag": headers.get("x-robots-tag"),
                "link_header": headers.get("link"),
                "error": None,
            }
            return metadata, body
    except requests.RequestException as exc:
        elapsed_ms = round(
            (datetime.now(timezone.utc) - started).total_seconds() * 1000
        )
        return (
            {
                "requested_url": url,
                "final_url": None,
                "status": None,
                "content_type": "",
                "bytes_read": 0,
                "truncated": False,
                "sha256": None,
                "elapsed_ms": elapsed_ms,
                "redirects": 0,
                "content_signal": None,
                "x_robots_tag": None,
                "link_header": None,
                "error": f"{type(exc).__name__}: {exc}",
            },
            b"",
        )


def decode_text(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    for part in content_type.split(";")[1:]:
        key, separator, value = part.strip().partition("=")
        if separator and key.lower() == "charset" and value:
            charset = value.strip('"\'')
            break
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def extract_discovery_links(
    base_url: str, html_text: str, link_header: str | None
) -> list[dict[str, str]]:
    parser = LinkMetadataParser()
    parser.feed(html_text)
    candidates = parser.links[:]
    if link_header:
        candidates.extend(requests.utils.parse_header_links(link_header.rstrip(">")))

    found: dict[tuple[str, str, str], dict[str, str]] = {}
    for item in candidates:
        rel_tokens = {token.lower() for token in item.get("rel", "").split()}
        media_type = item.get("type", "").lower()
        href = item.get("href") or item.get("url") or ""
        relevant = "describedby" in rel_tokens or (
            "alternate" in rel_tokens and media_type in {"text/markdown", "text/plain"}
        )
        if not relevant or not href:
            continue
        absolute = urljoin(base_url, href)
        rel = " ".join(sorted(rel_tokens))
        key = (absolute, rel, media_type)
        found[key] = {"url": absolute, "rel": rel, "type": media_type}
    return sorted(found.values(), key=lambda item: (item["rel"], item["url"]))


def plausible_llms(
    llms_metadata: dict[str, object],
    llms_body: bytes,
    probe_metadata: dict[str, object],
    probe_body: bytes,
) -> tuple[bool, str]:
    if llms_metadata.get("status") != 200:
        return False, "root llms.txt did not return HTTP 200"
    content_type = str(llms_metadata.get("content_type") or "").lower()
    if not any(token in content_type for token in ("text/", "markdown", "octet-stream")):
        return False, "response was not textual"
    if len(llms_body.strip()) < 20:
        return False, "response body was too short"
    prefix = llms_body[:512].lower()
    if b"<html" in prefix or b"<!doctype html" in prefix:
        return False, "response looked like an HTML page"
    if probe_metadata.get("status") == 200 and llms_body == probe_body:
        return False, "response matched the deterministic soft-404 probe"
    return True, "plausible textual llms.txt observed"


def robots_decisions(robots_body: bytes, target_url: str) -> dict[str, bool] | None:
    if not robots_body:
        return None
    parser = Protego.parse(robots_body.decode("utf-8", errors="replace"))
    return {agent: parser.can_fetch(target_url, agent) for agent in POLICY_AGENTS}


def collect_target(row: dict[str, str]) -> dict[str, object]:
    target_url = row["url"]
    parsed = urlparse(target_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    robots_url = urljoin(origin, "/robots.txt")
    llms_url = urljoin(origin, "/llms.txt")
    probe_url = urljoin(origin, PROBE_PATH)
    session = build_session()
    try:
        robots_metadata, robots_body = fetch(session, robots_url)
        decisions = robots_decisions(robots_body, target_url)
        collector_allowed = decisions is None or decisions.get(USER_AGENT, True)

        if collector_allowed:
            landing_metadata, landing_body = fetch(session, target_url)
            llms_metadata, llms_body = fetch(session, llms_url)
            probe_metadata, probe_body = fetch(session, probe_url)
            landing_text = decode_text(
                landing_body, str(landing_metadata.get("content_type") or "")
            )
            discovery = extract_discovery_links(
                str(landing_metadata.get("final_url") or target_url),
                landing_text,
                landing_metadata.get("link_header")
                if isinstance(landing_metadata.get("link_header"), str)
                else None,
            )
            llms_present, llms_reason = plausible_llms(
                llms_metadata, llms_body, probe_metadata, probe_body
            )
        else:
            skipped = {
                "requested_url": None,
                "final_url": None,
                "status": None,
                "content_type": "",
                "bytes_read": 0,
                "truncated": False,
                "sha256": None,
                "elapsed_ms": 0,
                "redirects": 0,
                "content_signal": None,
                "x_robots_tag": None,
                "link_header": None,
                "error": "skipped because robots.txt disallowed the collector",
            }
            landing_metadata = skipped.copy()
            llms_metadata = skipped.copy()
            probe_metadata = skipped.copy()
            discovery = []
            llms_present = False
            llms_reason = "not requested because robots.txt disallowed the collector"

        return {
            "schema_version": "0.1",
            "collector_version": COLLECTOR_VERSION,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "category": row["category"],
            "target_url": target_url,
            "rationale": row["rationale"],
            "collector_allowed": collector_allowed,
            "robots_decisions": decisions,
            "discovery_links": discovery,
            "llms_root_plausible": llms_present,
            "llms_classification": llms_reason,
            "resources": {
                "robots": robots_metadata,
                "landing": landing_metadata,
                "llms": llms_metadata,
                "soft_404_probe": probe_metadata,
            },
        }
    finally:
        session.close()


def load_sample(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = {"category", "url", "rationale"}
    if not rows or set(rows[0]) != expected:
        raise ValueError(f"sample must contain exactly these columns: {sorted(expected)}")
    for row in rows:
        parsed = urlparse(row["url"])
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError(f"target must be an absolute HTTPS URL: {row['url']}")
    return rows


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_summary(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "category",
        "target_url",
        "collector_allowed",
        "landing_status",
        "robots_status",
        "llms_status",
        "llms_root_plausible",
        "describedby_links",
        "markdown_alternates",
        "content_signal",
        "x_robots_tag",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            resources = record["resources"]
            links = record["discovery_links"]
            landing = resources["landing"]
            writer.writerow(
                {
                    "category": record["category"],
                    "target_url": record["target_url"],
                    "collector_allowed": record["collector_allowed"],
                    "landing_status": landing["status"],
                    "robots_status": resources["robots"]["status"],
                    "llms_status": resources["llms"]["status"],
                    "llms_root_plausible": record["llms_root_plausible"],
                    "describedby_links": sum(
                        "describedby" in link["rel"].split() for link in links
                    ),
                    "markdown_alternates": sum(
                        "alternate" in link["rel"].split()
                        and link["type"] in {"text/markdown", "text/plain"}
                        for link in links
                    ),
                    "content_signal": landing["content_signal"],
                    "x_robots_tag": landing["x_robots_tag"],
                }
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sample = load_sample(args.sample)
    records: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(collect_target, row): row["url"] for row in sample}
        for future in as_completed(futures):
            url = futures[future]
            try:
                record = future.result()
            except Exception as exc:
                print(f"collection failed for {url}: {type(exc).__name__}: {exc}", file=sys.stderr)
                return 1
            records.append(record)
            status = record["resources"]["landing"]["status"]
            print(f"collected {url} landing={status} llms={record['llms_root_plausible']}")
    records.sort(key=lambda item: str(item["target_url"]))
    write_jsonl(args.out, records)
    summary_path = args.summary or args.out.with_suffix(".csv")
    write_summary(summary_path, records)
    print(f"wrote {len(records)} observations to {args.out}")
    print(f"wrote summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

