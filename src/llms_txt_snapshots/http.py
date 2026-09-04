from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol
from urllib.parse import urldefrag, urljoin, urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from .models import FetchOutcome, FetchResult, RedirectHopRecord


USER_AGENT = (
    "llms-txt-snapshots/0.2.0 "
    "(+https://github.com/levvs-one/llms-txt-snapshots)"
)
MAX_BODY_BYTES = 512 * 1024
MAX_REDIRECTS = 5
TIMEOUT = (4, 10)
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class HttpSession(Protocol):
    def get(self, url: str, **kwargs: object) -> requests.Response: ...

    def close(self) -> None: ...


def build_session() -> requests.Session:
    retry = Retry(
        total=1,
        connect=1,
        read=1,
        status=1,
        redirect=0,
        backoff_factor=0.5,
        backoff_max=2,
        retry_after_max=2,
        status_forcelist=(502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.trust_env = False
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})
    adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
    session.mount("https://", adapter)
    return session


def require_https_url(url: str) -> None:
    try:
        parsed = urlsplit(url)
        parsed.port
    except ValueError as exc:
        raise ValueError(f"URL is malformed: {url}") from exc
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError(f"URL must be absolute HTTPS: {url}")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"URL must not contain credentials: {url}")


class HttpClient:
    def __init__(self, session: HttpSession | None = None) -> None:
        self._session = session or build_session()

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def fetch(
        self,
        url: str,
        can_fetch: Callable[[str], bool] | None = None,
    ) -> FetchResult:
        require_https_url(url)
        requested_url = url
        current_url = url
        redirect_chain: list[RedirectHopRecord] = []
        request_elapsed_ms = 0

        while True:
            if can_fetch is not None and not can_fetch(current_url):
                return FetchResult(
                    outcome=FetchOutcome.BLOCKED_BY_ROBOTS,
                    requested_url=requested_url,
                    final_url=current_url,
                    http_status=None,
                    content_type="",
                    body=b"",
                    body_truncated=False,
                    elapsed_ms=request_elapsed_ms,
                    redirect_chain=tuple(redirect_chain),
                    error="robots.txt disallowed this URL",
                )

            started_ns = time.perf_counter_ns()
            try:
                with self._session.get(
                    current_url,
                    timeout=TIMEOUT,
                    stream=True,
                    allow_redirects=False,
                ) as response:
                    status = response.status_code
                    headers = response.headers

                    if status in REDIRECT_STATUSES:
                        request_elapsed_ms += _elapsed_ms(started_ns)
                        location = headers.get("location")
                        if not location:
                            return _redirect_error(
                                requested_url,
                                current_url,
                                status,
                                redirect_chain,
                                request_elapsed_ms,
                                "redirect response had no Location header",
                            )
                        if len(redirect_chain) >= MAX_REDIRECTS:
                            return _redirect_error(
                                requested_url,
                                current_url,
                                status,
                                redirect_chain,
                                request_elapsed_ms,
                                f"redirect limit exceeded ({MAX_REDIRECTS})",
                            )

                        next_url = urldefrag(urljoin(current_url, location)).url
                        try:
                            require_https_url(next_url)
                        except ValueError as exc:
                            return _redirect_error(
                                requested_url,
                                current_url,
                                status,
                                redirect_chain,
                                request_elapsed_ms,
                                str(exc),
                            )
                        visited_urls = {
                            requested_url,
                            *(hop["to_url"] for hop in redirect_chain),
                        }
                        if next_url in visited_urls:
                            return _redirect_error(
                                requested_url,
                                current_url,
                                status,
                                redirect_chain,
                                request_elapsed_ms,
                                "redirect loop detected",
                            )
                        redirect_chain.append(
                            {
                                "from_url": current_url,
                                "http_status": status,
                                "to_url": next_url,
                            }
                        )
                        current_url = next_url
                        continue

                    body, truncated = _read_bounded_body(response)
                    request_elapsed_ms += _elapsed_ms(started_ns)
                    return FetchResult(
                        outcome=FetchOutcome.RESPONSE,
                        requested_url=requested_url,
                        final_url=str(response.url or current_url),
                        http_status=status,
                        content_type=headers.get("content-type", ""),
                        body=body,
                        body_truncated=truncated,
                        elapsed_ms=request_elapsed_ms,
                        redirect_chain=tuple(redirect_chain),
                        content_signal=headers.get("content-signal"),
                        x_robots_tag=headers.get("x-robots-tag"),
                        link_header=headers.get("link"),
                    )
            except requests.RequestException as exc:
                request_elapsed_ms += _elapsed_ms(started_ns)
                return FetchResult(
                    outcome=FetchOutcome.REQUEST_ERROR,
                    requested_url=requested_url,
                    final_url=current_url,
                    http_status=None,
                    content_type="",
                    body=b"",
                    body_truncated=False,
                    elapsed_ms=request_elapsed_ms,
                    redirect_chain=tuple(redirect_chain),
                    error=f"{type(exc).__name__}: {exc}",
                )


def _read_bounded_body(response: requests.Response) -> tuple[bytes, bool]:
    body = bytearray()
    for chunk in response.iter_content(chunk_size=16 * 1024):
        if not chunk:
            continue
        remaining = MAX_BODY_BYTES - len(body)
        if remaining == 0:
            return bytes(body), True
        body.extend(chunk[:remaining])
        if len(chunk) > remaining:
            return bytes(body), True
    return bytes(body), False


def _redirect_error(
    requested_url: str,
    final_url: str,
    http_status: int,
    redirect_chain: list[RedirectHopRecord],
    elapsed_ms: int,
    message: str,
) -> FetchResult:
    return FetchResult(
        outcome=FetchOutcome.REDIRECT_ERROR,
        requested_url=requested_url,
        final_url=final_url,
        http_status=http_status,
        content_type="",
        body=b"",
        body_truncated=False,
        elapsed_ms=elapsed_ms,
        redirect_chain=tuple(redirect_chain),
        error=message,
    )


def _elapsed_ms(started_ns: int) -> int:
    return round((time.perf_counter_ns() - started_ns) / 1_000_000)
