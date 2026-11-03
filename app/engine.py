"""Bounded real refresh and explicit filing validation. No experiment/sample reads."""
import hashlib
import json
import re
import sys
import time
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from .adapters import IST, SourceClient, SourceError, announcements_url, eod_url, parse_announcements, parse_eod
from .store import utcnow

HERE=Path(__file__).resolve().parent
PDF_LOCK=threading.RLock()


def holdings():return json.loads((HERE/'holdings.json').read_text(encoding='utf-8'))


def configuration(tickers=None,start=None,end=None,asof=None):
    known={c['ticker'] for c in holdings()}
    symbols=list(dict.fromkeys(tickers or sorted(known)))
    if not symbols or not set(symbols).issubset(known):raise ValueError('Refresh symbols must be selected portfolio tickers')
    today=datetime.now(IST).date()
    finish=date.fromisoformat(end) if end else today
    begin=date.fromisoformat(start) if start else finish-timedelta(days=7)
    session=date.fromisoformat(asof) if asof else today-timedelta(days=1)
    if begin>finish or (finish-begin).days>14 or finish>today:raise ValueError('Use an announcement window of at most 15 calendar dates, ending no later than today in IST')
    if session>=today or session<today-timedelta(days=31):raise ValueError('EOD must be a prior completed calendar date within 31 days; today is deliberately excluded')
    return symbols,begin,finish,session


def eod_missing(error):
    text=str(error)
    return 'HTTP 404' in text or 'EOD date differs' in text


def backfill_history(store,client,tickers,session,wanted,began,max_requests=14,budget=200):
    """Fetch earlier official EOD files so volume can be compared with a recent average.

    Only sessions not already stored are requested; weekends are skipped, holidays (404 / date mismatch)
    are skipped, and any blocked/network failure stops the backfill without affecting the refresh."""
    stored={q['date'] for q in store.rows('quotes') if q['ticker'] in tickers}
    have=sorted(d for d in stored if d<session.isoformat())
    outcome={'wanted':wanted,'requested':0,'added':[],'skipped':[],'error':None}
    day=session;requests=0
    while len(have)<wanted and requests<max_requests and (session-day).days<45:
        day-=timedelta(days=1)
        if day.weekday()>=5 or day.isoformat() in stored:continue
        if time.monotonic()-began>budget:outcome['error']='Time budget reached; remaining history will be fetched on a later refresh';break
        requests+=1
        try:
            source,body=client.get(eod_url(day),'eod',limit=3_000_000)
            try:rows=parse_eod(body,day);store.validate_source(source['id'],True)
            except Exception as error:
                store.validate_source(source['id'],False,str(error));raise
        except SourceError as error:
            if eod_missing(error):outcome['skipped'].append(day.isoformat());continue
            outcome['error']=str(error);break
        for ticker in tickers:
            if ticker in rows:
                quote=rows[ticker]
                quote.update(id=ticker+':'+quote['date'],source_id=source['id'],source=source['final_url'],retrieved_at=source['retrieved_at'])
                store.put('quotes',quote['id'],quote,ticker=ticker,session=quote['date'])
        have.append(day.isoformat());outcome['added'].append(day.isoformat())
        time.sleep(.2)
    outcome['requested']=requests;outcome['sessions']=len(have)
    return outcome


