# Data dictionary

The canonical snapshot is newline-delimited JSON. Each line is one independently collected target observation. The CSV is a convenience projection for quick comparison; fields omitted from CSV remain available in JSONL.

## Observation fields

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | string | Shape of the observation record. |
| `collector_version` | string | Version of the collection behavior. |
| `collected_at` | RFC 3339 timestamp | Completion time for this target in UTC. |
| `category` | string | Declared sample category. |
| `target_url` | HTTPS URL | Landing URL committed before collection. |
| `rationale` | string | Reason the target belongs in the purposive sample. |
| `collector_access` | object | Protego decision for the landing, root `llms.txt`, and soft-404 probe paths. |
| `robots_decisions` | object or null | Protego decisions for named agents at the landing URL. `null` means no HTTP `200` robots body was available. |
| `discovery_links` | array | Relevant HTML or HTTP links normalized to absolute URLs. |
| `llms_root_plausible` | boolean | Conservative root `llms.txt` classification. |
| `llms_classification` | string | Human-readable reason for the classification. |
| `resources` | object | Metadata for `robots`, `landing`, `llms`, and `soft_404_probe` requests. |

## Resource metadata

Each resource contains:

| Field | Meaning |
|---|---|
| `requested_url` | URL requested by the collector. |
| `final_url` | URL after redirects, or `null` when no response was available. |
| `status` | HTTP status, or `null` for a request error or robots-based skip. |
| `content_type` | Response `Content-Type` value. |
| `bytes_read` | Bytes retained for analysis, capped at 524,288. |
| `truncated` | Whether the body reached the byte cap. |
| `sha256` | Hash of the retained body. Bodies are not stored. |
| `elapsed_ms` | Observed request duration, including retries. |
| `redirects` | Redirect responses followed by Requests. |
| `content_signal` | `Content-Signal` response header when present. |
| `x_robots_tag` | `X-Robots-Tag` response header when present. |
| `link_header` | HTTP `Link` header used for discovery parsing. |
| `error` | Exception or explicit skip reason, otherwise `null`. |

## Reuse notes

- Treat missing, blocked, and non-`200` observations separately from negative observations.
- Do not infer legal permission or actual crawler behavior from these fields.
- Keep the collection date attached to every derived table: public signals can change at any time.
- Cite the release, not a mutable branch, when using a snapshot in another analysis.

