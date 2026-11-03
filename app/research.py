"""Bounded, generic NSE document discovery and extractive research. No model/provider calls.

Source text is untrusted data: it is indexed/displayed verbatim, never executed as instructions.
There are no per-symbol answers or prepared PDF URLs. Issuer indexes are fallback discovery only.
"""
import csv
import hashlib
import io
import json
import math
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit, unquote

from .adapters import HOSTS, IST, SourceClient, SourceError, allowed_url, announcements_url, parse_announcements
from .engine import PDF_LOCK, pdf_module
from .store import utcnow

VERSION='pull-v1'
INDEX_VERSION=2
MASTER='https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv'
# Only public issuer INDEX pages. Generic NSE discovery always runs first.
ISSUER_INDEXES={
    'INFY':['https://www.infosys.com/investors/reports-filings/annual-report/'],
    'CERA':['https://www.cera-india.com/investor-relations/financial-information',
            'https://www.cera-india.com/investor-relations/events'],
    'APOLLOHOSP':['https://www.apollohospitals.com/investor-relations'],
}
STOP={'a','an','and','are','as','at','be','by','can','company','did','do','does','for','from','has','have','how','i','in','is','it','its','latest','me','of','on','or','s','the','their','this','to','was','were','what','which','with','about','show','say','tell','explain','please','they','us','these','those','would','could','should','any'}


def symbol(value):
    if not isinstance(value,str):raise ValueError('Enter an NSE ticker, for example INFY')
    value=value.strip().upper()
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9&-]{0,24}',value):raise ValueError('Use an NSE symbol without .NS, spaces or URL characters')
    return value


def normalise(value):return re.sub(r'[^a-z0-9]','',value.casefold())


def identity_matches(text,company):
    original=text;text=normalise(text)
    name=re.sub(r'\b(limited|ltd|private|pvt)\b','',company['name'],flags=re.I).strip()
    aliases={normalise(name),normalise(company['ticker'])}
    return any((len(a)>=4 and a in text) or (len(a)==3 and re.search(r'\b'+re.escape(a)+r'\b',original,re.I)) for a in aliases)


def annual_period_matches(text,start,end):
    start,end=str(start),str(end)
    year_range=re.search(r'\b'+start+r'\s*[-–/]\s*(?:'+end+'|'+end[-2:]+r')\b',text)
    year_ended=re.search(r'(?:financial\s+year|year)\s+ended\s+(?:on\s+)?(?:31(?:st)?\s+March|March\s+31(?:st)?),?\s+'+end+r'\b',text,re.I)
    return bool(year_range or year_ended)


def parse_master(body,ticker):
    reader=csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
    if not {'SYMBOL','NAME OF COMPANY'}.issubset(reader.fieldnames or []):raise SourceError('NSE symbol master lacks expected CSV columns')
    for row in reader:
        row={k.strip():v.strip() for k,v in row.items()}
        if row['SYMBOL']==ticker:
            return {'ticker':ticker,'name':row['NAME OF COMPANY'],'isin':row.get('ISIN NUMBER'),'series':row.get('SERIES')}
    raise ValueError('Ticker not found in the current NSE equities list. SME/delisted coverage is not established; no company identity has been guessed.')


def parse_annual(body,company):
    value=json.loads(body)
    rows=value.get('data') if isinstance(value,dict) else None
    if not isinstance(rows,list):raise SourceError('Annual-report index is not a data list')
    result=[]
    for raw in rows:
        if not identity_matches(raw.get('companyName',''),company):raise SourceError('Annual-report index company identity mismatch')
        url=raw.get('fileName','')
        if not allowed_url(url):continue
        try:
            finish=int(raw['toYr']);start=int(raw['fromYr'])
            if finish-start!=1:continue
        except (ValueError,KeyError,TypeError):continue
        try:published=datetime.strptime(raw['broadcast_dttm'],'%d-%b-%Y %H:%M:%S').replace(tzinfo=IST).isoformat()
        except (ValueError,KeyError):published=''
        result.append({'kind':'annual','url':url,'label':f'Annual report FY {start}-{str(finish)[-2:]}',
                       'period':f'FY {start}-{str(finish)[-2:]}','year_start':start,'year_end':finish,'published_at':published,
                       'revision':str(raw.get('submission_type','unknown')),'state':'discovered'})
    return sorted(result,key=lambda r:(r['year_end'],r['published_at']),reverse=True)


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='a':self.current={'url':dict(attrs).get('href',''),'text':''}
    def handle_data(self,text):
        if self.current is not None:self.current['text']+=text+' '
    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None:self.links.append(self.current);self.current=None