def run_refresh(store,job,client=None,document_limit=2,history_sessions=10):
    client=client or SourceClient(store)
    if isinstance(client,SourceClient):client.job_id=job['id']
    began=time.monotonic();start=date.fromisoformat(job['start']);end=date.fromisoformat(job['end'])
    session=date.fromisoformat(job['requested_eod']);quotes={};eod_source=None;eod_error=None;inserted=0;updated=0
    try:
        # A file, not weekday assumptions, establishes a completed session. Holidays/weekends can fall back.
        for offset in range(5):
            candidate=session-timedelta(days=offset)
            try:
                eod_source,body=client.get(eod_url(candidate),'eod',limit=3_000_000)
                try:quotes=parse_eod(body,candidate);store.validate_source(eod_source['id'],True)
                except Exception as error:
                    store.validate_source(eod_source['id'],False,str(error));raise
                session=candidate;break
            except SourceError as error:
                eod_error=str(error)
                if getattr(error,'request_id',None):eod_source=store.get('sources',error.request_id)
                # An absent file, or NSE serving the previous session under a non-trading date (e.g. Sunday
                # returns Friday), warrants trying an older day; blocked/network sources do not.
                if not eod_missing(error):break
        job['eod_date']=session.isoformat() if quotes else None
        for ticker in job['tickers']:
            check=dict(id=job['id']+':'+ticker,job_id=job['id'],ticker=ticker,started_at=utcnow(),
                       start=job['start'],end=job['end'],eod_status='failed',filings_status='not_checked',filing_count=None,
                       eod_error=None,filings_error=None,eod_request_id=eod_source['id'] if eod_source else None,
                       announcements_url=announcements_url(ticker,start,end))
            if ticker in quotes:
                quote=quotes[ticker]
                quote.update(id=ticker+':'+quote['date'],source_id=eod_source['id'],source=eod_source['final_url'],retrieved_at=eod_source['retrieved_at'])
                store.put('quotes',quote['id'],quote,ticker=ticker,session=quote['date'])
                check.update(eod_status='passed',eod_date=quote['date'])
            else:check['eod_error']=eod_error or 'No EQ-series row for this ticker in the validated official file'
            try:
                if time.monotonic()-began>240:raise SourceError('Refresh job budget exhausted before this company; not a no-announcements result')
                source,body=client.get(check['announcements_url'],'announcements',limit=4_000_000)
                check['announcements_request_id']=source['id']
                try:events=parse_announcements(body,ticker,start,end);store.validate_source(source['id'],True)
                except Exception as error:
                    store.validate_source(source['id'],False,str(error));raise
                for event in events:
                    previous=store.get('filings',event['id'])
                    event.update(source_id=source['id'],retrieved_at=source['retrieved_at'],first_seen=previous['first_seen'] if previous else utcnow(),last_seen=utcnow())
                    store.put('filings',event['id'],event,ticker=ticker,published=event['published_at'])
                    if previous:updated+=1
                    else:inserted+=1
                check.update(filings_status='passed',filing_count=len(events))
            except Exception as error:
                check.update(filings_status='failed',filings_error=f'{type(error).__name__}: {error}')
                if getattr(error,'request_id',None):check['announcements_request_id']=error.request_id
            check['finished_at']=utcnow()
            store.put('checks',check['id'],check,ticker=ticker,job_id=job['id'])
            job['completed']+=1;store.save_job(job)
            time.sleep(.15)
        if quotes and history_sessions:
            # Extra context for volume alerts; it can never fail an otherwise successful refresh.
            try:job['eod_history']=backfill_history(store,client,job['tickers'],session,history_sessions,began)
            except Exception as error:job['eod_history']={'error':f'{type(error).__name__}: {error}'}
            store.save_job(job)
        candidates=[e for e in store.rows('filings') if e['ticker'] in job['tickers'] and job['start']<=e['date']<=job['end']]
        candidates.sort(key=lambda e:({'attention':2,'unreviewed':1,'routine':0}[e['priority']],e['published_at']),reverse=True)
        document_results=[]
        for event in candidates[:max(0,min(document_limit,3))]:
            if time.monotonic()-began>270:break
            document_results.append(ensure_document(store,event['id'],client=client,force=True))
        checks=[c for c in store.rows('checks') if c['job_id']==job['id']]
        passed=sum(c['eod_status']=='passed' and c['filings_status']=='passed' for c in checks)
        job.update(status='complete' if passed==len(job['tickers']) else 'partial',finished_at=utcnow(),
                   elapsed_seconds=round(time.monotonic()-began,3),companies_passed=passed,companies_failed=len(job['tickers'])-passed,
                   inserted=inserted,updated=updated,document_results=[{'event_id':d['event_id'],'status':d['status'],'error':d.get('error')} for d in document_results])
    except Exception as error:
        job.update(status='failed',finished_at=utcnow(),error=f'{type(error).__name__}: {error}')
    finally:store.save_job(job)
    return job


def pdf_module():
    try:import pymupdf
    except ImportError:
        local=HERE.parent/'tmp'/'pdf-render-tools'
        if not local.exists():raise SourceError('PDF text extraction dependency unavailable; original link remains available. Install app/requirements.txt.')
        sys.path.insert(0,str(local));import pymupdf
    return pymupdf


def ensure_document(store,event_id,client=None,force=False):
    with PDF_LOCK:return _ensure_document(store,event_id,client,force)


