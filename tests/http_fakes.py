from __future__ import annotations

from collections.abc import Iterable

import requests


class StubResponse:
    def __init__(
        self,
        url: str,
        status: int = 200,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        chunks: Iterable[bytes] | None = None,
    ) -> None:
        self.url = url
        self.status_code = status
        self.headers = requests.structures.CaseInsensitiveDict(headers or {})
        self._chunks = list(chunks) if chunks is not None else [body]

    def iter_content(self, chunk_size: int) -> Iterable[bytes]:
        del chunk_size
        return iter(self._chunks)

    def __enter__(self) -> StubResponse:
        return self

    def __exit__(self, *_: object) -> None:
        return None


class StubSession:
    def __init__(
        self,
        responses: dict[str, StubResponse | requests.RequestException],
    ) -> None:
        self.responses = responses
        self.calls: list[str] = []
        self.closed = False

    def get(
        self,
        url: str,
        *,
        timeout: tuple[int, int],
        stream: bool,
        allow_redirects: bool,
    ) -> StubResponse:
        assert timeout == (4, 10)
        assert stream is True
        assert allow_redirects is False
        self.calls.append(url)
        response = self.responses[url]
        if isinstance(response, requests.RequestException):
            raise response
        return response

    def close(self) -> None:
        self.closed = True
