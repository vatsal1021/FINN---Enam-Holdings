# Decisions and delivery plan

Updated 2026-10-31 (Asia/Kolkata). Deadline November 1, 2026; cutoff unspecified. Real push, generic retrieval and fixed Gemini answers are implemented and hosted on Render Free. Actual source refresh, recovery and cited generation/cache verification passed. Physical-phone testing, separate history-sharing permission/links and manual submission remain pending in release.md. Earlier stack/model/access proposals below are historical and superseded by current release evidence.

## Decision log

**D-021 · Implemented Gemini stage / scope frozen:** fixed `gemini-3.5-flash-lite`, server-only `GEMINI_API_KEY`, no tools/outside company evidence, paid fallback or provider-error retry. Six retrieved source pages get bounded context to avoid chopped qualifications. Validate source identity/hash/page, exact quote/IDs, figures, units and periods; allow one paced validation correction, otherwise retain passage-only access. Cache includes question/history, prompt/model and source versions. Four concise claims allow complete segment lists. Limits: lexical recall and semantic entailment remain imperfect; source review caught omitted segments and an incorrect audit assumption. The ten final outputs reuse seven earlier results, with only material failures rerun. Authorised public repository and Render Free deployment now proceed; optional features/research are frozen.

Competitor-research closeout, October 31: the five-product sample is sufficient for this assignment. The official-page/demo revalidation in research.md R-028 adds no feature obligation or known private architecture. No further generic market survey is planned before November 1; investigate only concrete source or implementation blockers. Product recommendations remain our choices, with attention-to-evidence usability as the focused opportunity.