def call_sections(pages):
    """Exclude letters and press/media sections, including mixed bundles such as INFY."""
    active=False;selected=[];starts=[]
    for p in pages:
        head=' '.join(p['text'][:1100].split()).casefold()
        cover=bool(re.search(r'dear sir|dear madam|please find (?:enclosed|attached)|stock exchange',head)) and len(p['text'])<5000
        title=bool(re.search(r'(earnings|results|q[1-4]|quarter).*?(?:conference\s+call|earnings\s+call)',head))
        press=bool(re.search(r'(press|media)\s+(?:conference|call)',head[:500]))
        if press:active=False
        elif title and not cover:
            if not active:starts.append(p['number'])
            active=True
        if active and not cover and not press:selected.append(p['number'])
    chosen=[p for p in pages if p['number'] in selected]
    text='\n'.join(p['text'] for p in chosen)
    # A notice can contain "earnings call"; actual dialogue must also be present.
    dialogue=len(re.findall(r'\bModerator\b|\b(?:Question.and.Answer|Q&A)\b|\b[A-Z][a-z]+\s+[A-Z][a-z]+\s*:',text))>=3
    if len(text)<3000 or not dialogue:return [],'No actual earnings-call dialogue verified; notice, press conference or cover letter is not a transcript'
    return selected,None


def call_period(pages):
    head=' '.join(p['text'][:2000] for p in pages[:3])
    match=re.search(r'\bQ([1-4])\s*(?:[-–]\s*)?(?:FY\s*[\x27’]?\s*)?(20\d{2}|\d{2})(?:\s*[-–/]\s*(\d{2,4}))?',head,re.I)
    if match:
        year=match.group(3) or match.group(2)
        if len(year)==2:year='20'+year
        return f'Q{match.group(1)} FY{year}'
    match=re.search(r'(first|second|third|fourth)\s+quarter.*?(20\d{2})',head,re.I)
    if match:return f"Q{['first','second','third','fourth'].index(match.group(1).lower())+1} FY{match.group(2)}"
    return 'Period not verified from transcript heading'


def published_pdf_links(pages,annotations,hosts):
    # Many exchange letters print URLs across lines without PDF link annotations.
    text='\n'.join(p['text'] for p in pages[:3])
    printed=re.findall(r'https://[^\s<>()]+(?:[ \t]*\r?\n[ \t]*[A-Za-z0-9_./%?=&+#~-]+)*?\.pdf(?:\?[^\s<>()]*)?',text,re.I)
    urls=[re.sub(r'\s+','',u) for u in printed]+annotations
    return list(dict.fromkeys(u for u in urls if '.pdf' in u.lower() and allowed_url(u,hosts)))


def page_context(text):
    basis=[]
    for value in ['standalone','consolidated']:
        if re.search(r'\b'+value+r'\b',text[:1800],re.I):basis.append(value)
    units=[]
    for pattern in [r'(?:INR|Rs\.?|₹|rupees)\s*(?:in\s*)?(?:crores?|lakhs?|lacs?|millions?|billions?)',
                    r'(?:USD|US\$|dollars)\s*(?:in\s*)?(?:millions?|billions?)']:
        units.extend(m.group(0) for m in re.finditer(pattern,text,re.I))
    return {'basis':', '.join(basis) or 'Not established on this page','units':'; '.join(dict.fromkeys(units)) or 'Read original passage/table; units not normalised'}


