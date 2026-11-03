# FINN assignment requirements

Reviewed on 2026-10-31 (Asia/Kolkata). Real push, generic retrieval and source-grounded Gemini answers are implemented. Public Render Free deployment, actual 15-company refresh, hosted pull, redeployment recovery and a real cited answer/cache check passed; fresh TCS discovery is honestly partial. Ten local answer outputs were reviewed with selective reruns/failures retained. Physical-phone testing, separately authorised actual history links and manual submission remain pending in release.md. The dated manual preview stays separate.

Sources: **M** = `1. ENAM_AI_Engineer_Build_Challenge_Main.pdf` (4 pages); **R** = `2. ENAM_AI_Engineer_Build_Challenge_Reference.pdf` (3 pages). Page references below are PDF page numbers; M also prints matching page numbers. Both documents were read completely and every page visually inspected.

## Short requirements checklist

Checked means completed and verified, not merely planned. These are assignment obligations; our additional engineering checks belong in verification.md.

- [ ] Mobile-first, interactive working prototype, easy to try on a phone. (M pp. 1, 3-4)
- [ ] Both proactive push and on-demand pull modes. Exact feature selection remains open. (M p. 1; examples on pp. 2-3)
- [ ] Mock portfolio of 15-20 NSE/BSE-listed companies, plus a handful of ad-hoc research demo companies. "Say 3-5" is guidance; being outside the portfolio is allowed, not required. (M p. 1)
- [ ] Research engine handles any NSE ticker where data is available; no hard-wiring to demo companies. (M p. 2)
- [ ] Working data paths for portfolio EOD price and volume, NSE/BSE announcements/filings, and company annual reports AND earnings-call transcripts. (M p. 2)
- [ ] Pull research grounded in primary sources, especially annual reports and transcripts; no news, broker notes, research reports, or model outside company knowledge. (M p. 3; R p. 2)
- [ ] Submit phone-accessible prototype, GitHub repository, actual AI build conversations, and short covering-email writeup. (M p. 4)
- [ ] Email links/attachments to `assessment@enam.com`, subject exactly `ENAM - IIT screening - 2027`, by November 1, 2026. Cutoff time/timezone unspecified. (M pp. 1, 4)

## What they are evaluating

Explicit: building ability, creativity, product instinct/sense, judgment, architecture, and how we use AI tools. They evaluate what we choose to build as well as how we build it. Efficiency earns bonus points. A small working product beats a broad broken demo. (M pp. 1, 3-4)

The investor's problem is attention, not lack of information: identify consequential changes, explain why they matter, and keep routine material out of the way. The frontend and interaction model are the central canvas; backend data plumbing should work without over-engineering. Concise, interactive presentation and thoughtful information density count, even though completeness and polish are not the main grading goals. (M pp. 1-3)

Interpretation, not an additional requirement: a good demonstration should show an investor going from "what needs my attention?" to "what primary evidence supports this?" quickly. Evidence of analysis beyond generic summaries is valuable; the four-quarter promise-versus-delivery example is an especially strong signal of their interests, but remains optional. (M p. 3)

No scoring weights, minimum number of implemented menu items, uptime target, or performance benchmark are supplied.

## Optional suggestions and freedoms

- Portfolio sector/size diversity is recommended for an interesting demo. Exact companies are ours to choose. (M p. 1)
- Yahoo Finance/yfinance is a suggested EOD starting point; equivalent sources are allowed. Screener links or company investor-relations sites are suggested for annual reports/transcripts. Their actual accessibility is not yet verified. (M p. 2)
- The reference's 17-category taxonomy is explicitly optional: use, adapt, or ignore it. Its definitions are orientation, not mandatory classification logic. (M p. 2; R p. 1)
- Frontend ideas are expressly "illustrations, not a checklist": a configurable-window digest, triggered alerts with configurable thresholds, management-background enrichment, and quarterly Revenue/EBITDA/PBT/PAT comparisons QoQ/YoY. The ~2x volume threshold is an example, not a fixed rule. If we choose these features, document which example behavior we implement. (M p. 2)
- Pull menu: business snapshot, financial snapshot, trajectory, balance sheet, cash quality, narrative versus numbers, guidance, bull versus bear. No obligation to implement all eight. The four-quarter comparison is a worked example, not a separate compulsory deliverable. (M pp. 2-3)
- Chat, voice, copilot, dashboard, or another interaction model are permitted; experimentation is encouraged. No requirement to implement multiple interaction types. (M p. 3)
- Models may be open-source, local, or commercial. Free tiers are described as sufficient, not mandatory; there is no stated spending cap. Routing, caching, and chunking are suggested efficiency techniques, not prescribed architecture. (M p. 3)
- Shipping format is flexible: deployed link, Expo/TestFlight, or responsive web, provided the reviewer can easily try it on a phone. (M p. 4)

