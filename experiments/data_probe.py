"""Read-only FINN feasibility experiments. Not application code.
Uses ordinary public HTTPS requests; no cookies, proxies, challenges or retries.
"""
import argparse, csv, hashlib, io, json, re, sys, time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'samples'
OUT.mkdir(exist_ok=True)

def now(): return datetime.now(timezone.utc).isoformat()

def fetch(url, label):
    manifest=OUT/'requests.jsonl'
    if manifest.exists():
        for line in reversed(manifest.read_text(encoding='utf-8').splitlines()):
            old=json.loads(line)
            if old['requested_url']==url and old.get('ok') and (ROOT/old['file']).exists():
                data=(ROOT/old['file']).read_bytes()
                if hashlib.sha256(data).hexdigest()==old['sha256']:
                    print('CACHE_REUSE',label,old['file'],flush=True)
                    return old,data
    start = now(); t = time.monotonic()
    row = dict(label=label, requested_url=url, retrieved_at_utc=start)
    data = b''
    try:
        req = Request(url, headers={'User-Agent': 'FINN-Recruitment-Feasibility/0.1', 'Accept': '*/*'})
        with urlopen(req, timeout=25) as r:
            data = r.read(35_000_001)
            row.update(status=r.status, final_url=r.url, content_type=r.headers.get('Content-Type'))
        if len(data)>35_000_000: raise ValueError('download size exceeds 35 MB cap')
        row['ok'] = True
    except HTTPError as e:
        row.update(ok=False, status=e.code, error=str(e)); data=e.read(20000)
    except Exception as e: row.update(ok=False,error=f'{type(e).__name__}: {e}')
    row.update(seconds=round(time.monotonic()-t,3),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    ext='.pdf' if data.startswith(b'%PDF') else '.json' if data.lstrip().startswith((b'{',b'[')) else '.bin'
    filename=re.sub(r'[^A-Za-z0-9_.-]','_',label)+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+ext
    (OUT/filename).write_bytes(data); row['file']=str((OUT/filename).relative_to(ROOT))
    with (OUT/'requests.jsonl').open('a',encoding='utf-8') as f: f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
    return row,data

class Links(HTMLParser):
    def __init__(self): super().__init__();self.rows=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            a=dict(attrs);self.current={'href':a.get('href',''),'text':''}
    def handle_data(self,d):
        if self.current is not None:self.current['text']+=d+' '
    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None:self.rows.append(self.current);self.current=None

def links(data,url):
    p=Links();p.feed(data.decode('utf-8',errors='replace'))
    return [dict(url=urljoin(url,x['href']),text=' '.join(x['text'].split())) for x in p.rows if x['href']]

def prices(ticker,asof):
    u=f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.NS?'+urlencode(dict(range='1mo',interval='1d',events='history'))
    r,b=fetch(u,ticker+'-yahoo-chart')
    if not r.get('ok'):return
    try:
        v=json.loads(b)['chart']['result'][0];q=v['indicators']['quote'][0];rows=[]
        for i,ts in enumerate(v['timestamp']):
            date=datetime.fromtimestamp(ts,timezone.utc).strftime('%Y-%m-%d')
            if date>asof:continue
            rows.append(dict(date=date,close=q['close'][i],volume=q['volume'][i]))
        result=dict(ticker=ticker,currency=v['meta'].get('currency'),exchange_timezone=v['meta'].get('exchangeTimezoneName'),asof=asof,source_request=r,raw_close_not_adjusted=True,observations=rows)
        (OUT/f'{ticker}-prices.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print('PRICE_OBSERVATIONS',ticker,json.dumps(rows[-3:]),flush=True)
    except Exception as e: print('PARSE_FAIL',ticker,str(e),flush=True)

def exchange(ticker,start,end):
    u='https://www.nseindia.com/api/corporate-announcements?'+urlencode(dict(index='equities',symbol=ticker,from_date=start,to_date=end))
    fetch(u,ticker+'-nse-announcements')

def discover(ticker,seeds):
    rows=[]
    for i,u in enumerate(seeds):
        r,b=fetch(u,f'{ticker}-discovery-{i}')
        if r.get('ok'):
            for x in links(b,r.get('final_url',u)):
                if re.search(r'\.pdf|annual|transcript|quarter|earning|financial|presentation|events|shareholder',x['url']+' '+x['text'],re.I):
                    rows.append(dict(**x,discovered_from=u))
        time.sleep(.25)
    seen=set();rows=[x for x in rows if not (x['url'] in seen or seen.add(x['url']))]
    old=OUT/f'{ticker}-links.json'
    if old.exists():
        prev=json.loads(old.read_text());known={x['url'] for x in rows};rows+= [x for x in prev if x['url'] not in known]
    old.write_text(json.dumps(rows,indent=2),encoding='utf-8')
    print('DISCOVERED',ticker,len(rows),flush=True)

def extract(path):
    sys.path.insert(0,str(ROOT.parent/'tmp/pdf-render-tools'))
    import pymupdf
    if Path(str(path)+'.text.json').exists():return
    pymupdf.TOOLS.mupdf_display_errors(False)
    pymupdf.TOOLS.mupdf_display_warnings(False)
    pymupdf.TOOLS.mupdf_warnings(reset=True)
    doc=pymupdf.open(path);pages=[]
    for n in range(len(doc)):
        try: pages.append(dict(pdf_page=n+1,text=doc[n].get_text(sort=False)))
        except Exception as e:pages.append(dict(pdf_page=n+1,text='',error=str(e)))
    dest=Path(str(path)+'.text.json');dest.write_text(json.dumps(pages,ensure_ascii=False,indent=2),encoding='utf-8')
    warnings=pymupdf.TOOLS.mupdf_warnings(reset=True)
    summary=dict(file=str(path),pdf_pages=len(doc),text_pages=sum(len(re.sub(r'\s','',p['text']))>=50 for p in pages),warning_chars=len(warnings),warning_excerpt=warnings[:300])
    with (OUT/'extractions.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(summary)+'\n')
    print('EXTRACTION_QUALITY',json.dumps(summary),flush=True)
    print('EXTRACT',str(path),len(doc),'pages',sum(len(p['text']) for p in pages),'characters',flush=True)

def documents(ticker,kind,limit,offset=0):
    if kind=='filing':
        src=sorted(OUT.glob(ticker+'-nse-announcements-*.json'))[-1]
        data=json.loads(src.read_text());rows=[dict(url=x['attchmntFile'],text=x['desc']+' '+x['attchmntText'],discovered_from=str(src)) for x in data if x.get('attchmntFile')]
        rows.sort(key=lambda x:not bool(re.search('financial|transcript',x['text'],re.I)))
    else:
        rows=json.loads((OUT/f'{ticker}-links.json').read_text())
        if kind=='transcript':
            for src in sorted(OUT.glob(ticker+'-nse-announcements-*.json'),reverse=True):
                for x in json.loads(src.read_text()):
                    if x.get('attchmntFile') and re.search('transcript',x['attchmntText'],re.I):
                        rows.append(dict(url=x['attchmntFile'],text=x['attchmntText'],discovered_from=str(src)))
        pattern=r'transcript|earningscall\.pdf' if kind=='transcript' else r'annual.?report|annualreport|annual-report|ar-\d\d\.pdf'
        rows=[x for x in rows if '.pdf' in x['url'].lower() and re.search(pattern,unquote(x['url'])+' '+x['text'],re.I)]
        if kind=='transcript':rows.sort(key=lambda x: 'press-conference' in x['url'])
    selected=rows[offset:offset+limit]
    for i,x in enumerate(selected):
        r,b=fetch(x['url'],f'{ticker}-{kind}-{i}')
        record=dict(ticker=ticker,kind=kind,candidate=x,request=r,is_pdf=b.startswith(b'%PDF'))
        with (OUT/'documents.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(record)+'\n')
        if r.get('ok') and record['is_pdf']:extract(ROOT/r['file'])
    if not selected: print('NO_CANDIDATES',ticker,kind,flush=True)

def resolve_pdf(path):
    sys.path.insert(0,str(ROOT.parent/'tmp/pdf-render-tools'))
    import pymupdf
    doc=pymupdf.open(path);urls=[]
    for page in doc:
        for link in page.get_links():
            u=link.get('uri','')
            if u.startswith('https://') and '.pdf' in u.lower() and u not in urls:urls.append(u)
        # Some exchange cover letters print the URL without a clickable annotation.
        compact=re.sub(r'\s+','',page.get_text())
        for u in re.findall(r'https://.*?\.pdf',compact):
            if u not in urls:urls.append(u)
    Path(str(path)+'.references.json').write_text(json.dumps(urls,indent=2))
    for i,u in enumerate(urls[:2]):
        r,b=fetch(u,Path(path).stem+'-reference-'+str(i))
        if r.get('ok') and b.startswith(b'%PDF'):extract(ROOT/r['file'])
    print('PDF_REFERENCES',json.dumps(urls),flush=True)

def official_eod(tickers,asof):
    stamp=datetime.strptime(asof,'%Y-%m-%d').strftime('%d%m%Y')
    url=f'https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{stamp}.csv'
    r,b=fetch(url,'NSE-EOD-'+asof)
    if not r.get('ok'):return
    rows=[]
    for row in csv.DictReader(io.StringIO(b.decode('utf-8-sig'))):
        row={k.strip():v.strip() for k,v in row.items()}
        if row.get('SYMBOL') in tickers and row.get('SERIES')=='EQ':rows.append(row)
    result=dict(source_request=r,asof=asof,price_unit='INR/share',volume_unit='shares',raw_rows=rows)
    (OUT/f'official-eod-{asof}.json').write_text(json.dumps(result,indent=2))
    print('OFFICIAL_EOD_ROWS',json.dumps(rows),flush=True)

def annual_index(ticker):
    url='https://www.nseindia.com/api/annual-reports?'+urlencode(dict(index='equities',symbol=ticker))
    r,b=fetch(url,ticker+'-nse-annual-index')
    if not r.get('ok'):return
    data=json.loads(b)['data'];rows=[]
    for x in data:
        if '.pdf' in x.get('fileName','').lower():rows.append(dict(url=x['fileName'],text=f"Annual report {x['fromYr']}-{x['toYr']} {x.get('submission_type')}",discovered_from=url,metadata=x))
    p=OUT/f'{ticker}-links.json';old=json.loads(p.read_text()) if p.exists() else []
    p.write_text(json.dumps(rows+old,indent=2),encoding='utf-8')
    print('ANNUAL_INDEX',ticker,len(rows),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prices','eod-official','exchange','annual-index','discovery','documents','fetch','extract','resolve','probe']);p.add_argument('--tickers',nargs='+',default=['INFY','KPRMILL','CERA']);p.add_argument('--asof',default='2026-10-29');p.add_argument('--start',default='01-10-2026');p.add_argument('--end',default='30-10-2026');p.add_argument('--url');p.add_argument('--label',default='manual-probe');p.add_argument('--file');p.add_argument('--kind',choices=['annual','transcript','filing'],default='filing');p.add_argument('--limit',type=int,default=1);p.add_argument('--offset',type=int,default=0);p.add_argument('--config',default=str(ROOT/'companies.json'));a=p.parse_args()
    with (OUT/'commands.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(started_at_utc=now(),argv=sys.argv))+'\n')
    if a.stage in ['fetch','probe']:fetch(a.url,a.label)
    elif a.stage=='extract':extract(a.file)
    elif a.stage=='resolve':resolve_pdf(a.file)
    elif a.stage=='eod-official':official_eod(a.tickers,a.asof)
    else:
        config=json.loads(Path(a.config).read_text())
        for t in a.tickers:
            if a.stage=='prices':prices(t,a.asof)
            elif a.stage=='exchange':exchange(t,a.start,a.end)
            elif a.stage=='documents':documents(t,a.kind,a.limit,a.offset)
            elif a.stage=='annual-index':annual_index(t)
            else:discover(t,config[t]['discovery_pages'])
            time.sleep(.5)
