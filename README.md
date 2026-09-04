# Agentic Web Signals

A reproducible field study of how public websites communicate preferences and discovery hints to AI agents.

The project observes four machine-readable surfaces:

- `robots.txt` rules for named AI-related user agents;
- root and linked `llms.txt` resources;
- HTTP and HTML links such as `rel="describedby"` and Markdown alternates;
- response headers such as `Content-Signal` and `X-Robots-Tag`.

## Why this exists

`llms.txt` v2 introduced path-scoped discovery and explicit link relations in August 2026. Most public measurements still focus on whether `/llms.txt` exists. This repository starts with a smaller, auditable question: can an agent discover the signals, and do those signals agree?

The first release is a purposive pilot across AI labs, developer platforms, cloud providers, language ecosystems, and standards or publishing sites. It is not a popularity ranking and must not be generalized to the whole web.

## Repository map

- [`METHODOLOGY.md`](METHODOLOGY.md) defines the protocol, ethics, and limits.
- [`sample/targets.csv`](sample/targets.csv) is the declared pilot sample.
- `src/collect.py` performs bounded requests and writes machine-readable observations.
- `tests/` checks parsing and classification against authored fixtures.
- `data/snapshots/` contains dated JSONL observations without copied page bodies.
- `reports/` contains dated findings derived from a snapshot.

## Reproduce the pilot

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe src\collect.py --sample sample\targets.csv --out data\snapshots\2026-09-04.jsonl
```

The collector identifies itself, fetches `robots.txt` first, respects rules for its own user agent, limits bodies to 512 KiB, uses four workers, and retries only safe `GET` requests after transient failures.

## Interpretation boundary

These files record published signals, not crawler behavior, legal permission, or policy compliance. `robots.txt` expresses preferences; it is not authentication or access control. Absence of a signal means “not observed,” never “allowed.”

## Sources

- [llms.txt v2 specification](https://llmstxt.org/)
- [llms.txt v2 changes](https://llmstxt.org/changes.html)
- [Robots Exclusion Protocol, RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)
- [Cloudflare managed robots.txt and Content Signals](https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/)

## License

Original code, documentation, and extracted factual observations are released under the [MIT License](LICENSE). Source websites retain all rights in their content; response bodies are hashed and discarded rather than republished.