def document_note(doc):
    exclusion=' Cover letters and press/media sections are excluded from call search.' if doc['source_kind']=='call' else ''
    return f"{doc['pageCount']} PDF pages extracted; {len(doc['indexed_pages'])} text-bearing pages indexed.{exclusion} No OCR or financial-table normalisation. Printed page numbers can differ from physical PDF pages."


def index_document(store,doc):
    selected=set(doc.get('indexed_pages',[]));rows=[]
    for page in doc['pages']:
        if page['number'] not in selected:continue
        text=page['text']
        # Overlapping character windows retain original line structure and physical PDF page.
        start=0
        while start<len(text):
            end=min(start+1850,len(text))
            if end<len(text):end=max(text.rfind('\n',start+1200,end),text.rfind(' ',start+1500,end),start+1500)
            chunk=text[start:end].strip()
            if len(chunk)<80:break
            cid=f"r-{doc['id']}-{page['number']}-{start}"
            rows.append((doc['id'],doc['ticker'],page['number'],cid,chunk))
            if end==len(text):break
            overlap=text.rfind('\n',start+1,end-250)
            start=overlap+1 if overlap>start else end
    with store.connect() as db:
        db.execute('DELETE FROM research_chunks WHERE doc_id=?',(doc['id'],))
        db.executemany('INSERT INTO research_chunks(doc_id,ticker,page,chunk_id,text) VALUES(?,?,?,?,?)',rows)
    doc['index_version']=INDEX_VERSION
    return len(rows)


def rank_chunks(rows,terms,total):
    """Document-local lexical scoring: adding another ticker cannot change this ranking."""
    prepared=[];frequency=Counter()
    for row in rows:
        words=re.findall(r'[a-z0-9]+',row['text'].casefold());counts=Counter(words)
        frequency.update(t for t in terms if counts[t])
        prepared.append((row,counts,len(words)))
    average=sum(n for _,_,n in prepared)/len(prepared) if prepared else 1
    scored=[]
    for row,counts,length in prepared:
        score=0
        for term in terms:
            tf=counts[term]
            if tf:
                weight=math.log(1+(max(total,len(rows))-frequency[term]+.5)/(frequency[term]+.5))
                score+=weight*(tf*2.2)/(tf+1.2*(.25+.75*length/max(1,average)))
        scored.append((score,row))
    return [row for score,row in sorted(scored,key=lambda x:(-x[0],int(x[1]['page']),x[1]['chunk_id']))]


