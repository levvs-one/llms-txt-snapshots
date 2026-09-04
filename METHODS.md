# Methods

- Protocol version: `0.2`
- Unit of observation: one declared HTTPS origin
- Target list: [`targets.csv`](targets.csv)

## Sample

The target list is a fixed convenience sample of 30 technology and publishing
origins. It was chosen to exercise the collector against different hosting
stacks, not to estimate adoption across the web. Categories are labels for
reading the table; they are not statistical strata.

Future runs can compare the same origins only when the protocol and target list
are unchanged. A protocol or sample change gets a separate version and cannot
be presented as a like-for-like trend.

## Requests and robots policy

The collector identifies itself as `llms-txt-snapshots/0.2.0` and sends anonymous
GET requests. Environment proxy and `.netrc` credentials are disabled. Connect
and read timeouts, response-size limits, retry counts, and worker counts are
fixed in the source.

Before requesting a resource, the collector loads `robots.txt` for that
resource's authority. Robots redirects are followed for at most five hops, as
described by RFC 9309, and the resulting rules apply to the original authority.
The outcomes are handled separately:

- a successful response is parsed and its `Allow` and `Disallow` rules are used;
- a `4xx` response is recorded as unavailable and collection may continue;
- a `5xx`, network failure, or parser failure is recorded as unreachable and
  collection stops for that authority.

Landing, `/llms.txt`, and missing-path requests use an explicit redirect loop.
Before every hop, including a hop to a different authority or path, the
collector checks the policy for the destination URL. The recorded redirect
chain shows each status and destination.

For every target, the requested resources are:

1. the declared landing URL;
2. `/llms.txt` at the declared authority;
3. one deterministic missing path used to detect an exact soft-404 response.

Response bodies are read only for classification and link extraction, up to
512 KiB after transfer decoding. The retained bytes are fingerprinted with
SHA-256 and then discarded. A fingerprint of a truncated response covers only
the retained prefix.

## `/llms.txt` outcomes

The main result is an outcome string rather than a boolean. It separates a
plausible document from `404`, forbidden, robots-blocked, request-failed,
non-text, HTML, short, malformed, and soft-404 responses.

A response is classified as present only when it returns `200`, uses a supported
text media type, decodes as UTF-8, contains a Markdown H1, is not HTML, and does
not exactly match the retained missing-path response. This is a format check,
not full validation of every link in the document.

## Discovery links

The collector examines the landing response's HTTP `Link` header and, for HTML
responses, `<link>` elements. It records:

- `rel="alternate"` only with `type="text/markdown"`;
- `rel="describedby"` only when the destination path ends in `/llms.txt`.

Relative URLs and RFC 8288 anchors are resolved against the response URL. A
link anchored to another context is not attributed to the landing page. Each
row keeps whether it came from HTML or the HTTP header.

If an HTML body is truncated before the parser sees the end of `<head>`, absence
is reported as indeterminate. A positive link found in the retained prefix
remains a positive observation.

## Limits

- Live responses vary by time, region, CDN, and bot controls.
- The sample is small and non-random.
- The collector honors `Allow` and `Disallow`; it does not implement optional
  crawl-delay or request-rate extensions.
- The missing-path comparison catches exact soft 404s, not every dynamic error
  template.
- Response fingerprints support later change detection, not reconstruction of
  discarded content.
- Published directives do not establish legal permission or actual crawler
  behavior.

The [v0.1 snapshot](snapshots/2026-09-04-v0.1/) is retained with a correction
note. It is not the baseline for protocol v0.2.
