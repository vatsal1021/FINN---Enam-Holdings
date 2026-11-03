"""API representation shared with the existing mobile interface."""
from datetime import datetime, timedelta
from .adapters import IST, KINDS, RULE_VERSION, allowed_url, classify
from .engine import holdings
from .store import utcnow
from .gemini import status as model_status


def public_document(store,doc,full=False):
    result=dict(doc)
    result['pdf']='/files/'+doc['id']+'.pdf'
    result['has_file']=bool(doc.get('sha256') and store.blob_path(doc['sha256']).exists())
    if not full:
        result['pages']=[p for p in doc['pages'] if p['number']==doc.get('excerpt_page')]
    return result


def evidence_for(doc):
    return {'id':'e-'+doc['id'],'doc':doc['id'],'page':doc['excerpt_page'],'label':doc['title'],
            'passage':doc['excerpt'],'context':doc['note']}


def live_data(store):
    checks=store.rows('checks');quotes=store.rows('quotes');events=store.rows('filings');latest_job=store.latest_job()
    companies=[];now=datetime.now(IST)
    window={'start':latest_job['start'],'end':latest_job['end']} if latest_job else {'start':(now.date()-timedelta(days=7)).isoformat(),'end':now.date().isoformat()}
    desired_session=latest_job.get('eod_date') if latest_job else None
    for holding in holdings():
        ticker=holding['ticker']
        related=sorted([c for c in checks if c['ticker']==ticker],key=lambda c:c['finished_at'],reverse=True)
        check=related[0] if related else None
        company_quotes=sorted([q for q in quotes if q['ticker']==ticker],key=lambda q:q['date'],reverse=True)
        quote=next((q for q in company_quotes if q['date']==desired_session),company_quotes[0] if company_quotes else None)
        market=market_stats(quote,company_quotes)
        covered=bool(check and check['filings_status']=='passed' and check['start']<=window['start'] and check['end']>=window['end'])
        failed=bool(check and (check['eod_status']!='passed' or not covered or (desired_session and (not quote or quote['date']!=desired_session))))
        companies.append({**holding,'quote':quote,'market':market,'coverage':'partial' if failed else 'saved' if check else 'missing',
                          'check':check,'windowCovered':covered,'filingCount':len([e for e in events if e['ticker']==ticker]),
                          'latestSuccessfulFilings':next((c for c in related if c['filings_status']=='passed'),None)})
    for event in events:reclassify(event)
    docs={};evidence={};latest_docs={}
    event_ids={e['id'] for e in events}
    for doc in sorted(store.rows('documents'),key=lambda d:d['checked_at']):
        if doc['event_id'] in event_ids:latest_docs[doc['event_id']]=doc
    for event in events:
        doc=latest_docs.get(event['id'])
        event['evidence']=None
        if doc and doc['status']=='ready':
            docs[doc['id']]=public_document(store,doc)
            ev=evidence_for(doc);evidence[ev['id']]=ev;event['evidence']=ev['id']
        elif doc:event['document_error']=doc.get('error')
    return {'mode':'live','now':now.isoformat(),'generatedAt':utcnow(),'window':window,'companies':companies,'events':events,
            'documents':docs,'evidence':evidence,'briefs':{},'job':latest_job,'activeJob':store.active_job(),
            'recovery':store.get('meta','recovery'),'storage':'ephemeral' if __import__('os').environ.get('FINN_EPHEMERAL')=='1' else 'local',
            'coverage':{'checked':sum(c['check'] is not None for c in companies),'passed':sum(c['check'] is not None and c['coverage']=='saved' for c in companies),
                        'failed':sum(c['coverage']=='partial' for c in companies),'notChecked':sum(c['check'] is None for c in companies),
                        'attachmentsReady':sum(d['status']=='ready' for d in latest_docs.values()),'attachmentsFailed':sum(d['status']!='ready' for d in latest_docs.values()),
                        'attachmentsNotRequested':len(events)-len(latest_docs)},
            'autoRefreshEnabled':__import__('os').environ.get('FINN_AUTO_REFRESH','1')=='1',
            'research':{r['ticker']:research_summary(r) for r in store.rows('research')},
            'kinds':KINDS,'model':model_status()}


BASELINE_SESSIONS=20
MIN_BASELINE=5


def market_stats(quote,company_quotes):
    """Volume versus the average of earlier stored sessions. Deterministic; no inference."""
    if not quote:return None
    prior=[q for q in company_quotes if q['date']<quote['date'] and isinstance(q.get('volume'),int)][:BASELINE_SESSIONS]
    average=sum(q['volume'] for q in prior)/len(prior) if prior else None
    ratio=quote['volume']/average if average else None
    return {'baseline_sessions':len(prior),'baseline_ready':len(prior)>=MIN_BASELINE,'min_baseline':MIN_BASELINE,
            'volume_avg':round(average) if average else None,'volume_ratio':round(ratio,2) if ratio is not None else None,
            'history':[{'date':q['date'],'close':q['close'],'volume':q['volume'],'change_pct':q.get('change_pct')} for q in reversed(([quote]+prior)[:11])]}


def reclassify(event):
    # Stored/snapshot filings carry the rule version they were fetched with; apply the current rules on read.
    c=classify(event.get('category'),event.get('description'))
    event.update(title=c['title'],priority=c['priority'],rule_id=RULE_VERSION+':'+c['rule'],reason=c['reason'],kind=c['kind'],score=c['score'])
    if 'attachment_fetchable' not in event:
        event['attachment_url']=event.get('url') or ''
        event['attachment_fetchable']=allowed_url(event['attachment_url'])
        if not event['attachment_fetchable']:event['url']=''
    return event


def research_summary(record):
    return {k:v for k,v in record.items() if k not in {'candidates','requests'}}