## Restrictions and boundaries

- Primary-source-only pull analysis. Secondary company commentary and pretrained company knowledge must not become research evidence. Push-side professional-background enrichment is expressly allowed. (M p. 3; R p. 2)
- Do not hard-wire research to a prepared demo set. The evaluator may try an unselected company. (M p. 2)
- Keep the product mobile-first and working. A static mockup alone does not meet the stated deliverable. (M pp. 1, 3-4)
- No mandated language, framework, cloud, model vendor, native app, trading integration, intraday price feed, voice feature, or compulsory finance expertise appears in either document.

## Submission deliverables

1. Working mobile-first prototype with a phone-friendly way to try it. (M p. 4)
2. GitHub repository. Visibility is unspecified; reviewer access must be resolved. (M p. 4)
3. Coding-agent and LLM conversations actually used during the build, via exports/share links. Project notes are useful context but do not replace actual conversations. Preserve history from this planning session onward. (M p. 4)
4. Short writeup in the covering email: what we built, key decisions/trade-offs, deliberate omissions, and next steps. No word count or separate report format specified. (M p. 4)
5. Submit the links/attachments by email to the address and exact subject in the checklist. November 1, 2026 is printed as Sunday. No hour/timezone is provided. (M pp. 1, 4)

## Ambiguities to keep visible

| Question | What the documents actually say | Working position, not a requirement |
| --- | --- | --- |
| Exact deadline cutoff | November 1, 2026 only. (M p. 1) | Aim to finish on October 31; use November 1 for final checks/submission. Do not assume 23:59 IST is authorized. |
| Are both modes required, and both push flavours? | Two modes are part of the product definition; frontend details are examples. (M pp. 1-3) | Include push and pull. A digest alone can be our push workflow; triggered alerts are a scope choice, with some interpretive uncertainty. |
| Meaning of proactive push | Tells the investor what changed without being asked; no transport specified. (M pp. 1-2) | A proactively populated in-app view is defensible. OS notifications, email, and background delivery are not explicitly required. |
| Data freshness, coverage, and history | EOD data, filings for the portfolio, annual reports/transcripts; no minimum history or refresh SLA. The all-filings/time-window language is within an illustrative digest. (M p. 2) | Choose and disclose dates, coverage, refresh cadence, and failures. Do not label partial coverage complete or imply intraday prices. |
| Generalisation expectations | Any NSE ticker "where the data is available." (M p. 2) | Test an unprepared ticker; source absence gets an honest unavailable state. Latency and required historical depth are unspecified. |
| Pull evidence beyond AR/transcripts | Main brief stresses AR + transcripts; reference also defines company filings/results/presentations as primary data. (M pp. 2-3; R p. 2) | Keep AR + transcripts central. If we add results/presentations for delivered numbers, record the rationale rather than silently substituting them. |
| Screener tables as research evidence | Screener is named as a link source; reference describes its standardized financials. (M p. 2; R p. 2) | Prefer original company documents for substantive claims until this boundary is resolved. |
| Demo companies | A portfolio plus "a handful" for ad-hoc research, "say 3-5," optionally outside portfolio. (M p. 1) | Plan 15 portfolio companies and 3 ad-hoc demos; choose at least one outside portfolio to demonstrate generalisation. This is our proposed scope. |
| Hosting/repository access and AI history format | Phone trial, GitHub repo, exports/share links. (M p. 4) | Verify reviewer access. Public repository, specific export format, video, slides, and a separate PDF report are not specified. |

R pp. 2-3 explain financial terms and document types; they do not create extra feature obligations. Treat the taxonomy's low-relevance labels as guidance rather than proof that an auditor appointment or an unclassified filing can never matter.