def _ensure_document(store,event_id,client=None,force=False):
    event=store.get('filings',event_id)
    if not event:raise ValueError('Unknown filing')
    existing=sorted([d for d in store.rows('documents') if d['event_id']==event_id],key=lambda d:d['checked_at'],reverse=True)
    if not force and existing and existing[0]['status']=='ready' and store.blob_path(existing[0]['sha256']).exists():return existing[0]
    # Failures are recorded, not converted into invented excerpts. Subsequent user action can retry.
    doc=dict(id=hashlib.sha256((event_id+utcnow()).encode()).hexdigest()[:24],event_id=event_id,ticker=event['ticker'],
             title=event['ticker']+' · '+event['title'],kind='Exchange filing',period='Period not inferred from metadata',date=event['date'],url=event['url'],
             status='failed',checked_at=utcnow(),pages=[],note='',pageCount=None)
    try:
        if not event.get('url'):
            raise SourceError('This announcement has no NSE-hosted attachment to download. Use the original source link.'
                              if event.get('attachment_url') else 'This announcement was filed as text only; there is no attachment to download.')
        source,body=(client or SourceClient(store)).get(event['url'],'filing-pdf',limit=25_000_000)
        doc.update(source_id=source['id'],retrieved=source['retrieved_at'],sha256=source['sha256'])
        try:
            if not body.startswith(b'%PDF-'):raise SourceError('Attachment is not a PDF; no passage extracted')
            if b'%%EOF' not in body[-4096:]:raise SourceError('PDF end-of-file marker is absent; incomplete/malformed response excluded')
            fitz=pdf_module()
            pdf=fitz.open(stream=body,filetype='pdf')
            if pdf.needs_pass:raise SourceError('PDF requires a password; no text extraction attempted')
            if pdf.page_count<1:raise SourceError('PDF contains no pages')
            if pdf.is_repaired:raise SourceError('PDF required structural repair; excluded pending review')
            pages=[dict(number=i+1,text=pdf[i].get_text(sort=False).strip()) for i in range(min(pdf.page_count,60))]
            name=next(c['name'] for c in holdings() if c['ticker']==event['ticker'])
            normalise=lambda s:re.sub('[^a-z0-9]','',s.casefold())
            # Use configured company identity, not generic corporate-finance words, to reject wrong PDFs.
            aliases={normalise(name),normalise(event.get('provider_company') or ''),normalise(event['ticker'])}
            aliases={a for a in aliases if len(a)>=4}
            identity_text=normalise(' '.join(p['text'] for p in pages[:4]))
            if not any(a in identity_text for a in aliases):raise SourceError('Company identity could not be verified in the first four PDF pages')
            text_pages=[p for p in pages if len(re.sub(r'\s','',p['text']))>=80]
            if not text_pages:raise SourceError('No usable text layer; scanned/OCR-required attachment. Original remains accessible.')
            chosen=text_pages[0]
            if 'transcript' in (event['category']+' '+event['description']).casefold():
                for index,page in enumerate(pages):
                    header=' '.join(page['text'][:700].split()).casefold()
                    if re.search(r'earnings (?:conference )?call',header) and not any(s in header for s in ['media conference','press conference','dear sir','please find enclosed']):
                        following=[p for p in pages[index:index+3] if len(p['text'])>800 and re.search(r'revenue|cash flow|operating margin',p['text'],re.I)]
                        if following:chosen=following[0];break
            elif ':results' in event['rule_id']:
                chosen=max(text_pages,key=lambda p:sum(word in p['text'].casefold() for word in ['consolidated','financial results','revenue','profit','quarter']))
            excerpt=' '.join(chosen['text'].split())
            # This is an extract, not a financial interpretation or automatically normalised table.
            if 'transcript' in event['description'].casefold():
                match=re.search(r'our revenue|revenue growth|good (?:morning|evening)',excerpt,re.I)
                if match:excerpt=excerpt[match.start():]
            excerpt=excerpt[:1800]
            doc.update(status='ready',pages=pages,pageCount=pdf.page_count,excerpt_page=chosen['number'],excerpt=excerpt,
                       identity_verified=True,note=f'Original text extracted from the actual exchange attachment; excerpt auto-selected. {len(pages)} of {pdf.page_count} PDF pages extracted. No AI summary or automatic financial-table normalisation.',
                       validation={'signature':True,'structure':'no repair required','company_identity':True,'text_layer':True,'numeric_table_validation':'not performed'})
            pdf.close();store.validate_source(source['id'],True)
        except Exception as error:
            store.validate_source(source['id'],False,str(error));raise
    except Exception as error:
        doc.update(error=f'{type(error).__name__}: {error}',note='Source retrieval/validation failed. No extracted passage is presented; use the original link or retry.')
        if getattr(error,'request_id',None):
            source=store.get('sources',error.request_id)
            doc.update(source_id=source['id'],retrieved=source['retrieved_at'])
    store.put('documents',doc['id'],doc,event_id=event_id,checked_at=doc['checked_at'])
    return doc