| ID | Status | Decision and reason | Evidence / trade-off | Revisit when |
| --- | --- | --- | --- | --- |
| D-001 | Completed-stage boundary; lifted for preview | The initial no-code instruction applied to research/planning. The user explicitly authorised a small local interactive preview on October 30. | Latest implementation request; no paid hosting/API use authorised by this preview request | Full integration remains a separate next stage |
| D-002 | Agreed working direction | Understand problem, research products and user feedback, verify sources, decide scope, then build and test. | User's proposed sequence; primary data/generalisation constraints in M pp. 2-3 | Research or source checks expose a blocker |
| D-003 | Proposed | Build two narrow workflows: proactive portfolio triage and on-demand company investigation with inspectable primary evidence. | M pp. 1-4; meets both modes while limiting breadth | After bounded research |
| D-004 | Proposed | Start with 15 portfolio companies and 3 ad-hoc research demos, including an outside-portfolio case. | M pp. 1-2; lower end of required portfolio size preserves time | Representative source coverage verified |
| D-005 | Proposed | Prefer responsive web for easy phone access and fewer distribution steps. Framework/hosting/model remain undecided. | M p. 4 allows responsive web; speed is our rationale | Existing skills, deployment feasibility, and source runtime requirements are checked |
| D-006 | Working practice | Preserve real AI conversation history from now; maintain these four notes as the concise project record. | AI build history is a submission deliverable (M p. 4) | Confirm export/share mechanism before final packaging |
| D-007 | Proposed | Aim for a working deployed version by October 31 evening; reserve November 1 for fixes/access checks/submission. | Deadline cutoff unspecified; M p. 4 prioritises a running demo | Actual hours available become clear |
| D-008 | Research complete; implication proposed | Stop competitor expansion after five products. Differentiate through a concise portfolio-change-to-evidence journey, not the mere presence of AI summaries, citations, or filters. | research.md R-001 through R-005 and R-011: existing products already offer these components | Real source feasibility and a later usability check |
| D-009 | Proposed engineering principle | Separate document extraction, deterministic numeric calculations, and prose explanation; preserve provenance and show unavailable/ambiguous evidence. | R-006 and historical failure-mode feedback R-008/R-009; vendor workflow descriptions are attributed, not copied as known private architectures | Source verification determines the simplest adequate implementation |
| D-010 | Feedback pass complete; proposals remain open | Close feedback collection after a bounded 48-entry working sample. Prioritise reading/list reliability, concise synthesis, and honest coverage; do not claim universal AI distrust or a proven missing-citation gap. | research.md R-013 to R-017 and sample/access ledger; no product defect reproduced | Data experiments and later phone/task checks |
| D-011 | Proposed | Keep brokerage sync, payment flows and multiple alert channels outside this prototype despite requests in commercial-product reviews. Test digest-to-source navigation and return position with the full portfolio size. | Relevant/peripheral feedback distinction; mock portfolio and thin working prototype in assignment | Core retrieval works and remaining time permits read-state refinement |
| D-012 | Local feasibility established; provider choice proposed | Use completed-session EOD data, with official NSE daily file a practical candidate and explicit source/date/missing-value handling. Prefer ticker-based NSE announcement/annual metadata plus issuer indexes. Do not infer cloud reliability or reuse rights from successful local requests. | R-018/R-019; V-011 to V-015 and V-040 to V-042 | Small actual-runtime retrieval check and full portfolio selection |
| D-013 | Recommended scope reduction, not yet implemented | Core pull: concise business/management investigation from available annual report + actual call text, a few checked figures and visible coverage. Keep full four-quarter promise-versus-delivery optional. Cera is a viable manually checked analytical example; recent KPR calls and Apollo full-call ingestion unresolved. | R-020/R-021; explicit extraction and chronology failures in verification.md | If additional verified evidence and time make deeper comparison inexpensive |
| D-014 | Superseded stack/budget proposal | The earlier FastAPI/Jinja/persistent-volume/Railway/paid-model proposal is no longer the implementation or approved budget. | D-017 and the explicit free-only user update supersede it | Do not provision paid infrastructure or model usage |
| D-015 | Bounded competitor recheck complete; design remains proposed | Keep the same five-product sample. Prioritise understandable event importance and passage-level evidence with a reliable return journey. Do not spend the remaining deadline window recreating brokerage integration, trading tools or enterprise research infrastructure. | Official-page and six-visual recheck; research.md comparison summary; V-048 to V-050 and V-069. Later 390 x 844 Screener public-web inspection adds actual interface evidence; its Important filter requires login. Indian DVM methodology is publicly readable. Sources/filtering already exist commercially; our usability opportunity is unproven. | Source/runtime checks or actual mobile task testing reveal a concrete need; no further generic market survey |
| D-016 | Implemented for local preview only | Use buildless HTML/CSS/JS with a Python standard-library loopback server to inspect Digest, all 15 Companies, Investigate and Evidence before integration. Prepare dated local samples offline; summaries/priorities are manually authored and labelled. | User explicitly permits a simpler local HTML preview. No framework install or credential dependency. This is not an alternative production-architecture comparison or proof of live AI/generalisation. | Actual preview feedback; then return to the existing integrated-product plan |
| D-017 | Implemented local push; free deployment prepared | Extend the existing screens with Python HTTP routes, SQLite, real NSE adapters and PyMuPDF. All 15 EOD/feed checks passed for the recorded window, 61 filings stored. Use temporary cache + dated recovery snapshot/request-triggered refresh on Render Free; no paid disk/cron/model calls. | User lifted preview-only boundary, imposed free tiers and asked cloud setup not to block local work. V-063 onward records full-data checks and limits. | Render account/repository access; actual hosted retrieval; next pull slice |
| D-018 | Implemented validation/rule correction | Require full declared response length, EOF marker and structural checks; allow PDFs up to 25 MB. Preserve the actual incomplete Sun Pharma response; new complete 34-page download validates. Scheduled capital/board notices no longer receive a delivered-results title (`push-v2`). | Actual full-portfolio/browser inspection and regression tests; old failure retained rather than rewritten | Larger/unreadable files get explicit failures; ranking quality still needs broader audit |
| D-019 | Implemented extractive pull | Use generic NSE equities-list identity, annual metadata and bounded announcement history before issuer-index fallbacks. Index full usable reports and actual-call sections with original source/hash/physical page. | R-027; INFY/CERA/TITAN and two symbols chosen after adapter implementation. Four have both source types; ITC/Apollo stay partial. A quoted endpoint 403 is not bypassed. | Broader source coverage exposes a concrete adapter gap; do not treat missing discovery as proof of absence |
| D-020 | Implemented retrieval without synthesis | Use SQLite FTS and document-local lexical ranking, balanced AR/call passages. No model request, source-based manual answer or copied demo brief. Keep period/basis/unit uncertainty visible. | Actual snapshot testing caught ticker-key restoration and corpus-dependent ranking; both corrected. Citation IDs/text survive derived-index rebuilding. Lexical search has limited paraphrase recall and does not reconcile contradictions. | Separate free-model stage; no key or credit decision blocks completed retrieval |

