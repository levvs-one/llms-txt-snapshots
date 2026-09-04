# v0.1 snapshot: 2026-09-04

This is the first 30-origin run. It is kept as released, including the limits
listed below. Use [`observations.jsonl`](observations.jsonl) for the complete
records and [`summary.csv`](summary.csv) for the flat projection.

## Results

| Check | Observed outcome |
|---|---:|
| Root `/llms.txt` classified as plausible | 7 |
| Root `/llms.txt` returned `404` | 21 |
| Root `/llms.txt` returned `403` | 2 |
| Landing response returned `200` | 27 |
| Landing response returned `403` | 2 |
| Landing response returned `404` | 1 |
| Markdown alternate found on a landing response | 2 |
| `describedby` link found on a landing response | 0 |
| `Content-Signal` header found | 0 |
| `X-Robots-Tag` header found | 0 |

The seven positive root checks were Azure, Cloudflare, Cohere, GitHub,
Netlify, Node.js, and Vercel. Cloudflare and Netlify advertised a Markdown
alternate.

Four `200` landing bodies reached the 512 KiB read limit: Cohere, GitHub,
Node.js, and Cloudflare. Cloudflare's retained prefix contained a Markdown
alternate. For the other three origins, the result means "not found in the
retained prefix," not "absent from the page." Three non-`200` landing outcomes
are also not evidence of absence.

## Known v0.1 problems

The review for [issue #1](https://github.com/levvs-one/llms-txt-snapshots/issues/1)
found flaws in the first collector:

- resource redirects were followed automatically, so a redirect to another
  origin did not trigger a check of that origin's `robots.txt`;
- a `5xx` or network failure while loading `robots.txt` would have been treated
  like no policy, although no such robots outcome occurred in this run;
- the full HTTP User-Agent string was passed to the robots parser instead of a
  stable product token;
- one boolean combined not found, forbidden, skipped, and invalid `/llms.txt`
  outcomes;
- landing-page totals did not distinguish complete, truncated, and non-`200`
  responses.

These problems are why v0.1 is not used as a trend baseline. The original
files remain available for inspection rather than being silently replaced.

## Scope

The origins were selected as a small convenience sample of technology and
publishing sites. The counts describe only these exact requests on this date.
They do not estimate web-wide adoption, legal permission, or crawler behavior.
