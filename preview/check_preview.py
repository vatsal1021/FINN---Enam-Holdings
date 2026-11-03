"""HTTP/content checks for the running loopback preview; no upstream requests."""
import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = 'http://127.0.0.1:8765'
checks = []


def get(route):
    try:
        with urllib.request.urlopen(BASE + route, timeout=12) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as error:
        return error.code, dict(error.headers), error.read()


def check(name, condition, detail=''):
    checks.append({'name': name, 'passed': bool(condition), 'detail': detail})


for route in ['/', '/app.js', '/source.js', '/style.css', '/source.html?doc=infy-call&page=25', '/data.json']:
    status, headers, body = get(route)
    check('HTTP ' + route, status == 200 and len(body) > 0, f'{status}; {len(body)} bytes')
status, headers, body = get('/data.json')
data = json.loads(body)
check('Exactly the selected fifteen companies', {c['ticker'] for c in data['companies']} == {
    'INFY','RELIANCE','HDFCBANK','BHARTIARTL','LT','MARUTI','SUNPHARMA','HINDUNILVR','NTPC',
    'TATASTEEL','APOLLOHOSP','KPRMILL','CERA','PERSISTENT','ELGIEQUIP'})
check('Four dated EOD samples, eleven unavailable', sum(c['quote'] is not None for c in data['companies']) == 4
      and all(c['quote']['date'] == '2026-10-29' for c in data['companies'] if c['quote']))
check('Eight selected filings; two manually prioritised', len(data['events']) == 8 and sum(e['priority']=='attention' for e in data['events']) == 2)
check('No reference to absent evidence', all(not e['evidence'] or e['evidence'] in data['evidence'] for e in data['events']))
for key, evidence in data['evidence'].items():
    doc = data['documents'][evidence['doc']]
    page = next(p for p in doc['pages'] if p['number']==evidence['page'])
    check('Passage matches saved PDF extraction: ' + key,
          ' '.join(evidence['passage'].split()) in ' '.join(page['text'].split()), f"{evidence['doc']} page {evidence['page']}")
for key, doc in data['documents'].items():
    status, headers, body = get(doc['pdf'])
    check('Saved PDF identity: ' + key, status == 200 and body.startswith(b'%PDF-') and hashlib.sha256(body).hexdigest()==doc['sha256'], f'{status}; {len(body)} bytes')
    check('Source URL is original HTTPS: ' + key, doc['url'].startswith('https://'))
if 'pageImage' in data['documents']['kpr-results']:
    status, headers, body = get(data['documents']['kpr-results']['pageImage'])
    check('Rendered original results table', status==200 and body.startswith(b'\x89PNG'), f'{status}; {len(body)} bytes')
for route in ['/project-notes/requirements.md','/experiments/samples/requests.jsonl','/../project-notes/requirements.md','/documents/unknown.pdf']:
    status, _, _ = get(route)
    check('Workspace not exposed: ' + route, status == 404, str(status))
check('Stale call not labelled current', data['documents']['kpr-old-call']['status']=='stale' and data['documents']['kpr-old-call']['date']=='2023-08-04')
check('Apollo call is cover letter / partial', data['documents']['apollo-cover']['status']=='partial' and data['documents']['apollo-cover']['pageCount']==1)
result = {'checked_at_utc':datetime.now(timezone.utc).isoformat(), 'base_url':BASE,
          'scope':'Local HTTP and saved evidence checks only. Browser interactions are recorded separately.',
          'passed':sum(c['passed'] for c in checks), 'total':len(checks), 'checks':checks}
(HERE / 'check-results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({k:result[k] for k in ['checked_at_utc','passed','total']}))
for c in checks:
    if not c['passed']: print('FAIL:', c)
raise SystemExit(0 if all(c['passed'] for c in checks) else 1)