Proposals are not settled requirements. Explain significant decisions using: problem, evidence, alternatives, chosen trade-off, and how we will verify it. Record the reason before implementation makes a choice expensive to change.

## Local interactive preview delivered October 30

Run/open: `python .\preview\serve.py --port 8765` from the workspace root, then **http://127.0.0.1:8765**. The server was left running for user inspection. It binds to this computer only; a physical phone cannot use its own localhost to reach it. The confirmed browser test viewport was **390×844 CSS pixels**.

Files: `preview/dist/index.html`, `style.css`, `app.js`, `source.html`, `source.js`, generated `data.json`; `prepare_samples.py`, explicit `document_routes.json`, `serve.py`, `check_preview.py`, README and evidence screenshots/results. No third-party app dependencies, paid account, model request or upstream refresh was introduced.

Implemented: eight selected real filing examples, two manually prioritised; the fifteen previously selected companies; four dated official EOD samples; business/management saved views for INFY/CERA, limited KPR/APOLLO cases and eleven not-loaded cases. The drawer offers original passages, company/document/period/page, saved source-page reader, saved full PDFs and original-source links. Native Back/Escape/close, tab focus wrap, filter/search/sort state and reading-position return were checked. Original links open a separate tab to preserve context. KPR original NSE PDF actually opened in the browser.

Preview state examples: replay loading (explicit simulation); empty 30 October saved window; routine-only and metadata-only filings; KPR August 2023 call explicitly stale; Apollo cover letter/full-call-403 explicitly partial. None produces invented live content.

Verification: **42/42** local HTTP/content/source-identity checks; browser action record in `preview/browser-results.json`; screenshots in `preview/screenshots/`; precise scope/limits in verification.md V-051 onward. A keyboard wrap issue found during inspection was fixed and retested. No real-phone task study, full platform acceptance or arbitrary-ticker research is claimed. Do not mark the recruitment checklist complete from this preview.

## Recommended product and technical plan

### Current budget and implementation override · October 30

**Free tiers only.** The paid Railway plan, earlier $10 hosting / $5 API allowance and paid-model recommendation below are superseded, not approved. The user reports an OpenAI key is available for secure setup later; credits are unconfirmed. No model call is enabled or needed for this push slice. No secrets are requested in chat.

Current implementation extends the preview's HTML/CSS/JS with Python standard-library HTTP routes, SQLite and the existing PyMuPDF extraction approach. This avoids a frontend rewrite or unnecessary framework installation. `app/adapters.py` refactors the working NSE request/CSV/announcement logic without the experiments' cache; every refresh issues actual requests. Files/requests carry original URL, UTC retrieval time, status, bytes/hash and validation outcome. Financial tables are not automatically summarised; EOD arithmetic is deterministic.

**Free deployment route: Render Free Python Web Service**, with `render.yaml` and `.python-version` prepared. Local SQLite persists on this computer. On the free host, SQLite/PDF files are temporary: cold startup can restore an explicitly dated, automatically exported full-refresh snapshot, then request-triggered catch-up rebuilds sources. No scheduled refresh while sleeping is promised, no keep-alive service is added, and no persistent volume/paid cron is provisioned. Snapshot restores preserve original retrieval times and omit raw PDF bytes; missing cached PDFs can be fetched again or opened at the original source.

