# Methodology

Protocol version: `0.1`  
Pilot date: `2026-09-04`  
Research question: **How do selected public websites expose discovery and usage signals to AI agents?**

## Sampling

The pilot uses a declared, purposive sample rather than a traffic-ranked list. Targets were selected to cover five roles where machine-readable documentation and reuse policy are practically relevant:

1. AI model and tooling providers;
2. developer collaboration and package platforms;
3. cloud and deployment providers;
4. language and documentation ecosystems;
5. standards bodies and large public publishers.

This design avoids redistributing a third-party popularity list, but it cannot estimate web-wide prevalence. Each target and its inclusion rationale is committed before collection in [`sample/targets.csv`](sample/targets.csv).

## Request protocol

For each target, the collector:

1. requests `/robots.txt` using `agentic-web-signals/0.1` as the user agent;
2. parses the response with Protego 0.6.2;
3. skips any other URL that the parsed rules disallow for the collector;
4. requests the declared landing URL, `/llms.txt`, and one deterministic nonexistent path used only to detect soft 404 responses;
5. records status, final URL, content type, byte count, SHA-256, elapsed time, redirect count, and selected headers;
6. extracts only link metadata from the landing page and HTTP `Link` header;
7. discards all response bodies after extraction.

Requests use TLS verification, a 4-second connect timeout, a 10-second read timeout, at most one retry for `429`, `502`, `503`, and `504`, and no more than four target workers. Bodies are truncated after 512 KiB. The collector does not authenticate, bypass blocks, execute JavaScript, submit forms, or crawl discovered pages.

## Observed signals

The snapshot records:

- whether a plausible root `llms.txt` was observed;
- whether the landing page advertises `rel="describedby"`;
- whether it advertises `rel="alternate"` with a Markdown media type;
- `Content-Signal` and `X-Robots-Tag` header values when present;
- whether Protego allows the landing URL for `GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`, and the study collector.

A root `llms.txt` is classified as plausible only when it returns `200`, has a textual media type, differs from the soft-404 probe, and is not an obvious HTML error page. This is a conservative heuristic, not full conformance validation.

## Provenance and minimization

Every record includes the target URL, collection timestamp, collector version, and hashes of fetched bodies. Full page, `robots.txt`, and `llms.txt` bodies are intentionally not stored. This preserves auditability of repeated observations without republishing third-party text.

## Known limitations

- The sample is small, non-random, and biased toward technology-heavy sites.
- CDN, region, time, bot detection, and redirects can change responses.
- A soft 404 heuristic can produce false positives or false negatives.
- A homepage may not expose path-scoped signals used elsewhere on the site.
- Protego follows modern crawler conventions, but published policies can be ambiguous.
- `robots.txt` cannot prove how any company actually collects or uses content.
- A single snapshot cannot establish a trend; comparisons require future dated releases using the same protocol.

## Change policy

Protocol changes receive a new version and are documented before a new snapshot. Historical snapshots are immutable. Corrections add a note and a new file rather than rewriting a released observation silently.