def download_document(store,company,candidate,client):
    stamp=utcnow()
    doc={'id':hashlib.sha256((candidate['url']+stamp).encode()).hexdigest()[:24],
         'event_id':'research:'+company['ticker']+':'+candidate['kind'],'scope':'research','ticker':company['ticker'],
         'company':company['name'],'title':company['ticker']+' · '+candidate['label'],'kind':'Annual report' if candidate['kind']=='annual' else 'Earnings-call transcript',
         'source_kind':candidate['kind'],'period':candidate.get('period','Not yet verified'),'date':candidate.get('published_at','')[:10],
         'url':candidate['url'],'status':'failed','checked_at':stamp,'pages':[],'indexed_pages':[],'pageCount':None,
         'discovered_from':candidate.get('discovered_from'),'discovery_source_id':candidate.get('discovery_source_id'),
         'revision':candidate.get('revision'),'note':''}
    try:
        source,body=client.get(candidate['url'],'research-'+candidate['kind']+'-pdf',limit=40_000_000)
        doc.update(source_id=source['id'],retrieved=source['retrieved_at'],sha256=source['sha256'])
        try:
            if not body.startswith(b'%PDF-') or b'%%EOF' not in body[-4096:]:raise SourceError('Incomplete/non-PDF source: signature or EOF missing')
            with PDF_LOCK:
                fitz=pdf_module()
                with fitz.open(stream=body,filetype='pdf') as pdf:
                    if pdf.needs_pass or pdf.is_repaired or not 1<=pdf.page_count<=800:raise SourceError('Encrypted, structurally repaired or over-800-page PDF excluded')
                    doc['pageCount']=pdf.page_count
                    pages=[{'number':i+1,'text':pdf[i].get_text(sort=False).strip()} for i in range(pdf.page_count)]
                    linked=[link.get('uri','') for page in list(pdf)[:3] for link in page.get_links()]
            first='\n'.join(p['text'] for p in pages[:6])
            if not identity_matches(first,company):raise SourceError('PDF company identity does not match NSE company metadata')
            usable=[p['number'] for p in pages if len(re.sub(r'\s','',p['text']))>=80]
            if len(usable)<max(1,len(pages)*.5):raise SourceError('Insufficient text coverage; OCR-required or malformed PDF excluded')
            doc['linked_pdfs']=published_pdf_links(pages,linked,client.hosts)
            if candidate['kind']=='call':
                selected,error=call_sections(pages)
                if error:
                    doc['status']='cover-letter' if len(pages)<=3 else 'not-a-call'
                    doc['note']=error;doc['error']=error
                    store.validate_source(source['id'],False,error)
                    store.put('documents',doc['id'],doc,event_id=doc['event_id'],checked_at=stamp)
                    return doc
                chosen=[p for p in pages if p['number'] in selected]
                doc['period']=call_period(chosen)
                # Publication is not the call date. Heading date is retained separately when parseable.
                head=' '.join(p['text'][:2200] for p in chosen[:3])
                found=re.search(r'\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})',head,re.I)
                if not found:found=re.search(r'\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December),?\s+(20\d{2})',head,re.I)
                call_day=None
                if found:
                    raw=found.group(0).replace(',','')
                    for fmt in ['%B %d %Y','%d %B %Y']:
                        try:call_day=datetime.strptime(raw,fmt).date();break
                        except ValueError:pass
                doc['call_date']=call_day.isoformat() if call_day else None
                age=(datetime.now(IST).date()-call_day).days if call_day else None
                doc['freshness']='stale' if age is not None and age>180 else 'dated' if age is not None else 'date-unverified'
            else:
                selected=usable
                end=str(candidate.get('year_end',''));start=str(candidate.get('year_start',int(end)-1 if end else 0))
                doc['period_verified']=bool(end and annual_period_matches(first,start,end))
                if not doc['period_verified']:raise SourceError('Annual-report financial year could not be checked against first six pages')
                today=datetime.now(IST).date();expected=today.year if today.month>=4 else today.year-1
                doc['freshness']='older-report' if candidate.get('year_end',0)<expected else 'dated'
            doc.update(status='ready',pages=pages,indexed_pages=[n for n in selected if n in usable],
                       excerpt_page=selected[0],identity_verified=True,extracted_page_count=len(pages))
            doc['note']=document_note(doc)
            doc['excerpt']=pages[selected[0]-1]['text'][:1850]
            doc['chunks']=index_document(store,doc)
            store.validate_source(source['id'],True)
        except Exception as error:
            store.validate_source(source['id'],False,str(error));raise
    except Exception as error:
        doc.update(status='blocked' if '403' in str(error) else 'failed',error=str(error),note='Retrieval/validation failed; no text indexed.',pages=[],indexed_pages=[])
        if getattr(error,'request_id',None):doc['source_id']=error.request_id
    store.put('documents',doc['id'],doc,event_id=doc['event_id'],checked_at=stamp)
    return doc


def cached_record(store,ticker):
    record=store.get('research',ticker)
    if record and record.get('version')==VERSION and record.get('status') in ('ready','partial'):
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(record['checked_at'])).total_seconds()
        if age<86400:return record
    return None


def begin_research(store,ticker,force=False):
    ticker=symbol(ticker)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT payload FROM meta WHERE id='research-active'").fetchone()
        active=json.loads(row['payload']) if row else None
        # A company whose sources are already stored is served immediately, even while another company loads.
        if not force and not (active and active.get('ticker')==ticker and active['status']=='running'):
            cached=cached_record(store,ticker)
            if cached:return cached,True
        if active and active['status']=='running' and active['expires_at']>utcnow():return active,True
        if active and active['status']=='running':
            active.update(status='interrupted',error='Research lease expired; load sources again to retry')
            db.execute('UPDATE meta SET payload=? WHERE id=?',(json.dumps(active),'research-job:'+active['id']))
        if not force:
            cached=cached_record(store,ticker)
            if cached:return cached,True
        job={'id':uuid.uuid4().hex,'ticker':ticker,'version':VERSION,'status':'running','progress':'Validating NSE ticker',
             'started_at':utcnow(),'checked_at':utcnow(),'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=8)).isoformat(),
             'documents':[],'candidates':[],'requests':[],'errors':[],'warnings':[]}
        db.execute("INSERT INTO meta(id,payload) VALUES('research-active',?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",(json.dumps(job),))
    store.put('meta','research-job:'+job['id'],job)
    return job,False