Exact setup pending: sign in to a Render account; provide a Git repository the service can read (or create/connect one in the coordinating chat); create the service with **Free** compute and verify included usage/spend settings without adding a payment method or paid add-ons. The dashboard opened at `/login`; no Render API credentials or authenticated dashboard access were available. Therefore cloud creation and the **actual hosted NSE retrieval check remain pending**. Neither local success nor the prepared YAML proves cloud network access. Continue local work independently.

Refresh architecture: one bounded job/SQLite lease, per-company outcomes, metadata upserts, immutable response hashes; manual selected-company/all-15 refresh and stale-on-request catch-up. Global request limits are prototype safeguards and reset with an ephemeral runtime. No assumption of durable cloud job history, always-on scheduling or complete exchange-feed reconciliation.

Planning revision: October 30, 2026. Requirements are in requirements.md; supporting observations are research.md R-001 through R-021 and verification.md V-011 through V-043. Recommendations below are concrete proposals, not implemented features or additional assignment requirements. No application scaffold, deployment, subscription or model call was created in this planning stage.

### Two focused directions

| Direction | Investor value | Reliability and deadline trade-off |
| --- | --- | --- |
| A. Portfolio attention digest -> evidence -> company investigation | Quickly find consequential developments, then investigate without restarting elsewhere. Meaningful push and pull share company/document context. | Reuses verified EOD/NSE routes. Useful even with partial document coverage. Main risk is event prioritisation quality; expose its reason and keep routine items accessible. |
| B. Company research notebook with an updates inbox | Stronger deep-reading experience and reusable company questions; push becomes a supporting inbox. | More dependent on current transcripts and robust retrieval before it feels useful. Tempts us toward a broad chat/report generator, while Apollo blocked calls and KPR old calls weaken coverage. |

**Recommend A.** It matches the attention problem (M pp. 1-2), the thin-working-product preference (M pp. 3-4), and feedback about readable monitoring and mobile controls (R-013 to R-017). Competitors already have summaries, filters and source links; our hypothesis is that this connected path can be executed particularly clearly, not that it is a proven market gap. Evidence links are also an assignment/factuality discipline, not established universal user demand.

### Mobile experience and core scope

**First screen: Today / selected period.** Default last 24 hours, optional 7 days and custom dates in IST. Show last successful filing refresh, EOD trading date, and coverage such as 14/15 companies checked; do not hide a failed fetch inside an empty digest. If no filings occurred, say so and offer another period. If a dated demonstration window is used, label the exact dates; do not present it as today's feed.

Then show a compact attention section ordered by materiality tier and timestamp. Each event contains company/ticker, event type and exchange time, one-sentence change, one concrete reason to review it, and Evidence / Investigate actions. Routine records remain under an expandable section with a count; unknown categories remain visible, not silently buried. Initial priority uses transparent rules: results, substantive management changes, acquisitions/fundraising or regulatory concerns generally merit review; meeting notices and routine compliance generally rank lower. Type alone never proves financial materiality. LLM labels are suggestions with uncertainty; rules provide conservative defaults.

**EOD section:** all 15 companies have a dated row/card with close (INR/share), day move, traded volume (shares), provider and missing-data status. Sort alphabetically/by move. Compute move from official close and previous close; do not use turnover or delivery quantity as volume. No fabricated value when missing. An optional unusual-volume ratio requires 20 valid preceding sessions excluding the current session; omit with explanation if that history is incomplete. It is not a core launch dependency. Price movement and a nearby filing are not automatically cause and effect.

**Next action: Investigate this company**, from an event, an EOD row or ticker search. Default question: "What does this business do, what is management saying now, and what evidence or risks should I check?" Produce a concise brief: business/segments from the annual report; latest available call commentary with its date; 2-3 grounded observations or open questions, and a few verified financial facts only where available. A company without a current call gets a clearly partial brief, not invented management commentary. Offer two focused follow-ups (e.g. cash conversion, management outlook/risks) plus a bounded text question. No eight-section generated report by default.

**Evidence interaction:** numbered references open a bottom sheet containing a short original passage, source title/type, company, fiscal period, PDF page, accounting basis where relevant, and original-document link. The whole source inventory is one tap away. Return restores company, filters and scroll position. On phones, extracted passages are the primary reading aid; the original PDF remains accessible. Opening a PDF at a page may vary by browser, so never rely on that fragment alone. Keep first brief at <=250 words excluding evidence. Report contradictions instead of smoothing them away.

