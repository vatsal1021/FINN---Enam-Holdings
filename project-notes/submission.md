# Submission preparation — do not send automatically

Deadline November 1, 2026; hour/timezone unspecified. Main PDF p4 lists deliverables; see `requirements.md`.

## Actual AI build history

Supply actual exports or share links for the conversations used, including the coordinating chat and this implementation chat. Notes and Git history support them but do not replace actual conversations.

1. Open each original build conversation and use its available share/export action. Include actual planning, source verification, implementation, failures and corrections; do not compose a replacement transcript.
2. Review shares/exports for API keys, passwords, private account details and unrelated content before giving reviewers access. `.env.local` must never be included. Use supported redaction/export controls if required; do not publish a secret to satisfy history submission.
3. Paste accessible links below or attach actual exports. Test signed-out access. Local chat IDs/workspace links are not reviewer links.

| Conversation | Actual share link / export |
| --- | --- |
| Coordinating assignment/build chat | PENDING — actual share/export needed |
| Requirements, research and implementation chat | PENDING — actual share/export needed |

## Covering-email draft

To: assessment@enam.com
Subject: ENAM - IIT screening - 2027

Dear ENAM team,

Please find my FINN prototype for monitoring and researching Indian listed companies.

- Prototype: https://finn-enam-holdings.onrender.com
- Repository: https://github.com/Sanchit525/FINN---Enam-holdings
- Actual AI build conversations: [INSERT ACCESSIBLE LINKS OR ATTACH EXPORTS]

The product connects a 15-company portfolio digest to focused company investigation. It uses actual EOD prices/volume and exchange filings, then annual reports and actual earnings-call transcripts for cited Gemini answers and follow-ups. Reviewers can inspect quotes, document periods and physical PDF pages and open original documents. Freshness, partial coverage and failed retrievals remain visible.

I prioritised a small mobile workflow and traceable evidence over a broad dashboard. Python, SQLite, PyMuPDF and buildless HTML/CSS/JavaScript keep the architecture compact. Retrieval/validation are separate from explanation; reported figures are checked rather than delegated to model arithmetic. Unfamiliar NSE symbols work where documents are available, with honest missing-source states.

Local validation includes 40 offline tests, push/retrieval checks and ten source-reviewed answer cases, with failed first passes preserved. The actual Render Free service passed source search, a 15-company EOD/filings refresh using October 30 EOD, redeployment recovery, and a real uncached cited Gemini answer followed by a cached repeat. That answer correctly reports Infosys growth from actual-call PDF p25; provider generation took 3.297 seconds in this case. One client connection timed out before health; verification succeeded through another DNS-returned address with normal HTTPS verification. This small audit does not guarantee every answer or network/latency outcome. Free-host storage is ephemeral and upstream/model quota can fail; source-only recovery preserves dated evidence. I omitted broker integrations, trading advice, intraday feeds, OCR and universal financial-table normalisation. Next steps would be broader source/answer evaluation, durable ingestion and physical-phone testing with investors.

Regards,
Sanchit Arora

## Before sending

- History-sharing permission is still pending separately. Add actual approved share links/exports before sending; project notes and Git history are not substitutes.
- Open prototype, repository and history links signed out/on a phone.
- Confirm intended version and exact subject; submit before the unspecified cutoff.
- This is a draft. No email has been sent.