def save_progress(store,job,message=None):
    if message:job['progress']=message
    store.put('meta','research-active',job);store.put('meta','research-job:'+job['id'],job)


def research_job(store,job_id):
    job=store.get('meta','research-job:'+job_id)
    if job and job['status']=='running' and job['expires_at']<utcnow():
        job.update(status='interrupted',error='Research lease expired; available sources are retained. Load sources to retry.')
        store.put('meta','research-job:'+job_id,job)
    return job


def run_research(store,job,client=None):
    ticker=job['ticker'];started=time.monotonic();today=datetime.now(IST).date()
    hosts=HOSTS|{urlsplit(u).hostname for u in ISSUER_INDEXES.get(ticker,[])}
    client=client or SourceClient(store,timeout=45,hosts=hosts)
    client.job_id=job['id'];job['requests']=[]
    def fetch(url,kind):
        if time.monotonic()-started>240:raise SourceError('Four-minute discovery budget exceeded; available validated sources retained')
        try:
            source,body=client.get(url,kind)
            job['requests'].append(source['id']);return source,body
        except SourceError as error:
            if error.request_id:job['requests'].append(error.request_id)
            raise
    def use(candidate):
        save_progress(store,job,'Validating '+candidate['label'])
        if time.monotonic()-started>240:return False
        doc=download_document(store,job['company'],candidate,client)
        candidate.update(state=doc['status'],document_id=doc['id'],error=doc.get('error'))
        if doc.get('source_id'):job['requests'].append(doc['source_id'])
        if doc['status']=='ready':job['documents'].append(doc['id']);return True
        # Follow published links only to the same explicit official-source host registry.
        if candidate['kind']=='call':
            for url in doc.get('linked_pdfs',[])[:2]:
                if url==candidate['url']:continue
                follow={**candidate,'url':url,'discovered_from':candidate['url'],'discovery_source_id':doc.get('source_id'),'state':'discovered'}
                job['candidates'].append(follow)
                child=download_document(store,job['company'],follow,client)
                follow.update(state=child['status'],document_id=child['id'],error=child.get('error'))
                if child.get('source_id'):job['requests'].append(child['source_id'])
                if child['status']=='ready':job['documents'].append(child['id']);return True
        return False
    try:
        master=store.get('meta','research-master')
        if master and (datetime.now(timezone.utc)-datetime.fromisoformat(master['retrieved_at'])).total_seconds()<86400 and store.blob_path(master['sha256']).exists():
            source=master;body=store.blob_path(master['sha256']).read_bytes()
            job['master_cache_reused']=True
        else:
            source,body=fetch(MASTER,'research-symbol-master')
            # Validate format independently of whether the requested symbol exists.
            if not body.startswith(b'SYMBOL,NAME OF COMPANY,'):raise SourceError('Unexpected NSE symbol-master format')
            store.validate_source(source['id'],True);store.put('meta','research-master',source)
        job['company']=dict(parse_master(body,ticker),source_id=source['id'],retrieved_at=source['retrieved_at'])
        annual_ready=False;call_ready=False
        save_progress(store,job,'Discovering annual reports from NSE')
        annual_url='https://www.nseindia.com/api/annual-reports?'+urlencode({'index':'equities','symbol':ticker})
        try:
            source,body=fetch(annual_url,'research-annual-index');annual=parse_annual(body,job['company'])
            store.validate_source(source['id'],True)
            for c in annual[:4]:
                c.update(discovered_from=annual_url,discovery_source_id=source['id']);job['candidates'].append(c)
            for c in job['candidates'][:]:
                if c['kind']=='annual' and use(c):annual_ready=True;break
            if annual_ready:
                picked=next(c for c in job['candidates'] if c['state']=='ready')
                if any(c['state'] in ('failed','blocked') for c in job['candidates'][:job['candidates'].index(picked)]):
                    job['warnings'].append('A newer/revised annual candidate failed. The selected earlier submission is a fallback; inspect candidate history.')
        except Exception as error:job['errors'].append('Annual index: '+str(error))
        # Four disjoint 90-day windows: bounded history, not a claim of complete exchange coverage.
        for offset in range(4):
            end=today-timedelta(days=offset*90);start=end-timedelta(days=89)
            save_progress(store,job,f'Discovering actual calls: {start} to {end}')
            url=announcements_url(ticker,start,end)
            try:
                source,body=fetch(url,'research-announcements');events=parse_announcements(body,ticker,start,end)
                store.validate_source(source['id'],True)
                relevant=[e for e in events if re.search(r'transcript|earnings.*call|conference.*call',e['category']+' '+e['description'],re.I)]
                relevant.sort(key=lambda e:e['published_at'],reverse=True)
                attempts=0
                for e in relevant:
                    actual=bool(re.search('transcript',e['category']+' '+e['description'],re.I))
                    c={'kind':'call','url':e['url'],'label':e['description'],'published_at':e['published_at'],
                       'discovered_from':url,'discovery_source_id':source['id'],'state':'discovered' if actual else 'notice-not-transcript'}
                    job['candidates'].append(c)
                    if actual and attempts<3:
                        attempts+=1
                        if use(c):call_ready=True;break
                if call_ready:break
            except Exception as error:job['errors'].append(f'Announcements {start}/{end}: {error}')
            if time.monotonic()-started>240:break
        if not (annual_ready and call_ready):
            for url in ISSUER_INDEXES.get(ticker,[]):
                save_progress(store,job,'Checking issuer index fallback')
                try:
                    source,body=fetch(url,'research-issuer-index');parser=Links();parser.feed(body.decode('utf-8',errors='replace'))
                    store.validate_source(source['id'],True);candidates=[]
                    for link in parser.links:
                        target=urljoin(url,link['url']);label=unquote(target)+' '+link['text']
                        kind='call' if re.search(r'transcript',label,re.I) and not call_ready else 'annual' if re.search(r'annual.?report|ar-\d\d\.pdf',label,re.I) and not annual_ready else None
                        if not kind or '.pdf' not in target.lower() or not allowed_url(target,hosts):continue
                        years=re.findall(r'20\d{2}',label);year=max(map(int,years),default=0)
                        if year>today.year:continue
                        candidates.append({'kind':kind,'url':target,'label':link['text'].strip() or kind+' report',
                            'published_at':'','year_end':year,'period':f'FY ending {year}' if year else 'Year not verified',
                            'discovered_from':url,'discovery_source_id':source['id'],'state':'discovered'})
                    candidates.sort(key=lambda c:(c['year_end'],c['url']),reverse=True)
                    for c in candidates[:4]:
                        if (c['kind']=='call' and call_ready) or (c['kind']=='annual' and annual_ready):continue
                        job['candidates'].append(c)
                        if use(c):
                            if c['kind']=='call':call_ready=True
                            else:annual_ready=True
                except Exception as error:job['errors'].append('Issuer fallback: '+str(error))
                if annual_ready and call_ready:break
        for kind,ready in [('annual report',annual_ready),('actual earnings call',call_ready)]:
            if not ready:job['warnings'].append('No usable '+kind+' found within bounded discovery. This is a discovery/availability gap, not evidence that none exists.')
        for doc_id in job['documents']:
            doc=store.get('documents',doc_id)
            if doc.get('freshness') in ('stale','older-report','date-unverified'):
                job['warnings'].append(doc['title']+': '+doc['freshness']+'. Review the document period/date; this is not verified current commentary.')
        job['status']='ready' if annual_ready and call_ready and not job['warnings'] and not job['errors'] else 'partial'
    except ValueError as error:job.update(status='invalid',error=str(error))
    except Exception as error:job.update(status='failed',error=str(error))
    job.update(checked_at=utcnow(),seconds=round(time.monotonic()-started,3),progress='Finished; inspect source coverage',model={'available':False,'reason':'Extractive retrieval only. Synthesis is not configured.'})
    store.put('research',ticker,job);save_progress(store,job)
    return job


