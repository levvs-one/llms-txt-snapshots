from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urljoin

from .http import HttpClient, HttpSession
from .models import FetchOutcome, ObservationRecord
from .robots import RobotsCache, authority_for
from .signals import classify_llms_txt, decode_html, extract_discovery


SCHEMA_VERSION = "0.2"
COLLECTOR_VERSION = "0.2.0"
MISSING_PATH = "/.well-known/llms-txt-snapshots-missing-7f3a9d2c"
HTML_MEDIA_TYPES = frozenset({"text/html", "application/xhtml+xml"})


@dataclass(frozen=True)
class Target:
    category: str
    url: str
    rationale: str


def collect_target(
    target: Target,
    session: HttpSession | None = None,
) -> ObservationRecord:
    http = HttpClient(session=session)
    try:
        robots = RobotsCache(http)
        authority = authority_for(target.url)
        landing = http.fetch(target.url, robots.can_fetch)
        llms_txt = http.fetch(urljoin(authority, "/llms.txt"), robots.can_fetch)
        missing_path_probe = http.fetch(
            urljoin(authority, MISSING_PATH),
            robots.can_fetch,
        )

        html_text = None
        discovery_outcome = "unavailable"
        if (
            landing.outcome is FetchOutcome.RESPONSE
            and landing.http_status is not None
            and 200 <= landing.http_status < 300
        ):
            media_type = landing.content_type.partition(";")[0].strip().lower()
            if media_type in HTML_MEDIA_TYPES:
                html_text = decode_html(landing.body, landing.content_type)
            discovery = extract_discovery(
                landing.final_url or target.url,
                html_text,
                landing.link_header,
            )
            discovery_links = discovery.links
            discovery_outcome = "complete"
            if (
                html_text is not None
                and landing.body_truncated
                and not discovery.html_head_complete
            ):
                discovery_outcome = "partial"
        else:
            discovery_links = []

        classification = classify_llms_txt(llms_txt, missing_path_probe)
        return {
            "schema_version": SCHEMA_VERSION,
            "collector_version": COLLECTOR_VERSION,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "category": target.category,
            "target_url": target.url,
            "rationale": target.rationale,
            "llms_txt_outcome": classification.outcome.value,
            "llms_txt_reason": classification.reason,
            "discovery_outcome": discovery_outcome,
            "discovery_links": discovery_links,
            "robots_policies": robots.to_records(),
            "resources": {
                "landing": landing.to_record(),
                "llms_txt": llms_txt.to_record(),
                "missing_path_probe": missing_path_probe.to_record(),
            },
        }
    finally:
        http.close()


def collect_targets(
    targets: list[Target],
    workers: int = 4,
) -> list[ObservationRecord]:
    records: list[ObservationRecord] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(collect_target, target): target.url for target in targets
        }
        for future in as_completed(futures):
            records.append(future.result())
    records.sort(key=lambda record: str(record["target_url"]))
    return records