Bottom navigation: Digest, Companies, Investigate. A company page can show its EOD row, recent filings and document coverage, not a second analytics dashboard. Read/unread state and preferences are local to the reviewer's browser; no account system. Preserve state across page navigation; allow reset of mock data/preferences. Important controls should remain available without horizontal page scrolling.

### Proposed portfolio and research demos

These are research-design choices, not investment recommendations. Size labels are rough diversity intentions, not verified October 30 market-cap ranks. All 15 need a coverage pass in the actual runtime; no claim of current transcripts for the untested 11.

| NSE ticker | Company / sector | Selection reason / intended scale | Evidence already tested |
| --- | --- | --- | --- |
| INFY | Infosys / IT services | Large global services business, clear reporting | EOD, metadata, current annual report and actual Q2 FY27 call bundle locally verified |
| RELIANCE | Reliance Industries / diversified energy-retail-digital | Large multi-segment business | Not tested |
| HDFCBANK | HDFC Bank / banking | Large financial-sector contrast; no generic EBITDA assumption | Not tested |
| BHARTIARTL | Bharti Airtel / telecom | Capital-intensive recurring-services business | Not tested |
| LT | Larsen & Toubro / engineering and construction | Orders/project execution context | Not tested |
| MARUTI | Maruti Suzuki / automobiles | Manufacturing, volumes and demand | Not tested |
| SUNPHARMA | Sun Pharmaceutical / pharmaceuticals | Regulatory and product-development context | Not tested |
| HINDUNILVR | Hindustan Unilever / consumer staples | Consumer demand, mix and margin context | Not tested |
| NTPC | NTPC / power generation | Utility/capacity and capex context | Not tested |
| TATASTEEL | Tata Steel / metals | Cyclical commodity/multi-geography context | Not tested |
| APOLLOHOSP | Apollo Hospitals / healthcare | Healthcare and useful partial-coverage case | EOD/metadata, original annual report work; revised PDF rejected, full call local 403 |
| KPRMILL | KPR Mill / textiles | Different business scale; integrated textile/sugar exposure | EOD/metadata/current AR/results work; downloaded call is old, Q1 FY24 |
| CERA | Cera Sanitaryware / building products | Smaller business and document-backed analytical example | EOD via NSE fallback; AR, four recent call transcripts and tables checked |
| PERSISTENT | Persistent Systems / IT services | Mid-sized IT contrast to Infosys | Not tested |
| ELGIEQUIP | Elgi Equipments / industrial equipment | Smaller export-oriented manufacturing contrast | Not tested |

Three proposed research demos: **INFY** (current complete source-backed journey), **CERA** (business/current commentary; optional checked revenue-guidance example), **TITAN** (outside portfolio, discovery/generalisation demo). TITAN is not yet tested and must earn its demo slot through real source checks; a coverage failure must be disclosed, not concealed by prepared text. Apollo/KPR are additional failure-state checks, not advertised as fully covered research demos. No portfolio weights, purchase prices or broker imports are needed; this mock portfolio is a set of holdings to monitor.

### Document state must affect both UI and retrieval

Track access, extraction, period and version separately; multiple states can coexist.

| State | Investor-facing behavior / research rule |
| --- | --- |
| Missing | "No transcript found in the checked sources as of [time]"; list routes checked. Not "the company has no calls." |
| Older/stale | Show call quarter/date prominently; warn when older than a newer known reporting period or a configurable age threshold (initially 120 days). Older text may explain history, never current management guidance. |
| Blocked | Preserve HTTP 403 and attempt time; no repeated automated evasion. Offer original link and a partial brief from accessible sources. Web-tool lookup is not ingestion. |
| Cover letter / notice | Show as announcement and follow its published document reference normally. Require actual call body/participants before classifying it as an ingested transcript. |
| Malformed / image-only | Quarantine from model context; report extraction failure or OCR needed. No blank output disguised as successful research. |
| Superseded | Preserve version/hash/provenance but exclude old version from default current retrieval when a usable replacement exists. |
| Revised version unusable | Keep warning that newer changes are unverified; original report can be a labeled fallback for historical description, not represented as recovered revised/current facts. |

