from __future__ import annotations

from collections import defaultdict
from enum import Enum
from urllib.parse import urlsplit

from protego import Protego

from .http import HttpClient
from .models import (
    FetchOutcome,
    FetchResult,
    RobotsCheckRecord,
    RobotsPolicyRecord,
)


COLLECTOR_TOKEN = "llms-txt-snapshots"
AGENT_TOKENS = {
    "collector": COLLECTOR_TOKEN,
    "gptbot": "GPTBot",
    "claudebot": "ClaudeBot",
    "google_extended": "Google-Extended",
    "ccbot": "CCBot",
}


class RobotsState(str, Enum):
    RULES = "rules"
    UNAVAILABLE = "unavailable"
    UNREACHABLE = "unreachable"


class RobotsPolicy:
    def __init__(
        self,
        authority: str,
        state: RobotsState,
        reason: str,
        resource: FetchResult,
        parser: Protego | None,
    ) -> None:
        self.authority = authority
        self.state = state
        self.reason = reason
        self.resource = resource
        self._parser = parser

    def decisions(self, url: str) -> dict[str, bool]:
        if self.state is RobotsState.UNAVAILABLE:
            return {name: True for name in AGENT_TOKENS}
        if self.state is RobotsState.UNREACHABLE:
            return {name: False for name in AGENT_TOKENS}
        assert self._parser is not None
        return {
            name: self._parser.can_fetch(url, token)
            for name, token in AGENT_TOKENS.items()
        }


class RobotsCache:
    def __init__(self, http: HttpClient) -> None:
        self._http = http
        self._policies: dict[str, RobotsPolicy] = {}
        self._checks: dict[str, dict[str, dict[str, bool]]] = defaultdict(dict)

    def can_fetch(self, url: str) -> bool:
        authority = authority_for(url)
        policy = self._policies.get(authority)
        if policy is None:
            policy = self._load_policy(authority)
            self._policies[authority] = policy
        decisions = policy.decisions(url)
        self._checks[authority][url] = decisions
        return decisions["collector"]

    def to_records(self) -> list[RobotsPolicyRecord]:
        records: list[RobotsPolicyRecord] = []
        for authority in sorted(self._policies):
            policy = self._policies[authority]
            checks: list[RobotsCheckRecord] = [
                {"url": url, "agents": self._checks[authority][url]}
                for url in sorted(self._checks[authority])
            ]
            records.append(
                {
                    "authority": authority,
                    "state": policy.state.value,
                    "reason": policy.reason,
                    "resource": policy.resource.to_record(),
                    "checks": checks,
                }
            )
        return records

    def _load_policy(self, authority: str) -> RobotsPolicy:
        resource = self._http.fetch(f"{authority}/robots.txt")
        if resource.outcome is not FetchOutcome.RESPONSE:
            return RobotsPolicy(
                authority,
                RobotsState.UNREACHABLE,
                f"robots.txt request ended as {resource.outcome.value}",
                resource,
                None,
            )

        status = resource.http_status
        if status is not None and 200 <= status < 300:
            try:
                parser = Protego.parse(resource.body.decode("utf-8", errors="replace"))
            except Exception as exc:
                return RobotsPolicy(
                    authority,
                    RobotsState.UNREACHABLE,
                    f"robots.txt parsing failed: {type(exc).__name__}: {exc}",
                    resource,
                    None,
                )
            return RobotsPolicy(
                authority,
                RobotsState.RULES,
                f"robots.txt rules parsed from HTTP {status}",
                resource,
                parser,
            )
        if status is not None and 400 <= status < 500:
            return RobotsPolicy(
                authority,
                RobotsState.UNAVAILABLE,
                f"robots.txt returned HTTP {status}; access allowed",
                resource,
                None,
            )
        return RobotsPolicy(
            authority,
            RobotsState.UNREACHABLE,
            f"robots.txt returned HTTP {status}; access denied",
            resource,
            None,
        )


def authority_for(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"URL is malformed: {url}") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError(f"URL must be absolute HTTPS: {url}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"URL must not contain credentials: {url}")
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    host_literal = f"[{host}]" if ":" in host else host
    authority = f"https://{host_literal}"
    if port is not None and port != 443:
        authority += f":{port}"
    return authority
