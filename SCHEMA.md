# Snapshot schema

Protocol v0.2 writes one JSON object per line to `observations.jsonl`. Records
are sorted by `target_url` after collection.

## Observation

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | string | Public record shape. |
| `collector_version` | string | Collector behavior version. |
| `collected_at` | RFC 3339 string | Completion time in UTC. |
| `category` | string | Label from `targets.csv`. |
| `target_url` | HTTPS URL | Exact declared landing URL. |
| `rationale` | string | Inclusion note from `targets.csv`. |
| `llms_txt_outcome` | string | Classified root `/llms.txt` result. |
| `llms_txt_reason` | string | Short explanation of that result. |
| `discovery_outcome` | string | `complete`, `partial`, or `unavailable`. |
| `discovery_links` | array | Relevant landing-page link metadata. |
| `robots_policies` | array | Policies loaded for every authority reached. |
| `resources` | object | `landing`, `llms_txt`, and `missing_path_probe`. |

`llms_txt_outcome` is one of:

- `plausible`
- `blocked_by_robots`
- `request_failed`
- `not_found`
- `forbidden`
- `http_error`
- `unsupported_media_type`
- `invalid_utf8`
- `too_short`
- `html_response`
- `missing_title`
- `matches_missing_path`
- `missing_path_probe_unavailable`

## Resource record

| Field | Type | Meaning |
|---|---|---|
| `outcome` | string | `response`, `blocked_by_robots`, `request_error`, or `redirect_error`. |
| `requested_url` | URL | URL passed to the HTTP client. |
| `final_url` | URL or null | Last reached or policy-checked URL. |
| `http_status` | integer or null | Terminal HTTP status when a response was received. |
| `content_type` | string | Terminal `Content-Type` header. |
| `observed_body_bytes` | integer | Bytes retained, at most 524,288. |
| `body_truncated` | boolean | Whether more decoded bytes existed beyond the retained prefix. |
| `observed_body_sha256` | string or null | SHA-256 of the retained bytes. |
| `elapsed_ms` | integer | Time spent in network requests, excluding robots checks. |
| `redirect_count` | integer | Redirect hops followed. |
| `redirect_chain` | array | Followed hops with `from_url`, `http_status`, and `to_url`. |
| `content_signal` | string or null | `Content-Signal` response header. |
| `x_robots_tag` | string or null | `X-Robots-Tag` response header. |
| `link_header_sha256` | string or null | SHA-256 of the raw HTTP `Link` header. |
| `error` | string or null | Request, redirect, or policy error. |

The raw `Link` header is parsed during collection but not stored. Only relevant
link rows and the header fingerprint remain in the public record.

## Discovery link

| Field | Meaning |
|---|---|
| `url` | Absolute destination URL. |
| `relation` | `alternate` or `describedby`. |
| `media_type` | Normalized `type` parameter, possibly empty. |
| `source` | `html` or `http_header`. |

An `alternate` row requires `type="text/markdown"`. A `describedby` row must
point to a path ending in `/llms.txt`.

## Robots policy

Each policy contains its `authority`, state, reason, fetched robots resource,
and every URL checked against that policy. States are:

- `rules`: a `2xx` robots response was parsed;
- `unavailable`: a `4xx` response, for which collection may continue;
- `unreachable`: a `5xx`, request failure, redirect failure, or parser failure,
  for which collection stops on that authority.

Every check stores boolean decisions under stable keys: `collector`, `gptbot`,
`claudebot`, `google_extended`, and `ccbot`. The full HTTP User-Agent is never
used as a key or as the robots product token.

## CSV projection

`summary.csv` contains category and target URL; landing outcome and status;
discovery completeness; `/llms.txt` status and outcome; counts of qualifying
`describedby` and Markdown-alternate links; and the two selected landing
headers. JSONL remains the canonical record.
