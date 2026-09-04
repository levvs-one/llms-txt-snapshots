# Snapshot: 2026-09-04, protocol v0.2

Thirty selected HTTPS origins were checked between 19:51:59 and 19:52:14 UTC.
The [observations](observations.jsonl) contain the complete records;
[summary.csv](summary.csv) is the flat projection.

## Results

| Check | Observed | Other outcomes |
|---|---:|---:|
| Plausible root `/llms.txt` | 7 | 21 not found, 2 forbidden |
| Landing response with Markdown alternate | 2 of 27 successful responses | 25 without one |
| Landing response with `/llms.txt` `describedby` link | 0 of 27 successful responses | 27 without one |
| `Content-Signal` response header | 0 | 30 without one |
| `X-Robots-Tag` response header | 0 | 30 without one |

The seven plausible root files were observed at Azure, Cloudflare, Cohere,
GitHub, Netlify, Node.js, and Vercel. Cloudflare linked
`https://www.cloudflare.com/.md`; Netlify linked
`https://www.netlify.com/index.md`. Both links came from HTML and used
`rel="alternate" type="text/markdown"`.

Landing requests returned `200` for 27 origins, `403` for npm and Stack
Overflow, and `404` for crates.io. The non-`200` outcomes are not counted as
negative discovery observations.

Four landing bodies reached the 512 KiB limit, but each retained prefix
included a closing `</head>`. The HTML discovery result is therefore complete
for the document head under this protocol. All 30 resource sets completed
without a request or robots-policy error.

## Category table

The categories are reading aids for this convenience sample, not statistical
strata.

| Category | Origins | Landing `200` | Plausible `/llms.txt` | Markdown alternate |
|---|---:|---:|---:|---:|
| AI platforms | 5 | 5 | 1 | 0 |
| Cloud | 5 | 5 | 4 | 2 |
| Developer platforms | 7 | 4 | 1 | 0 |
| Documentation and projects | 8 | 8 | 1 | 0 |
| Standards and publishing | 5 | 5 | 0 | 0 |
| **Total** | **30** | **27** | **7** | **2** |

## Reading the snapshot

These counts describe the exact origins, user agent, and time above. They do
not estimate web-wide adoption. A plausible result confirms a textual `200`
response with the expected top-level Markdown structure; it does not validate
every link in the file. Crawler directives are published preferences, not
evidence of crawler behavior or legal permission.
