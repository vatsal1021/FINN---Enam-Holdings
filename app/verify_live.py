"""Check the saved real-source dataset and running local app without refreshing NSE."""
import csv
import hashlib
import io
import json
import tempfile
import threading
from datetime import datetime,timezone
from decimal import Decimal
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from .engine import holdings
from .server import App,make_handler
from .store import Store
from .views import live_data

BASE='http://127.0.0.1:8766'
ROOT=Path(__file__).resolve().parents[1]
checks=[]


def check(name,condition,detail=None):checks.append({'check':name,'passed':bool(condition),'detail':detail})


def http(base,path,method='GET',body=None,token=None):
    headers={'Content-Type':'application/json'}
    if token:headers['X-FINN-Token']=token
    request=Request(base+path,data=json.dumps(body).encode() if body is not None else None,method=method,headers=headers)
    try:
        with urlopen(request,timeout=20) as response:return response.status,response.read()
    except HTTPError as error:return error.code,error.read()


def main():
    store=Store(ROOT/'runtime');latest=store.latest_job()
    check('Saved full-portfolio job complete',latest['status']=='complete' and len(latest['tickers'])==15,latest['id'])
    expected={c['ticker'] for c in holdings()}
    company_checks=[c for c in store.rows('checks') if c['job_id']==latest['id']]
    check('All fifteen outcomes accounted for',{c['ticker'] for c in company_checks}==expected)
    quotes=store.rows('quotes')
    quote_report=[]
    for quote in quotes:
        source=store.get('sources',quote['source_id']);body=store.blob_path(source['sha256']).read_bytes()
        raw_rows=[{k.strip():v.strip() for k,v in row.items()} for row in csv.DictReader(io.StringIO(body.decode('utf-8-sig')))]
        raw=next(row for row in raw_rows if row['SYMBOL']==quote['ticker'] and row['SERIES']=='EQ')
        change=(Decimal(raw['CLOSE_PRICE'])/Decimal(raw['PREV_CLOSE'])-1)*100 if Decimal(raw['PREV_CLOSE'])>0 else None
        passed=(Decimal(quote['close_exact'])==Decimal(raw['CLOSE_PRICE']) and Decimal(quote['previous_exact'])==Decimal(raw['PREV_CLOSE'])
                and quote['volume']==int(raw['TTL_TRD_QNTY']) and quote['date']==datetime.strptime(raw['DATE1'],'%d-%b-%Y').date().isoformat()
                and (quote['change_pct'] is None if change is None else abs(Decimal(str(quote['change_pct']))-change)<Decimal('0.00000001'))
                and quote['price_unit']=='INR/share' and quote['volume_unit']=='shares')
        check('Official EOD reconciliation '+quote['ticker'],passed)
        quote_report.append({k:quote[k] for k in ['ticker','date','close_exact','previous_exact','volume','change_pct','source_id','retrieved_at']})
    for source in store.rows('sources'):
        path=store.blob_path(source['sha256'])
        check('Response hash '+source['id'],path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256'])
    events=store.rows('filings')
    check('Stored filings have unique exchange IDs',len(events)>0 and len({e['id'] for e in events})==len(events),len(events))
    for outcome in company_checks:
        source=store.get('sources',outcome['announcements_request_id'])
        rows=json.loads(store.blob_path(source['sha256']).read_bytes())
        stored=[e for e in events if e['ticker']==outcome['ticker'] and outcome['start']<=e['date']<=outcome['end']]
        check('Returned filing count '+outcome['ticker'],outcome['filings_status']=='passed' and outcome['filing_count']==len(rows)==len(stored),len(rows))
    for route in ['/','/app.js','/live.js','/style.css','/source.js','/?demo=1','/data.json','/health']:
        status,body=http(BASE,route);check('HTTP '+route,status==200 and bool(body),status)
    status,body=http(BASE,'/api/data');data=json.loads(body)
    check('Live data matches real store, separate from demo',status==200 and data['mode']=='live' and len(data['events'])==len(events) and len(data['companies'])==15)
    check('Verification does not auto-refresh upstream',data['autoRefreshEnabled'] is False)
    check('Push data does not substitute generated briefs',data['briefs']=={} and all(not e.get('summary') for e in data['events']))
    check('Price/feed outcomes 15/15',data['coverage']['passed']==15,data['coverage'])
    ready=list(data['documents'].values())
    check('Validated attachments accounted for, failures excluded',len(ready)>=1 and len(ready)==data['coverage']['attachmentsReady'] and all(d['status']=='ready' for d in ready),data['coverage'])
    for doc in ready:
        status,body=http(BASE,doc['pdf'])
        check('Served validated PDF '+doc['ticker'],status==200 and hashlib.sha256(body).hexdigest()==doc['sha256'] and b'%%EOF' in body[-4096:])
        status,body=http(BASE,'/api/filings/'+doc['event_id']+'/evidence')
        payload=json.loads(body)
        check('Cached evidence '+doc['ticker'],status==200 and bool(payload.get('evidence',{}).get('passage')))
        status,body=http(BASE,'/api/documents/'+doc['id'])
        check('Source page data '+doc['ticker'],status==200 and len(json.loads(body)['pages'])>0)
    for route in ['/runtime/finn.sqlite3','/.git/config','/app/holdings.json','/api/filings/unknown/evidence','/files/unknown.pdf']:
        status,_=http(BASE,route);check('Unexposed/unknown route '+route,status==404,status)
    status,_=http(BASE,'/api/refresh',method='POST',body={});check('Refresh rejects missing token',status==403)
    # Actual full-data recovery, without copying raw files or claiming a cloud restart.
    snapshot=ROOT/'app'/'bootstrap.json.gz';store.export_snapshot(snapshot)
    temp_root=ROOT/'runtime'/'verification-temporary';temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as temp:
        restored=Store(Path(temp)/'recovery');restored.restore_snapshot(snapshot)
        recovered=live_data(restored)
        check('Actual snapshot restores stored filings and 15 quotes',len(recovered['events'])==len(events) and sum(bool(c['quote']) for c in recovered['companies'])==15)
        check('Recovery keeps original retrieval time',restored.rows('quotes')[0]['retrieved_at']==store.rows('quotes')[0]['retrieved_at'])
        check('Recovery is labelled and does not bundle PDFs',bool(recovered['recovery']) and all(not d['has_file'] for d in recovered['documents'].values()))
        # HTTP duplicate-job branch tested with a local fixture lease; no source requests run.
        busy_store=Store(Path(temp)/'busy');job=busy_store.begin_job(['INFY'],latest['start'],latest['end'],latest['requested_eod'])
        fixture_app=App(Path(temp)/'busy')
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(fixture_app));thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            local='http://127.0.0.1:'+str(server.server_port)
            results=[http(local,'/api/refresh',method='POST',body={},token=fixture_app.token) for _ in range(2)]
            decoded=[json.loads(r[1]) for r in results]
            check('HTTP duplicate refresh reuses one active lease',all(r[0]==202 for r in results) and all(d['reused'] and d['job']['id']==job['id'] for d in decoded) and len(busy_store.rows('jobs'))==1)
            check('Duplicate-lease check made zero upstream requests',len(busy_store.rows('sources'))==0)
        finally:server.shutdown();server.server_close();thread.join()
        assert Path(temp).resolve().is_relative_to(temp_root.resolve())
    result={'checked_at':datetime.now(timezone.utc).isoformat(),'scope':'Saved real dataset + local HTTP; no portfolio refresh or chargeable model calls. Lease fault/recovery checks are local, not hosted.',
            'passed':sum(c['passed'] for c in checks),'total':len(checks),'job':latest,'companies':company_checks,'quotes':quote_report,'checks':checks}
    (ROOT/'app'/'verification'/'live-checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['checked_at','passed','total']}))
    for item in checks:
        if not item['passed']:print('FAIL',item)
    raise SystemExit(0 if all(c['passed'] for c in checks) else 1)


if __name__=='__main__':main()
