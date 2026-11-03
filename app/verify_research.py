"""Saved real-source and local HTTP audit. Does not refresh upstream or invoke a model."""
import hashlib
import json
import re
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from .research import ISSUER_INDEXES,begin_research,identity_matches,retrieve
from .store import Store,utcnow
from .verify_live import http

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8766'
TICKERS=['INFY','CERA','TITAN','ASIANPAINT','ITC','APOLLOHOSP']


def main():
    store=Store(ROOT/'runtime');checks=[];outcomes=[];timings=[]
    def check(name,ok,detail=None):checks.append({'check':name,'passed':bool(ok),'detail':detail})
    status,body=http(BASE,'/api/data');data=json.loads(body);token=data['refreshToken']
    check('Retrieval remains separate from synthesis',status==200 and data['briefs']=={})
    check('Push remains 15 companies and 61 stored filings',len(data['companies'])==15 and len(data['events'])==61 and data['coverage']['passed']==15)
    check('Fresh test symbols have no issuer/PDF configuration',not any(t in ISSUER_INDEXES for t in ['ASIANPAINT','ITC','TITAN']))
    before=len(store.rows('sources'))
    for ticker in TICKERS:
        record=store.get('research',ticker);docs=[store.get('documents',i) for i in record['documents']]
        check('Validated NSE identity '+ticker,record.get('company',{}).get('ticker')==ticker and record['company'].get('isin'))
        check('Annual report beyond 60 pages '+ticker,any(d['source_kind']=='annual' and len(d['pages'])==d['pageCount'] and max(d['indexed_pages'])>60 for d in docs))
        if ticker in ['INFY','CERA','TITAN','ASIANPAINT']:
            check('Annual AND actual call '+ticker,record['status']=='ready' and {d['source_kind'] for d in docs}=={'annual','call'})
        else:check('Honest partial coverage '+ticker,record['status']=='partial' and bool(record['warnings']) and all(d['source_kind']=='annual' for d in docs))
        for doc in docs:
            raw=store.blob_path(doc['sha256']).read_bytes()
            check('Immutable PDF bytes '+doc['id'],hashlib.sha256(raw).hexdigest()==doc['sha256'] and raw.startswith(b'%PDF-') and b'%%EOF' in raw[-4096:])
            source=store.get('sources',doc['source_id'])
            check('Source provenance '+doc['id'],source['validation']=='passed' and source['sha256']==doc['sha256'] and doc['discovery_source_id'])
            check('PDF company identity '+doc['id'],identity_matches('\n'.join(p['text'] for p in doc['pages'][:6]),record['company']))
            if doc['source_kind']=='annual':
                end=doc['period'][-2:];start=doc['period'][3:7]
                text='\n'.join(p['text'] for p in doc['pages'][:6])
                range_match=re.search(r'\b'+start+r'\s*[-–/]\s*(?:20'+end+'|'+end+r')\b',text)
                end_match=re.search(r'financial year ended 31st March,? 20'+end,text,re.I)
                check('Financial-year match '+doc['id'],bool(range_match or end_match))
        for question in ['What are the business segments and management outlook?','operating cash flow receivables']:
            with patch('app.research.SourceClient.get',side_effect=AssertionError('Unexpected upstream call during retrieval')):
                result=retrieve(store,ticker,question)
            check('Real passages for '+ticker+' / '+question,bool(result['passages']) and not result['model']['available'] and 'answer' not in result)
            for p in result['passages']:
                doc=store.get('documents',p['doc']);page=next(x for x in doc['pages'] if x['number']==p['page'])
                with store.connect() as db:known=db.execute('SELECT text FROM research_chunks WHERE chunk_id=? AND doc_id=?',(p['id'],doc['id'])).fetchone()
                check('Citation resolves '+p['id'],bool(known) and p['doc'] in record['documents'] and p['ticker']==ticker and p['sha256']==doc['sha256'] and p['source_url']==doc['url'] and p['page'] in doc['indexed_pages'] and p['passage'] in page['text'])
        status,body=http(BASE,'/api/research',method='POST',body={'ticker':ticker},token=token);cached=json.loads(body)
        check('HTTP cached load '+ticker,status==202 and cached['reused'] and cached['job']['id']==record['id'])
        outcomes.append({'ticker':ticker,'status':record['status'],'job_id':record['id'],'seconds':record['seconds'],
            'checked_at':record['checked_at'],'warnings':record['warnings'],'errors':record['errors'],
            'documents':[{k:d.get(k) for k in ['id','source_kind','period','date','call_date','freshness','pageCount','chunks','sha256','url','source_id','discovery_source_id','retrieved']}|{'indexed_pages':len(d['indexed_pages']),'extracted_pages':len(d['pages'])} for d in docs],
            'candidates':record['candidates']})
    infy=store.get('documents',store.get('research','INFY')['documents'][1])
    check('INFY mixed bundle call starts at physical page 24',min(infy['indexed_pages'])==24 and not any(p<24 for p in infy['indexed_pages']))
    for ticker in ['CERA','TITAN']:
        record=store.get('research',ticker)
        check('Newer notice not substituted '+ticker,any(c['state']=='notice-not-transcript' for c in record['candidates']))
    apollo=store.get('research','APOLLOHOSP')
    check('Apollo cover letter and actual issuer block retained',any(c['state']=='cover-letter' for c in apollo['candidates']) and any(c['state']=='blocked' and '403' in c.get('error','') for c in apollo['candidates']))
    check('Apollo revision fallback caveat retained',any('revised' in w for w in apollo['warnings']))
    for _ in range(5):
        start=time.perf_counter();status,body=http(BASE,'/api/research/query',method='POST',body={'ticker':'CERA','question':'operating cash flow receivables'},token=token)
        timings.append(round(time.perf_counter()-start,4));check('Warm HTTP question request',status==200 and bool(json.loads(body)['passages']))
    status,body=http(BASE,'/api/research/query',method='POST',body={'ticker':'CERA','question':'xylophone quasar unobtainium'},token=token)
    check('Unanswerable question returns no invented passages',status==200 and json.loads(body)['passages']==[])
    for path in ['/api/documents/not-real','/files/not-real.pdf','/api/research/jobs/not-real','/api/citations/not-real']:
        check('Unknown source/citation route '+path,http(BASE,path)[0]==404)
    check('Question API rejects missing token',http(BASE,'/api/research/query',method='POST',body={'ticker':'CERA','question':'cash flow'})[0]==403)
    check('URL input rejected before discovery',http(BASE,'/api/research',method='POST',body={'ticker':'https://evil.test'},token=token)[0]==400)
    status,body=http(BASE,'/api/research',method='POST',body={'ticker':'ZZFINNINVALID'},token=token);invalid=json.loads(body)['job']
    for _ in range(25):
        status,body=http(BASE,'/api/research/jobs/'+invalid['id']);invalid=json.loads(body)
        if invalid['status']!='running':break
        time.sleep(.1)
    check('Unknown ticker has explicit invalid/unestablished identity',invalid['status']=='invalid' and not invalid['documents'])
    check('Cache/question/invalid checks made zero upstream requests',len(store.rows('sources'))==before)
    check('Manual demo remains separate',b'content="demo"' in http(BASE,'/?demo=1')[1] and bool(json.loads(http(BASE,'/data.json')[1])['briefs']))
    temporary=ROOT/'runtime'/'verification-temporary';temporary.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temporary) as directory:
        recovered=Store(directory);recovered.restore_snapshot(ROOT/'app'/'bootstrap.json.gz')
        with patch('app.research.SourceClient.get',side_effect=AssertionError('Recovery retrieval must use stored text only')):
            restored=retrieve(recovered,'CERA','operating cash flow receivables')
        original=retrieve(store,'CERA','operating cash flow receivables')
        check('Actual research snapshot rebuilds derived index with same citations',restored['passages']==original['passages'])
        check('Recovery does not pretend raw PDFs are bundled',all(not d['has_file'] for d in restored['documents']))
        check('Recovery preserves document retrieval time',restored['documents'][0]['retrieved']==original['documents'][0]['retrieved'])
        assert Path(directory).resolve().is_relative_to(temporary.resolve())
    report={'checked_at':utcnow(),'scope':'Real saved PDFs, metadata and local HTTP; no new upstream or model requests. Mobile observations are separate.',
        'passed':sum(c['passed'] for c in checks),'total':len(checks),'warm_http_query_seconds':timings,'outcomes':outcomes,'checks':checks}
    (ROOT/'app'/'verification'/'pull-checks.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['checked_at','passed','total','warm_http_query_seconds']}))
    for check in checks:
        if not check['passed']:print('FAIL',check)
    raise SystemExit(0 if all(c['passed'] for c in checks) else 1)


if __name__=='__main__':main()
