"""Prepare a small, explicitly manual preview from existing local evidence. No network."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
SAMPLES = ROOT / 'experiments' / 'samples'
DIST = HERE / 'dist'
DIST.mkdir(exist_ok=True)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


requests = load(SAMPLES / 'official-eod-2026-10-29.json')
ledger = [json.loads(line) for line in (SAMPLES / 'requests.jsonl').read_text(encoding='utf-8').splitlines()]
file_map = {}
documents = {}


def document(key, filename, title, kind, period, date, pages, status='saved', note=''):
    path = SAMPLES / filename
    record = next(r for r in ledger if Path(r.get('file', '').replace('\\', '/')).name == filename and r.get('ok'))
    text = load(path.with_name(path.name + '.text.json'))
    selected = []
    for number in pages:
        original = next(p['text'] for p in text if p['pdf_page'] == number)
        selected.append({'number': number, 'text': original.strip()})
    documents[key] = {
        'id': key, 'title': title, 'kind': kind, 'period': period, 'date': date,
        'status': status, 'note': note, 'url': record.get('final_url', record['requested_url']),
        'retrieved': record['retrieved_at_utc'], 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'pdf': f'/documents/{key}.pdf', 'pages': selected, 'pageCount': len(text),
    }
    file_map[f'/documents/{key}.pdf'] = str(path.relative_to(ROOT)).replace('\\', '/')


document('infy-call', 'INFY-filing-0-20261030T074521070565Z.pdf',
         'Infosys · Q2 FY27 earnings call', 'Earnings-call transcript', 'Q2 FY27', '2026-10-23', [25],
         note='Exchange bundle filed 28 Oct 2026. Actual earnings call starts at PDF page 24; this passage is page 25, printed page 2. The bundle also contains a separate press conference.')
document('infy-annual', 'INFY-annual-0-20261030T074606259596Z.pdf',
         'Infosys · Annual report 2025–26', 'Annual report', 'FY2025–26', '2026', [10])
document('kpr-results', 'KPRMILL-filing-0-20261030T074523691154Z.pdf',
         'KPR Mill · September 2026 results', 'Exchange results filing', 'Q2 FY27 · quarter ended 30 Sep 2026', '2026-10-28', [3, 9],
         note='PDF page 3 is standalone; page 9 is consolidated. Tables are in INR lakh. Values in the preview were manually checked against the rendered table, not extracted by an automated financial parser.')
document('cera-call', 'CERA-transcript-0-20261030T074614659681Z.pdf',
         'Cera · Q1 FY27 earnings call', 'Earnings-call transcript', 'Q1 FY27', '2026-08-08', [4],
         note='PDF page 4 is printed page 3. This is an August call, not a Q2 FY27 transcript. A comparative-year inconsistency elsewhere on this page is preserved in the full page text, not silently repaired.')
document('cera-annual', 'CERA-annual-0-20261030T074835558662Z.pdf',
         'Cera · Annual report 2025–26', 'Annual report', 'FY2025–26', '2026', [3, 148])
document('cera-notice', 'CERA-filing-0-20261030T074525316823Z.pdf',
         'Cera · Q2 & H1 FY27 call invitation', 'Call notice', 'Q2 & H1 FY27', '2026-10-22', [1, 2],
         note='Invitation only. It is not a call transcript and does not establish results or management commentary.')
document('kpr-old-call', 'KPRMILL-transcript-0-20261030T074612081320Z.pdf',
         'KPR Mill · Q1 FY24 earnings call', 'Earnings-call transcript', 'Q1 FY24', '2023-08-04', [4], status='stale',
         note='Historical source from August 2023. Excluded from current management commentary. No recent KPR call was established in the saved experiments.')
document('apollo-cover', 'APOLLOHOSP-transcript-0-20261030T075051735128Z.pdf',
         'Apollo · transcript submission cover letter', 'Cover letter only', 'Q1 FY27', '2026-08-19', [1], status='partial',
         note='The saved attachment is a single-page cover letter. Its full linked transcript returned HTTP 403 in the local experiment. No call-body research is shown.')

for file, route in [('KPRMILL-financial-pdf-page-9.png', '/evidence/kpr-results-page-9.png')]:
    path = SAMPLES / file
    if path.exists():
        file_map[route] = str(path.relative_to(ROOT)).replace('\\', '/')
        documents['kpr-results']['pageImage'] = route


def excerpt(doc, start, end=None, max_chars=None):
    text = ' '.join(documents[doc]['pages'][0]['text'].split())
    index = text.index(start)
    text = text[index:]
    if end:
        text = text[:text.index(end) + len(end)]
    if max_chars:
        text = text[:max_chars]
    return text


evidence = {
    'infy-growth': {'doc': 'infy-call', 'page': 25, 'label': 'Growth, AI revenue and large deals',
                    'passage': excerpt('infy-call', 'Our revenue growth', 'was at 8.2%.'),
                    'context': 'Salil Parekh · management opening remarks. Constant-currency growth; AI share of total revenue. These are reported management statements, not an investment verdict.'},
    'infy-deals': {'doc': 'infy-call', 'page': 25, 'label': 'Large-deal disclosure',
                   'passage': excerpt('infy-call', 'Our large deals', 'The second mega deal was for $1 bn for a renewal.'),
                   'context': 'A multi-year deal value is not quarterly revenue. The future contribution is a management expectation.'},
    'infy-business': {'doc': 'infy-annual', 'page': 10, 'label': 'Business description',
                      'passage': excerpt('infy-annual', 'Infosys is a global leader', 'unlock AI value at scale.'),
                      'context': 'Company description in annual report FY2025–26. Wording belongs to the company.'},
    'kpr-consolidated': {'doc': 'kpr-results', 'page': 9, 'label': 'Consolidated quarterly results',
                         'passage': documents['kpr-results']['pages'][1]['text'],
                         'context': 'Original PDF text, with extraction line breaks retained. Quarter ended 30 September 2026; consolidated; INR lakh. See the source-page image for the aligned table. Revenue from operations = sale of products/services 187,117 + other operating revenue 6,857 = 193,974 lakh. PAT 34,500 lakh. Arithmetic and summary manually checked.'},
    'cera-outlook': {'doc': 'cera-call', 'page': 4, 'label': 'FY27 brand investment and outlook',
                     'passage': excerpt('cera-call', 'Building on the launch', 'creating sustainable long-term value for all our stakeholders.'),
                     'context': 'Management remarks from 8 August 2026. Approximate planned spend and FY27 revenue guidance, not delivered full-year results.'},
    'cera-context': {'doc': 'cera-annual', 'page': 3, 'label': 'Demand context in the annual report',
                     'passage': excerpt('cera-annual', 'Even as consumers', 'immediate financial commitments.'),
                     'context': 'Chairman and managing director’s overview. Management’s description of demand, not an independently verified causal conclusion.'},
    'cera-notice': {'doc': 'cera-notice', 'page': 1, 'label': 'Original invitation',
                    'passage': documents['cera-notice']['pages'][0]['text'],
                    'context': 'A call notice is a scheduled event. It contains no actual call discussion.'},
    'kpr-stale': {'doc': 'kpr-old-call', 'page': 4, 'label': 'Historical call · not current',
                  'passage': documents['kpr-old-call']['pages'][0]['text'],
                  'context': 'Stale example: August 2023. Kept available for inspection; not used for a 2026 management outlook.'},
    'apollo-partial': {'doc': 'apollo-cover', 'page': 1, 'label': 'Cover letter · transcript body missing',
                       'passage': documents['apollo-cover']['pages'][0]['text'],
                       'context': 'Partial/failure example. A successful PDF download does not mean a full transcript was acquired.'},
}

holdings = [
    ('INFY', 'Infosys', 'IT services'), ('RELIANCE', 'Reliance Industries', 'Energy, retail & digital'),
    ('HDFCBANK', 'HDFC Bank', 'Banking'), ('BHARTIARTL', 'Bharti Airtel', 'Telecom'),
    ('LT', 'Larsen & Toubro', 'Engineering & construction'), ('MARUTI', 'Maruti Suzuki', 'Automobiles'),
    ('SUNPHARMA', 'Sun Pharmaceutical', 'Pharmaceuticals'), ('HINDUNILVR', 'Hindustan Unilever', 'Consumer staples'),
    ('NTPC', 'NTPC', 'Power'), ('TATASTEEL', 'Tata Steel', 'Metals'), ('APOLLOHOSP', 'Apollo Hospitals', 'Healthcare'),
    ('KPRMILL', 'KPR Mill', 'Textiles'), ('CERA', 'Cera Sanitaryware', 'Building products'),
    ('PERSISTENT', 'Persistent Systems', 'IT services'), ('ELGIEQUIP', 'Elgi Equipments', 'Industrial equipment'),
]
quotes = {r['SYMBOL']: {'close': float(r['CLOSE_PRICE']), 'previous': float(r['PREV_CLOSE']),
                        'volume': int(r['TTL_TRD_QNTY']), 'date': requests['asof'],
                        'source': requests['source_request']['final_url']} for r in requests['raw_rows']}
companies = [{'ticker': t, 'name': n, 'sector': s, 'quote': quotes.get(t),
              'coverage': {'INFY': 'saved', 'CERA': 'saved', 'KPRMILL': 'stale', 'APOLLOHOSP': 'partial'}.get(t, 'missing')}
             for t, n, s in holdings]

metadata = {}
for ticker in ['INFY', 'KPRMILL', 'CERA']:
    metadata[ticker] = load(next(SAMPLES.glob(ticker + '-nse-announcements-*.json')))


def event(ticker, contains, title, priority, reason, summary, ev=None):
    raw = next(row for row in metadata[ticker] if contains in row['attchmntFile'])
    return {'id': raw['seq_id'], 'ticker': ticker, 'title': title, 'priority': priority,
            'reason': reason, 'summary': summary, 'evidence': ev, 'url': raw['attchmntFile'],
            'description': raw['attchmntText'], 'date': raw['sort_date'][:10],
            'time': raw['an_dt'], 'category': raw['desc'], 'manual': bool(summary)}


events = [
    event('INFY', 'Earnings_call_transcript', 'Q2 earnings call is available', 'attention',
          'New management commentary on growth and the revenue mix.',
          'Management reported Q2 constant-currency revenue growth of 1.5% YoY and AI revenue at 10.5% of total revenue, versus 8.2% last quarter.', 'infy-growth'),
    event('KPRMILL', 'BMOUTCOME28102026', 'Quarterly results to review', 'attention',
          'A new quarterly results filing contains updated financial statements.',
          'For the September quarter, consolidated revenue from operations was ₹1,939.74 crore and PAT was ₹345.00 crore. Figures are manually checked; no causal or investment conclusion is implied.', 'kpr-consolidated'),
    event('CERA', 'CERAQ2CALL', 'Q2 & H1 call invitation', 'routine',
          'Scheduling notice; no call commentary or results in this document.',
          'A call invitation was filed. Do not treat it as a Q2 transcript.', 'cera-notice'),
    event('INFY', 'Newspaper', 'Newspaper publication', 'routine',
          'Publication copy. Content has not been reviewed for material changes.', '', None),
    event('KPRMILL', 'Newspaper', 'Newspaper publication', 'routine',
          'Publication copy. Content has not been reviewed for material changes.', '', None),
    event('KPRMILL', 'Investormeet', 'Investor meeting schedule', 'routine',
          'Meeting schedule; no evidence of new operating information in the saved metadata.', '', None),
    event('INFY', 'PR_29102026', 'Finacle awards announcement', 'unreviewed',
          'Only exchange metadata is saved. Materiality is not assessed.', '', None),
    event('CERA', 'CERA745', 'Depository compliance certificate', 'routine',
          'Regulatory certificate. Original content has not been reviewed.', '', None),
]

briefs = {
    'INFY': {'headline': 'Growth and AI mix, in management’s words.', 'coverage': 'Annual report + actual Q2 FY27 earnings call saved.',
             'date': 'Call: 23 Oct 2026 · filed 28 Oct', 'documents': ['infy-annual', 'infy-call'],
             'facts': [
                 {'label': 'Business', 'text': 'Infosys describes its business as AI-first consulting and technology services, supporting enterprise transformation.', 'evidence': 'infy-business'},
                 {'label': 'Management commentary', 'text': 'Management reported Q2 constant-currency revenue growth of 1.5% YoY and 1.2% sequentially. AI revenue represented 10.5% of total revenue, up from 8.2% last quarter.', 'evidence': 'infy-growth'},
                 {'label': 'What to investigate', 'text': 'Management disclosed $5.2 billion of large deals, including a seven-year net-new deal of over $2 billion. Check conversion timing: deal value is not the same as quarterly revenue.', 'evidence': 'infy-deals'}]},
    'CERA': {'headline': 'Read the outlook with its date attached.', 'coverage': 'Annual report + August Q1 FY27 call saved. October filing is a call notice only.',
             'date': 'Call: 8 Aug 2026 · Q1 FY27', 'documents': ['cera-annual', 'cera-call', 'cera-notice'],
             'facts': [
                 {'label': 'Annual-report context', 'text': 'Management’s annual-report overview describes customers deferring sanitaryware and faucetware purchases while prioritising other household commitments.', 'evidence': 'cera-context'},
                 {'label': 'Management outlook', 'text': 'In the August call, management maintained FY27 revenue-growth guidance of 18–20% and planned approximately ₹85 crore of brand-building and marketing investment.', 'evidence': 'cera-outlook'},
                 {'label': 'What remains open', 'text': 'These are forward-looking statements. The October Q2 invitation does not establish delivery against them; a newer actual call is not saved here.', 'evidence': 'cera-notice'}]},
    'KPRMILL': {'headline': 'Current results. A gap in current commentary.', 'coverage': 'October results saved; the only saved call is from August 2023 and is excluded from current outlook.',
                'date': 'Results: quarter ended 30 Sep 2026', 'documents': ['kpr-results', 'kpr-old-call'],
                'facts': [
                    {'label': 'Verified results excerpt', 'text': 'Quarterly consolidated revenue from operations was ₹1,939.74 crore; PAT was ₹345.00 crore. The original table is in INR lakh, and the conversion divides by 100.', 'evidence': 'kpr-consolidated'},
                    {'label': 'Stale source', 'text': 'The available Q1 FY24 transcript is dated 4 August 2023. It cannot support a current management view.', 'evidence': 'kpr-stale'}]},
    'APOLLOHOSP': {'headline': 'No research conclusion from a cover letter.', 'coverage': 'Partial: saved one-page submission; the full linked call returned HTTP 403 in the local experiment.',
                   'date': 'Cover letter: 19 Aug 2026', 'documents': ['apollo-cover'],
                   'facts': [{'label': 'Missing call body', 'text': 'A transcript submission was downloaded, but it contains only a cover letter. Current management commentary is unavailable in this preview.', 'evidence': 'apollo-partial'}]},
}

data = {'preview': {'asof': '2026-10-30', 'window': '22–29 Oct 2026', 'retrieved': '30 Oct 2026, approximately 13:09–13:30 IST',
                    'description': 'Saved experiment data. Summaries and priorities manually authored. No live feed or AI response.'},
        'companies': companies, 'events': events, 'documents': documents, 'evidence': evidence, 'briefs': briefs}
(DIST / 'data.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
(HERE / 'document_routes.json').write_text(json.dumps(file_map, indent=2), encoding='utf-8')
print(f'Prepared {len(companies)} companies, {len(events)} saved filing examples, {len(documents)} documents, {len(evidence)} evidence passages. No network requests.')
