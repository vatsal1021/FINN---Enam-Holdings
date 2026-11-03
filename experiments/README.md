# FINN data feasibility experiments

These are bounded read-only retrieval and extraction experiments, **not application scaffolding**. All samples are dated October 30, 2026, not live data. The completion evidence and scope recommendation are in `../project-notes/verification.md` and `decisions-and-plan.md`.

## Environment and provenance

- Tested locally with Python 3.14 and PyMuPDF 1.26.5 already under `../tmp/pdf-render-tools`. Standard library handles HTTP, HTML, CSV and JSON. No model or paid API was used. A fresh environment needs `python -m pip install --target .\tmp\pdf-render-tools PyMuPDF==1.26.5 --no-deps` from workspace root.
- `data_probe.py` is the configurable CLI. NSE/Yahoo URLs use the ticker argument. `companies.json` supplies IR **index pages**, not an allowlist of PDF links. NSE annual-report discovery works without a company-specific index. A held-out ticker was APOLLOHOSP; the generic prices/announcements/annual-index functions were unchanged.
- `samples/requests.jsonl` records each actual HTTP attempt, full requested/final URL, UTC retrieval start, duration, status/error, bytes, SHA256, and saved file. UTC +05:30 is IST. `commands.jsonl` records CLI invocations after command logging was added; earliest commands below predate that logger. HTTP status 200 is not proof of content validity.
- Successful requests are reused by URL and SHA256 on reruns. This preserves the original retrieval time; a rerun is **not** a freshness test. Failed attempts are retained. No automated retry, spoofed browser session, proxy, CAPTCHA, authentication, or access-control bypass is used.
- `documents.jsonl` records discovery lineage and the download selected. `*-links.json` contains discovered candidates; filename heuristics are imperfect. Old reports, invitations, press conferences and cover letters must not be called latest annual reports or full earnings transcripts merely because selection matched.
- `*.pages.json` is the initial layout-sorted extraction where generated. `*.text.json` is the improved unsorted extraction. Initial sorted extraction made some scanned/OCR-overlay tables excessively spaced. Keeping both preserves that evidence. `document-inventory.json` reports nonblank text-page coverage, **not** semantic accuracy. PDF parsing/rendering is of source copies; no source PDF was edited.

## Exact principal commands from workspace root

```powershell
# Initial Yahoo attempt in the restricted sandbox failed DNS; same command with network access succeeded.
python .\experiments\data_probe.py prices --tickers INFY
python .\experiments\data_probe.py prices --tickers INFY KPRMILL CERA
python .\experiments\data_probe.py exchange --tickers INFY KPRMILL CERA
python .\experiments\data_probe.py discovery --tickers INFY KPRMILL CERA
```

The first configuration used `https://kprmilllimited.com/investors/` (404) and Cera's top-level IR page (insufficient links). Current config contains the corrected, publicly discovered KPR financial/call pages and Cera's financial/events/AGM child pages. No successful request needs repeating to inspect the saved evidence.

```powershell
python .\experiments\data_probe.py discovery --tickers KPRMILL CERA APOLLOHOSP
python .\experiments\data_probe.py documents --tickers INFY KPRMILL CERA --kind filing
python .\experiments\data_probe.py documents --tickers INFY KPRMILL CERA --kind annual
python .\experiments\data_probe.py documents --tickers INFY KPRMILL CERA --kind transcript
python .\experiments\data_probe.py prices --tickers APOLLOHOSP
python .\experiments\data_probe.py exchange --tickers APOLLOHOSP
python .\experiments\data_probe.py exchange --tickers APOLLOHOSP --start 01-07-2026 --end 30-09-2026
python .\experiments\data_probe.py annual-index --tickers INFY KPRMILL CERA APOLLOHOSP
python .\experiments\data_probe.py documents --tickers KPRMILL APOLLOHOSP --kind annual
python .\experiments\data_probe.py documents --tickers APOLLOHOSP --kind annual --offset 1
python .\experiments\data_probe.py documents --tickers APOLLOHOSP --kind transcript
python .\experiments\data_probe.py resolve --file '.\experiments\samples\APOLLOHOSP-transcript-0-20261030T075051735128Z.pdf'
python .\experiments\data_probe.py documents --tickers CERA --kind transcript --limit 4
python .\experiments\data_probe.py eod-official --tickers INFY KPRMILL CERA APOLLOHOSP --asof 2026-10-29
python .\experiments\inspect_samples.py
python .\experiments\validate_samples.py
```

One-off probes whose URLs/response hashes remain in requests.jsonl:

```powershell
python .\experiments\data_probe.py fetch --url 'https://www.nseindia.com/api/annual-reports?index=equities&symbol=APOLLOHOSP' --label APOLLOHOSP-nse-annual-index
python .\experiments\data_probe.py fetch --url 'https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_29102026.csv' --label NSE-EOD-2026-10-29
python .\experiments\data_probe.py documents --tickers CERA --kind annual
```

The last command was run after URL decoding was fixed and before NSE-index candidates were prepended: it downloaded Cera's current FY2026 issuer report instead of the older filename match. Later command results can differ as candidate inventories evolve. Exact selected URLs and document lineage are authoritative in the manifests.

## Extraction and verification

To re-extract a downloaded PDF with no HTTP request:

```powershell
python .\experiments\data_probe.py extract --file '.\experiments\samples\KPRMILL-filing-0-20261030T074523691154Z.pdf'
```

Extraction caches are retained. `inspect_samples.py` renders KPR PDF pages 3/9 and attempts ruled/text table detection, preserving word boxes and cell output. Default detection found zero tables; text detection produced split cells. The report's manually checked values are **not** an automated successful table-parser benchmark.

For Cera annual/report visual checks, the offline inspection used `pymupdf.open(path)[page_number-1].get_pixmap(matrix=pymupdf.Matrix(1.3,1.3)).save(output_path)` on annual PDF pages 52/148 and transcript PDF pages 4/5; resulting PNGs are in samples. PDF and printed page numbers differ in the annual report. Text files preserve exact PDF-page boundaries.

APOLLOHOSP revised FY2026 annual PDF is malformed/partial (14 text-bearing pages out of a reported 278). It is **rejected**. The original FY2026 submission yields 298/301 text-bearing pages; it is a separately identified fallback, not proof the revised content was recovered. The downloaded transcript is only a cover letter; its referenced full transcript returned 403 locally. A web lookup could read that 18-page transcript, but is not a backend pipeline success.

## Deployment boundary

These are local server-side network experiments with tool-level outbound-network permission. No target hosting environment, CORS flow, scheduled refresh, sustained rate-limit behavior, reuse licence, OCR service, or production service level has been verified. Do not copy these source calls into a browser client and assume they work. Do not depend on an assistant web-search tool as the app's data provider.