Examples to retain as regression evidence: CERA Yahoo null, KPR bad IR path and stale call, INFY separate press conference versus actual call, Apollo cover letter/403 and malformed revision. Do not silently fix Cera's apparent comparative-year typo or combine revenue presentations across periods. Failed table detection means no universal automatic table standardisation promise.

### Current architecture and next pull boundary

**Implemented:** one Python standard-library HTTP service reusing the existing HTML/CSS/JS screens, SQLite WAL with short transactions and a single refresh lease, content-addressed raw responses, PyMuPDF, and one process-wide PDF lock. No React rewrite, Redis, paid volume, scheduler, model SDK or provider request was added. The local tested runtime is Python 3.14.2; the prepared Render minor pin is 3.13 and still needs actual-runtime verification.

**Fetch and provenance:** fresh ordinary NSE requests, per-company outcomes, bounded windows/pacing/timeouts, byte caps, host/redirect allowlist, source UTC timestamps/HTTP status/length/SHA-256 and validation results. Financial-table meaning is not inferred from successful text extraction. PDF download limit is 25 MB; declared size and EOF/structure are checked. Actual failed bytes remain preserved. No retry of a block, cookie trick or arbitrary URL fetch is implemented.

**Storage and refresh:** local SQLite/raw files persist across restarts. Free-host files are temporary; the generated complete-data recovery snapshot retains original timestamps/text and omits PDF bytes. Request-driven stale catch-up runs only while the service is handling traffic; no scheduled work during sleep is promised. Manual refresh accepts selected/all configured holdings and bounded dates. The finishing local server uses `--no-auto-refresh` so opening it does not repeat the already successful portfolio fetch; the explicit Refresh button still performs real requests.

**Presentation:** generic `push-v2` metadata rules, every routine/unknown filing recoverable, 15-company EOD/source coverage, real extracted passage and original file/source routes. Price/previous-close arithmetic uses Decimal. Scheduled decisions are distinct from delivered results. AI investigation is visibly unavailable; demonstration briefs are in a separate dated mode.

**Next pull slice, not yet implemented:** annual-report and actual-transcript discovery for arbitrary available NSE symbols; correct identity/period/version checks; page chunks and bounded lexical retrieval, then cited extractive research. Investigate one genuinely free supported model route separately before enabling synthesis. Preserve source-only grounding, no model arithmetic/outside company knowledge, correct citation IDs/pages and ten factuality cases. Add a process boundary or embeddings only if measured need justifies it. No claim that FTS, an embedding model or free model quota has already been tested.

### Discovery for an unfamiliar NSE ticker

1. Normalise/validate symbol against the official NSE symbol list when ingested; company name is resolved from authoritative metadata. Keep BSE code/ISIN mappings separately; do not guess from arbitrary search results.
2. Run the generic NSE annual-report index by symbol; select eligible latest fiscal year and submission/version, fetch and validate content. This route already worked on the additional APOLLOHOSP ticker.
3. Search ticker-specific NSE announcement windows for call/transcript entries, in bounded 90-day windows (up to four initially). Distinguish actual call body from call invitation, recording, press conference, and cover letter. Follow published PDF references with the same access policy.
4. Try configured company IR **index routes** if the exchange route has incomplete documents. Existing INFY/KPR/CERA index routes are examples, not a fixed PDF dataset. Adding an issuer adapter must improve index parsing/discovery, not insert a company-specific answer.
5. If generic sources fail for an unconfigured issuer, show the checked routes and partial/unavailable coverage. There is currently no verified automatic issuer-site discovery/search API integration. Do not claim arbitrary ticker full-call coverage is solved.