def retrieve(store,ticker,question):
    ticker=symbol(ticker)
    if not isinstance(question,str) or not 3<=len(question.strip())<=500:raise ValueError('Enter a question of 3–500 characters')
    record=store.get('research',ticker)
    if not record:raise ValueError('Load this company’s source documents first')
    doc_ids=record['documents'];docs=[store.get('documents',i) for i in doc_ids]
    docs=[d for d in docs if d and d['status']=='ready']
    # Indexes are derived; rebuilding after snapshot recovery performs no source/model call.
    with store.connect() as db:
        counts={r['doc_id']:r['n'] for r in db.execute('SELECT doc_id,count(*) n FROM research_chunks WHERE ticker=? GROUP BY doc_id',(ticker,))}
    for doc in docs:
        if not counts.get(doc['id']) or doc.get('index_version')!=INDEX_VERSION:
            if doc['source_kind']=='call':doc['period']=call_period([p for p in doc['pages'] if p['number'] in doc['indexed_pages']])
            doc['chunks']=index_document(store,doc)
            store.put('documents',doc['id'],doc,event_id=doc['event_id'],checked_at=doc['checked_at'])
        if doc.get('scope')=='research' and doc.get('extracted_page_count')!=len(doc['pages']):
            doc['extracted_page_count']=len(doc['pages']);doc['note']=document_note(doc)
            store.put('documents',doc['id'],doc,event_id=doc['event_id'],checked_at=doc['checked_at'])
    tokens=[t for t in re.findall(r'[a-z0-9]+',question.casefold()) if t not in STOP and t.casefold()!=ticker.casefold()]
    expanded=set(tokens)
    if any(t in tokens for t in ['business','segments','products','services','sell']):expanded.update(['business','segments','products','services','customers'])
    if any(t in tokens for t in ['outlook','guidance','demand','management']):expanded.update(['outlook','guidance','demand','growth'])
    if any(t in tokens for t in ['cash','conversion','cashflow']):expanded.update(['cash','operating','receivables'])
    if not expanded:return {'ticker':ticker,'question':question,'passages':[],'documents':[],'notice':'No specific searchable terms. Ask about business, cash flow or management outlook.','model':{'available':False}}
    match=' OR '.join('"'+t+'"' for t in sorted(expanded)[:24])
    hits=[]
    # Balance report/call evidence rather than letting the long annual report dominate.
    for doc in docs:
        with store.connect() as db:
            rows=db.execute('SELECT page,chunk_id,text FROM research_chunks WHERE research_chunks MATCH ? AND doc_id=?',(match,doc['id'])).fetchall()
        rows=rank_chunks(rows,expanded,doc.get('chunks',len(rows)))
        seen=set()
        for row in rows:
            page=int(row['page'])
            if page in seen:continue
            seen.add(page)
            hits.append({'id':row['chunk_id'],'doc':doc['id'],'ticker':ticker,'company':doc['company'],'page':page,
                'label':doc['title']+f' · PDF p. {page}','passage':row['text'],'context':doc['note'],
                'period':doc['period'],'source_url':doc['url'],'sha256':doc['sha256'],'freshness':doc.get('freshness'),
                **page_context(doc['pages'][page-1]['text'])})
            if len(seen)>=3:break
    from .views import public_document
    return {'ticker':ticker,'question':question,'passages':hits,'documents':[public_document(store,d) for d in docs],
            'checked_at':record['checked_at'],'coverage_status':record['status'],'warnings':record['warnings'],
            'notice':'Relevant original passages ranked by lexical search, not an answer or factual synthesis. Missing/contradictory evidence is not resolved automatically.',
            'model':{'available':False,'reason':'Synthesis unavailable; no model call.'}}
