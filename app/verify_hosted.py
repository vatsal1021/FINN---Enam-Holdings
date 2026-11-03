"""Small real hosted release probe. Source phase waits for one actual catch-up job."""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from .gemini import load_key
from .store import utcnow

ROOT=Path(__file__).resolve().parents[1]
QUESTION='What constant-currency revenue growth did management report for Q2 FY27?'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--base',required=True)
    parser.add_argument('--phase',choices=['source','answer','recovery'],default='source');args=parser.parse_args()
    base=args.base.rstrip('/');secret=load_key().encode();checks=[];report={'checked_at':utcnow(),'base':base,'phase':args.phase}
    def call(path,body=None,token=None):
        headers={'Content-Type':'application/json'}
        if token:headers['X-FINN-Token']=token
        request=Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with urlopen(request,timeout=120) as r:status,raw=r.status,r.read()
        except HTTPError as e:status,raw=e.code,e.read();e.close()
        if secret and secret in raw:raise RuntimeError('Secret found in public response; body suppressed')
        try:return status,json.loads(raw)
        except ValueError:return status,{'non_json':True}
    def check(name,ok,detail=None):checks.append({'check':name,'passed':bool(ok),'detail':detail})
    status,health=call('/health');check('Hosted health',status==200 and health.get('status')=='ok',health)
    status,data=call('/api/data');token=data['refreshToken']
    check('15 companies remain readable',status==200 and len(data.get('companies',[]))==15)
    check('Recovery provenance visible',bool(data.get('recovery')),data.get('recovery'))
    check('Free-host storage declared ephemeral',data.get('storage')=='ephemeral')
    check('Private answer/audit tables absent','answers' not in data and 'model_calls' not in data)
    report['model_available']=data['model']['available']
    if args.phase=='recovery':
        previous=json.loads((ROOT/'app/verification/hosted-source.json').read_text(encoding='utf-8'))
        old=next(c['detail']['restored_at'] for c in previous['checks'] if c['check']=='Recovery provenance visible')
        restored=data.get('recovery',{}).get('restored_at','')
        check('New runtime restored after redeployment',restored>old,{'previous_restored_at':old,'restored_at':restored})
        status,_=call('/api/research/TCS')
        check('Unsnapshotted TCS state is not falsely durable',status==404)
    payload={'ticker':'INFY','question':QUESTION,'history':[]}
    if args.phase=='answer':
        status,result=call('/api/research/answer',payload,token);answer=result.get('answer',{})
        check('Real hosted cited answer',status==200 and answer.get('status')=='ready',answer)
        if answer.get('status')=='ready':
            ids={p['id']:p for p in result['passages']};cites=[c for claim in answer['content']['claims'] for c in claim['citations']]
            normal=lambda s:' '.join(s.split())
            check('Answer quotes occur in returned source pages',bool(cites) and all(c['evidence_id'] in ids and normal(c['quote']) in normal(ids[c['evidence_id']]['passage']) for c in cites))
            _,again=call('/api/research/answer',payload,token)
            check('Hosted repeat uses cache',again['answer'].get('cached') and again['answer'].get('content')==answer['content'])
    else:
        status,result=call('/api/research/query',payload,token)
        check('Hosted pull retrieves real evidence',status==200 and bool(result.get('passages')))
        call_page=next((p for p in result.get('passages',[]) if p['doc']=='3e7c4e2a2b30f514af1a69bb' and p['page']==25),None)
        check('Actual call p25 retrievable',bool(call_page))
        if call_page:
            status,doc=call('/api/documents/'+call_page['doc'])
            page=next((p for p in doc.get('pages',[]) if p['number']==25),{})
            check('Citation resolves to full saved source',status==200 and call_page['passage'] in page.get('text','') and '1.5%' in page.get('text',''))
            report['document']={k:doc.get(k) for k in ('id','sha256','period','retrieved','url','has_file')}
        if args.phase=='source':
            active=data.get('activeJob');deadline=time.monotonic()+360
            if not active:
                status,kick=call('/api/refresh',{'tickers':['INFY']},token);active=kick.get('job')
                check('Real source refresh accepted',status==202,{'job_id':active.get('id') if active else None})
            if active:
                job=active
                while job.get('status')=='running' and time.monotonic()<deadline:
                    time.sleep(5);_,job=call('/api/jobs/'+active['id'])
                report['refresh_job']=job
                _,latest=call('/api/data')
                report['coverage_after_refresh']=latest.get('coverage')
                report['company_outcomes']=[{'ticker':c['ticker'],'check':c.get('check'),'coverage':c.get('coverage')} for c in latest['companies']]
                check('Actual source job finished',job.get('status')=='complete',{'status':job.get('status'),'errors':job.get('errors')})
                check('Hosted refreshed EOD and filings passed',all(c.get('check',{}).get('filings_status')=='passed' and c.get('check',{}).get('eod_status')=='passed' for c in latest['companies'] if c['ticker'] in job['tickers']))
    report.update(finished_at=utcnow(),checks=checks,passed=sum(c['passed'] for c in checks),total=len(checks))
    path=ROOT/'app/verification'/('hosted-'+args.phase+'.json');path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('base','phase','passed','total','model_available','finished_at')},ensure_ascii=True),flush=True)

if __name__=='__main__':main()
