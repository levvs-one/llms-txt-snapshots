# llms.txt snapshots

Dated checks of `/llms.txt`, discovery links, and crawler directives across a
fixed set of public web origins.

The collector requests each declared landing URL, its root `/llms.txt`, and one
missing path. It records HTTP outcomes, redirect hops, robots decisions, link
metadata, selected headers, and fingerprints of the retained response bytes.
Response bodies are not published.

## Latest snapshot

The protocol v0.2 run on 2026-09-04 covered 30 selected origins.

| Result | Count |
|---|---:|
| Plausible root `/llms.txt` | 7 |
| Root `/llms.txt` not found | 21 |
| Root `/llms.txt` forbidden | 2 |
| Successful landing response | 27 |
| Landing response with Markdown alternate | 2 of 27 |
| Landing response with `/llms.txt` `describedby` link | 0 of 27 |

See the [report](snapshots/2026-09-04-v0.2/) and
[JSONL observations](snapshots/2026-09-04-v0.2/observations.jsonl). The sample
is deliberately small and non-random; these counts are not web-wide estimates.

## Run the collector

Python 3.10 or newer is required.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m llms_txt_snapshots --targets targets.csv --output-dir runs\local
```

The output directory must not already exist. A run writes
`observations.jsonl` and `summary.csv`; released snapshots cannot be overwritten
by the CLI.

## Files

- [`METHODS.md`](METHODS.md) defines the request and classification rules.
- [`SCHEMA.md`](SCHEMA.md) documents the JSONL and CSV fields.
- [`targets.csv`](targets.csv) is the fixed convenience sample.
- [`snapshots/`](snapshots/) contains versioned observations and reports.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) lists the checks required for changes.

The [v0.1 snapshot](snapshots/2026-09-04-v0.1/) is kept with a correction note.
It is not used as the v0.2 baseline.

## References

- [llms.txt proposal, revision 2](https://llmstxt.org/)
- [Robots Exclusion Protocol, RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)

Code and documentation are under the [MIT License](LICENSE). Original snapshot
metadata is dedicated under [CC0 1.0](DATA-LICENSE.md). Source sites retain all
rights in their content.
