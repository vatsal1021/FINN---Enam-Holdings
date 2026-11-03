# FINN local interactive preview

Run from the workspace root (Python standard library only):

```powershell
python .\preview\prepare_samples.py
python .\preview\serve.py --port 8765
```

Open **http://127.0.0.1:8765**. Stop the server with Ctrl+C in its terminal. It binds only to this computer's loopback interface. A physical phone cannot open this URL on its own; use desktop browser device emulation at 390×844 or 360×800 for this local preview. No package install, hosting account or model credential is needed. Open through the HTTP server, not `file://`.

## What is implemented

- Digest with company/date/category filters, two manually prioritised real filing examples, accessible routine/unreviewed records and a simulated 1.5-second loading replay.
- All fifteen selected companies, search and name/day-move/coverage sorting. Four official NSE EOD samples from **29 October 2026**; missing prices remain unavailable.
- Investigation views for all names: manually authored saved briefs for Infosys/Cera, explicitly limited KPR/Apollo cases, and honest not-loaded states for the other eleven.
- Native modal evidence drawer with real extracted passages, document/date/period/page metadata, source identity, saved source-page reader, saved full PDFs and original-source links. Links open in new tabs, preserving the preview.
- Back/Escape and drawer close preserve filters and scroll. Browser session storage retains view/filter/search/sort/reading state; full browser restart persistence is not promised.
- Visible stale KPR call (August 2023), Apollo cover-letter/HTTP-403 partial case, empty sample period and missing-company states. No invented data.

## Try these paths

1. Digest → choose KPR Mill → review results → inspect PDF page 9 → open saved page/full PDF or original source in a new tab → return → close drawer. The company/date/category filters and exact reading position should remain.
2. Companies → sort by day move → search `CERA` → open company → management view → inspect the August call evidence. Return to Companies with search/sort intact.
3. Companies → KPR Mill → source coverage → stale August 2023 call. It is never presented as a current management view.
4. Companies → Apollo Hospitals → partial cover-letter case; then choose an unloaded company such as Reliance.
5. Digest → 30 Oct empty sample → reset. Use **Replay loading** for the loading example; it does not fetch new data.

## Boundaries and provenance

This is an interaction preview, not the final recruitment submission. No ingestion service, live AI, arbitrary-ticker research, backend database, scheduler or hosted deployment is implemented. All summaries, questions/views and priorities are manually authored. Dates remain attached; the UI never calls the content live.

`prepare_samples.py` reads only existing experiment files. `dist/data.json` contains the selected text/metadata. `document_routes.json` maps explicit local PDF/image URLs to saved experiments; the static server does not expose the workspace generally. Eight filing examples are selected, not a complete exchange-feed archive. Source-level URLs, retrieval timestamps and SHA-256 hashes are retained. Original websites may block or change access independently of the saved evidence.

KPR financial summary is manually checked: original consolidated page 9 in INR lakh, revenue 187,117 + 6,857 = 193,974 lakh = ₹1,939.74 crore; PAT 34,500 lakh = ₹345.00 crore. Infosys passage is actual earnings-call PDF page 25, not the press-conference section. Cera August guidance is forward-looking; October call notice is not a transcript. Apollo full-call HTTP 403 and KPR old-call limitations are saved experiment outcomes, not newly run network tests.

Actual preview checks and screenshots are recorded in `../project-notes/verification.md`. This file describes intended behavior; only observed checks there count as passed.

Observed on October 30: 42/42 HTTP/content checks (`check-results.json`), JavaScript/Python syntax checks, all fifteen research selections, list sorting/search and state restoration, original KPR NSE PDF navigation, evidence Back/Escape/focus wrap, and loading/empty/stale/partial examples. Browser observations: `browser-results.json`. Main views/drawer confirmed at 390×844 CSS px; source reader also inspected at desktop width. Real phone and 360/768 widths are not verified. Screenshots under `screenshots/` are actual captures; source-reader screenshot is labelled desktop.
