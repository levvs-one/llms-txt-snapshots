from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import TypedDict


class RedirectHopRecord(TypedDict):
    from_url: str
    http_status: int
    to_url: str


class ResourceRecord(TypedDict):
    outcome: str
    requested_url: str
    final_url: str | None
    http_status: int | None
    content_type: str
    observed_body_bytes: int
    body_truncated: bool
    observed_body_sha256: str | None
    elapsed_ms: int
    redirect_count: int
    redirect_chain: list[RedirectHopRecord]
    content_signal: str | None
    x_robots_tag: str | None
    link_header_sha256: str | None
    error: str | None


class DiscoveryLinkRecord(TypedDict):
    url: str
    relation: str
    media_type: str
    source: str


class RobotsCheckRecord(TypedDict):
    url: str
    agents: dict[str, bool]


class RobotsPolicyRecord(TypedDict):
    authority: str
    state: str
    reason: str
    resource: ResourceRecord
    checks: list[RobotsCheckRecord]


class ResourcesRecord(TypedDict):
    landing: ResourceRecord
    llms_txt: ResourceRecord
    missing_path_probe: ResourceRecord


class ObservationRecord(TypedDict):
    schema_version: str
    collector_version: str
    collected_at: str
    category: str
    target_url: str
    rationale: str
    llms_txt_outcome: str
    llms_txt_reason: str
    discovery_outcome: str
    discovery_links: list[DiscoveryLinkRecord]
    robots_policies: list[RobotsPolicyRecord]
    resources: ResourcesRecord


class FetchOutcome(str, Enum):
    RESPONSE = "response"
    BLOCKED_BY_ROBOTS = "blocked_by_robots"
    REQUEST_ERROR = "request_error"
    REDIRECT_ERROR = "redirect_error"


@dataclass(frozen=True)
class FetchResult:
    outcome: FetchOutcome
    requested_url: str
    final_url: str | None
    http_status: int | None
    content_type: str
    body: bytes
    body_truncated: bool
    elapsed_ms: int
    redirect_chain: tuple[RedirectHopRecord, ...]
    content_signal: str | None = None
    x_robots_tag: str | None = None
    link_header: str | None = None
    error: str | None = None

    def to_record(self) -> ResourceRecord:
        digest = (
            sha256(self.body).hexdigest()
            if self.outcome is FetchOutcome.RESPONSE
            else None
        )
        link_digest = (
            sha256(self.link_header.encode("utf-8")).hexdigest()
            if self.link_header is not None
            else None
        )
        return {
            "outcome": self.outcome.value,
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "http_status": self.http_status,
            "content_type": self.content_type,
            "observed_body_bytes": len(self.body),
            "body_truncated": self.body_truncated,
            "observed_body_sha256": digest,
            "elapsed_ms": self.elapsed_ms,
            "redirect_count": len(self.redirect_chain),
            "redirect_chain": list(self.redirect_chain),
            "content_signal": self.content_signal,
            "x_robots_tag": self.x_robots_tag,
            "link_header_sha256": link_digest,
            "error": self.error,
        }