**Test:** after adapters are frozen, select two valid NSE symbols outside the 15 holdings and 3 named demos, with no IR config/PDF URLs prepared. One must discover/download AR + actual transcript through generic routes; both must preserve correct company/period and honest failure behavior. If no available-source case passes, generalisation is a launch blocker: improve generic retrieval or disclose the unresolved requirement, rather than replacing it with canned demos. TITAN is a useful outside-portfolio demo but is not an independently unprepared final test. Also run an invalid symbol and Apollo's known partial case.

### Model and hosting choice

**Free tiers only.** Render Free is the prepared route; login/repository access and an actual hosted NSE check are pending. Its temporary-storage/request-triggered design is described above and in app/README.md. No paid Railway plan, disk, cron or API budget is approved.

**Models remain disabled.** The user is uncertain about OpenAI credits; do not ask the same question again, infer free use from an API key, or make a chargeable call. The next pull stage will investigate a genuinely free supported route. Source discovery/extraction/retrieval can proceed independently.

### Remaining implementation plan

Deadline Nov 1 has no supplied cutoff/timezone. Keep October 31 evening as the target for a usable reviewer deployment and preserve November 1 for access checks/submission. Estimates below are focused work budgets, not assumptions about user availability.

| Order | Budget / status | Deliverable / stop condition |
| --- | --- | --- |
| 1 | Complete locally | Real EOD/announcements for all fifteen, deterministic priorities, filing validation and mobile evidence return. Dataset and checks recorded in verification.md. |
| 2 | 30–45 min when access exists, parallel to local work | Connect repo to Render **Free**, deploy prepared service, test actual hosted NSE retrieval, sleep/restart recovery and timestamps. If blocked, report exact runtime outcome; no paid workaround or challenge bypass. |
| 3 | Complete locally for the tested slice | Generic AR + actual-call discovery, full page indexing and cited retrieval. Three requested cases + two unprepared symbols tested; ITC/Apollo partial limitations retained. See R-027 and V-070 onward. No synthesis/canned answers. |
| 4 | 45–60 min bounded route check, then 1–2 h if feasible | Establish a genuinely free supported model path before any synthesis call; add one provider and ten grounded factuality cases. If unavailable, retain explicit unavailable state and disclose the remaining analytical limitation. |
| 5 | 1–1.5 h | Actual phone and additional viewport checks, fresh-ticker/failure tests, source/number audits, hosted cold-start latency and memory measurement. Fix core failures only. |
| 6 | 1–1.5 h + submission buffer | Clean-checkout startup, reviewer access to prototype/repo/actual AI history, covering email with decisions/omissions/limits. No email send without user instruction. |

Optional CERA guidance example remains deferred until core push/pull and submission checks pass. No universal four-quarter promise-versus-delivery claim is made.

### Deliberate omissions and scale path

Leave out universal four-quarter comparison, broad automatic financial table normalisation, native apps, voice, intraday feeds, brokerage sync/trades, buy/sell targets, social/news analysis, biographies, all eight pull sections, OS/WhatsApp/email alerts, multi-user accounts, and large agent orchestration. These are scope choices, not assignment prohibitions. In-app proactive updates are our interpretation of push (requirements.md ambiguity); make cadence obvious.

At larger scale: move PDF blobs to object storage and SQLite to Postgres; split ingestion/extraction into durable queued workers; add multi-user entitlements and robust operations. Add embeddings if measured retrieval needs them; add licensed feeds/OCR only after need/rights/cost are established. This is a future path, not additional infrastructure for the prototype.

### Setup still needed

Render sign-in and a Git repository connection/visibility choice are needed for deployment. The dashboard reached `/login`; no host account or service was created. Local commits exist, but nothing has been pushed or published. Configure secrets through a secure mechanism if/when a genuinely free model route needs them; never paste keys into chat. No additional credit question or paid-budget confirmation is needed to finish the independent push work.

## Submission preparation later

Use the exact recipient and subject in requirements.md. The covering email should briefly state what works, how to try it, the important choices/trade-offs, deliberate omissions/known limits, and next steps. Include prototype, repository, and actual AI build-history access. Verify links from a reviewer-like session. Do not send an email merely because the assignment specifies the recipient; sending requires the user's instruction.
