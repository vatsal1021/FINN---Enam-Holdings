"""Refactored from experiments/data_probe.py: ordinary NSE requests, now uncached and validated."""
import csv
import hashlib
import io
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .store import utcnow

IST=timezone(timedelta(hours=5,minutes=30))
RULE_VERSION='push-v3'
HOSTS={'www.nseindia.com','nsearchives.nseindia.com','archives.nseindia.com'}


class SourceError(Exception):
    def __init__(self,message,request_id=None):
        super().__init__(message);self.request_id=request_id


def allowed_url(url,hosts=None):
    p=urlsplit(url)
    return p.scheme=='https' and p.hostname in (HOSTS if hosts is None else hosts) and p.port in (None,443) and not p.username and not p.password


class CheckedRedirect(HTTPRedirectHandler):
    def __init__(self,hosts=None):
        super().__init__();self.hosts=hosts
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not allowed_url(newurl,self.hosts): raise SourceError('Source redirected outside the explicit source allowlist')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


class SourceClient:
    def __init__(self,store,timeout=12,hosts=None):
        self.store=store;self.timeout=timeout;self.hosts=hosts

    def get(self,url,kind,limit=8_000_000):
        if not allowed_url(url,self.hosts):raise SourceError('Unsupported source URL; only explicit official-source HTTPS hosts are fetched')
        started=time.monotonic();body=b'';chunks=[]
        record=dict(url=url,kind=kind,retrieved_at=utcnow(),http_status=None,ok=False,final_url=url,job_id=getattr(self,'job_id',None))
        try:
            request=Request(url,headers={'User-Agent':'FINN-Assignment/0.2','Accept':'*/*'})
            with build_opener(CheckedRedirect(self.hosts)).open(request,timeout=self.timeout) as response:
                record.update(http_status=response.status,final_url=response.url,content_type=response.headers.get('Content-Type',''),
                              content_length=response.headers.get('Content-Length'),content_range=response.headers.get('Content-Range'))
                if not allowed_url(response.url,self.hosts):raise SourceError('Unsupported final source host')
                if response.status!=200:raise SourceError(f'Unexpected HTTP {response.status}; partial responses are not treated as complete sources')
                expected=response.headers.get('Content-Length')
                if expected and int(expected)>limit:raise SourceError(f'Declared source size {int(expected):,} exceeds download limit {limit:,} bytes')
                size=0
                while True:
                    chunk=response.read(min(65536,limit+1-size))
                    if not chunk:break
                    chunks.append(chunk);size+=len(chunk)
                    if size>limit:raise SourceError(f'Source exceeds {limit:,}-byte cap')
                    if time.monotonic()-started>self.timeout:raise SourceError('Source transfer exceeded time budget')
                body=b''.join(chunks)
                expected=response.headers.get('Content-Length')
                if expected and int(expected)!=len(body):raise SourceError('Downloaded bytes do not match declared Content-Length')
                record['ok']=True
        except HTTPError as error:
            body=error.read(2000);record.update(http_status=error.code,error=f'HTTP {error.code}')
        except Exception as error:
            if chunks:body=b''.join(chunks)
            record['error']=f'{type(error).__name__}: {error}'
        record['seconds']=round(time.monotonic()-started,3)
        record=self.store.source(record,body)
        if not record['ok']:
            self.store.validate_source(record['id'],False,record.get('error'))
            raise SourceError(f"{record.get('error','Source request failed')} [request {record['id']}]",request_id=record['id'])
        return record,body


def eod_url(day):
    return 'https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_'+day.strftime('%d%m%Y')+'.csv'


def announcements_url(ticker,start,end):
    return 'https://www.nseindia.com/api/corporate-announcements?'+urlencode(dict(index='equities',symbol=ticker,
                from_date=start.strftime('%d-%m-%Y'),to_date=end.strftime('%d-%m-%Y')))


def parse_eod(body,day):
    reader=csv.DictReader(io.StringIO(body.decode('utf-8-sig')))
    fields={k.strip() for k in (reader.fieldnames or [])}
    required={'SYMBOL','SERIES','DATE1','CLOSE_PRICE','PREV_CLOSE','TTL_TRD_QNTY'}
    if not required.issubset(fields):raise SourceError('EOD response lacks required CSV columns (possibly an HTML/error response)')
    result={}
    for row in reader:
        row={str(k).strip():str(v or '').strip() for k,v in row.items()}
        if row['SERIES']!='EQ':continue
        try:
            if datetime.strptime(row['DATE1'],'%d-%b-%Y').date()!=day:raise SourceError('EOD date differs from requested session')
            close,previous=Decimal(row['CLOSE_PRICE']),Decimal(row['PREV_CLOSE'])
            if not close.is_finite() or not previous.is_finite() or close<0 or previous<0:raise SourceError('Invalid EOD price')
            volume=int(row['TTL_TRD_QNTY'])
            if volume<0:raise SourceError('Invalid traded-share volume')
            change=(close/previous-1)*100 if previous>0 else None
            value={'ticker':row['SYMBOL'],'date':day.isoformat(),'close_exact':str(close),'previous_exact':str(previous),
                   'close':float(close),'previous':float(previous),'volume':volume,'change_pct':float(change) if change is not None else None,
                   'price_unit':'INR/share','volume_unit':'shares','series':'EQ','raw':row}
            if row['SYMBOL'] in result:raise SourceError('Duplicate EQ symbol in EOD source')
            result[row['SYMBOL']]=value
        except (ValueError,InvalidOperation) as error:raise SourceError(f'Invalid EOD row for {row.get("SYMBOL")}: {error}')
    if not result:raise SourceError('No EQ records in EOD response')
    return result


# Reference-document taxonomy (results, M&A, fund_raise, management_change, ...), adapted to NSE metadata.
# Each rule: (kind, tier, score, rule id, regex, card title, why-it-matters line). Order matters: specific before generic.
RULES=[
    ('unclassified','routine',5,'publication',r'newspaper','Newspaper copy','Published copy of an earlier filing. No new information expected.'),
    ('unclassified','routine',5,'employee-shares',r'esop|esos|esps|employee stock|grant of [\d,]+\s+options|pursuant to esop','Employee share allotment','Routine employee-share paperwork; tiny dilution.'),
    ('unclassified','routine',5,'compliance',r'regulation 74\(5\)|compliance certificate|certificate under|trading window|loss of share certificate|duplicate share|book closure|change in registrar','Compliance paperwork','Routine regulatory paperwork.'),
    ('earnings_call','attention',62,'transcript',r'transcript','Earnings-call transcript',"Management's own words on the quarter: guidance, tone and what analysts pushed on."),
    ('earnings_call','routine',8,'recording',r'audio recording|video recording|link of (?:the )?recording|webcast|recording of the','Call recording posted','Audio/video of the call. The transcript, when filed, is easier to scan.'),
    ('M&A','attention',82,'subsidiary-listing',r'trading in equity shares of|initial public offer of','Subsidiary listing / IPO',"A group company is listing; can re-rate the parent's holding."),
    ('fund_raise','attention',60,'planned-corporate',r'(?:board meeting intimation|meeting.*scheduled|meeting.*to be held|to consider).*(?:raising.*funds|fund.?rais|debenture|qip|rights issue|preferential)','Board to consider fund raise','Board will consider raising money; terms and dilution not yet known.'),
    ('results','routine',12,'scheduled-results',r'board meeting intimation|meeting.*scheduled|meeting.*to be held|will be held','Results date announced','Board meeting scheduled. The numbers come later.'),
    ('results','routine',10,'presentation',r'investor presentation|analyst presentation|results presentation','Investor presentation',"Management's slide deck, usually with results. Read alongside the results filing."),
    ('investor_meetings','routine',6,'investor-meet',r'schedule of (?:analyst|investor)?\s*meet|investor conference|analyst(?:s)? meet|institutional investor meet|con\.? call updates','Investor meeting','Meeting or call with investors. No new numbers in the notice.'),
    ('results','attention',90,'results-press',r'(?:press|media) release.*(?:financial results|results for the quarter|q[1-4] (?:and h[12] )?fy)','Results press release',"Management's summary of the quarter. The results filing has the full numbers."),
    ('results','attention',100,'results',r'financial results|audited financial|unaudited financial|results for the quarter','Quarterly results filed','New quarterly numbers. Check revenue and profit against last quarter and last year.'),
    ('results','attention',70,'auditor-report',r'report of auditors|limited review report','Auditor report on results',"Auditor's review of the latest results. Look for any qualification."),
    ('management_change','attention',72,'auditor-change',r'(?:appoint|resign|cessation|change)[^.]{0,80}(?:statutory|secretarial|internal)?\s*auditor','Auditor change','Auditor appointed or leaving. A mid-term resignation is a warning sign.'),
    ('management_change','attention',95,'management',r'(?:appoint|resign|cessation|retire|re-?designat|demise|step(?:s|ping)? down|change in (?:directorate|management))[^.]{0,200}(?:director|chief|ceo|cfo|coo|cto|managing|kmp|key managerial|company secretary|chairman|whole.?time|president)|(?:director|chief|ceo|cfo|managing|kmp|chairman)[^.]{0,120}(?:appoint|resign|cessation|retire)','Leadership change','A change at the top. Check who is leaving or joining and their background.'),
    ('litigation','attention',88,'litigation',r'action\(s\) taken or orders passed|orders? passed|penalt|show cause|litigation|tax demand|insolvency|nclt|fraud|default|regulatory action|adjudicat|search and seizure|enforcement','Legal or regulatory action','An order, penalty or dispute. Check the amount and whether it is contested.'),
    ('M&A','attention',85,'corporate-action',r'acquisition|acquire|amalgamation|merger|demerger|joint venture|scheme of arrangement|wholly.?owned subsidiary|incorporation of|divest|sale of stake|stake sale|restructuring','Deal or restructuring','Acquisition, merger, new subsidiary or restructuring. Check size and price.'),
    ('fund_raise','attention',80,'fund-raise',r'qualified institution|\bqip\b|rights issue|preferential (?:issue|allotment)|buy.?back|non.?convertible|debenture|commercial paper|fund.?rais|raising of funds|allotment of securities|warrants','Fund raising','Company raising equity or debt (or buying back shares). Check size and dilution.'),
    ('pledging','attention',78,'pledge',r'pledge|encumbrance|invocation','Promoter pledge change','Promoter shares pledged or released. Rising pledges are a risk signal.'),
    ('insider_trading','attention',55,'insider',r'insider trading|prohibition of insider|\bsast\b|substantial acquisition|regulation 29|regulation 7\(2\)','Promoter / insider trade','An insider bought or sold shares. Direction and size matter.'),
    ('credit_rating','attention',66,'credit-rating',r'credit rating|crisil|icra|care ratings|care edge|india ratings|acuite|rating(?:s)? (?:upgrade|downgrade|reaffirm|assign|revis)','Credit rating action',"A rating agency changed or confirmed its view of the company's debt."),
    ('bonus_split','attention',68,'bonus-split',r'bonus issue|bonus shares|issue of bonus|stock split|sub-?division of (?:equity )?shares|split of (?:equity )?shares','Bonus issue / split','Share count changes; no cash to you. Often a signal of management confidence.'),
    ('dividend','routine',9,'record-date',r'record date','Record date set','Cut-off date for an already-announced payout.'),
    ('dividend','attention',52,'dividend',r'dividend','Dividend declared',"Cash payout announced. Compare with last year's payout."),
    ('capex','attention',58,'capex',r'capacity|commercial operation|declared commercial|\d\s*mw\b|commissioning|commissioned|new plant|capex|capital expenditure|greenfield|brownfield|commercial production|expansion','Capacity / project update','New capacity or project going live. Adds to future revenue.'),
    ('press_release','attention',54,'order-win',r'bagging|receiving of orders|order win|\bbags\b|contracts? (?:worth|award|from)|letter of award|orders? (?:worth|from|received)','Order win','New orders or contracts. Size relative to revenue decides how much it matters.'),
    ('agm_egm','routine',7,'agm',r'annual general meeting|\bagm\b|extraordinary general|\begm\b','General meeting','Shareholder meeting notice or outcome.'),
    ('postal_ballot','routine',7,'postal-ballot',r'postal ballot|e-?voting','Postal ballot','Shareholder vote by post. Usually on already-announced items.'),
    ('results','attention',45,'board-outcome',r'outcome of (?:the )?board meeting','Board meeting outcome','Board decisions, often including results. Open to see what was approved.'),
    ('unclassified','routine',6,'committee',r'committee meeting','Committee update','Board-committee paperwork.'),
    ('press_release','unreviewed',20,'press-release',r"press release|media release|regarding '",'Company update','Company news or press release. Open if the headline looks relevant.'),
]
COMPILED=[(kind,tier,score,rule,re.compile(pattern),title,why) for kind,tier,score,rule,pattern,title,why in RULES]
KINDS={'results':'Results','earnings_call':'Earnings calls','management_change':'Management change','M&A':'M&A / restructuring',
       'fund_raise':'Fund raising','litigation':'Legal / regulatory','credit_rating':'Credit rating','pledging':'Promoter pledge',
       'insider_trading':'Insider trades','dividend':'Dividend','bonus_split':'Bonus / split','capex':'Capex / capacity',
       'press_release':'Orders & news','investor_meetings':'Investor meetings','agm_egm':'AGM / EGM','postal_ballot':'Postal ballot','unclassified':'Routine paperwork'}
SCHEDULED=re.compile(r'board meeting intimation|meeting.*scheduled|meeting.*to be held|to consider and approve')


def quoted_title(description):
    match=re.search(r"regarding\s+'\s*([^']{6,140}?)\s*'",description or '')
    return match.group(1).strip() if match else None


def classify(category,description):
    text=' '.join((str(category or '')+' '+str(description or '')).split()).casefold()
    for kind,tier,score,rule,pattern,title,why in COMPILED:
        # Results wording inside a scheduling notice is not a delivered result.
        if rule in ('results','results-press') and SCHEDULED.search(text):continue
        if pattern.search(text):
            headline=quoted_title(description) if rule=='press-release' else None
            return {'kind':kind,'priority':tier,'score':score,'rule':rule,'title':headline or title,'reason':why}
    return {'kind':'unclassified','priority':'unreviewed','score':10,'rule':'unknown','title':str(category or 'Other filing'),
            'reason':'No rule matched. Kept visible; open it if the description looks relevant.'}


def priority(category,description):
    c=classify(category,description);return c['priority'],c['rule'],c['reason']


def priority_title(rule,category):
    return next((title for _,_,_,r,_,title,_ in COMPILED if r==rule),category)


def parse_announcements(body,ticker,start,end):
    try:rows=json.loads(body)
    except (ValueError,UnicodeDecodeError) as error:raise SourceError('Announcements response is not JSON') from error
    if not isinstance(rows,list):raise SourceError('Announcements response is not a list')
    if len(rows)>2000:raise SourceError('Announcements response exceeds bounded record count')
    result=[]
    for raw in rows:
        if not isinstance(raw,dict) or raw.get('symbol')!=ticker:raise SourceError('Announcement company identity differs from requested ticker')
        try:published=datetime.strptime(raw['an_dt'],'%d-%b-%Y %H:%M:%S').replace(tzinfo=IST)
        except (ValueError,KeyError) as error:raise SourceError('Unrecognised announcement timestamp') from error
        if not start<=published.date()<=end:raise SourceError('Announcement outside requested date window')
        url=str(raw.get('attchmntFile') or '').strip()
        # Text-only announcements and non-NSE attachment hosts are kept as metadata; only the PDF fetch is refused.
        fetchable=allowed_url(url)
        category=str(raw.get('desc') or 'Unclassified')
        description=str(raw.get('attchmntText') or category)
        c=classify(category,description)
        identity=str(raw.get('seq_id') or hashlib.sha256((ticker+url+published.isoformat()).encode()).hexdigest()[:24])
        result.append(dict(id='nse-'+ticker+'-'+identity,ticker=ticker,provider_company=raw.get('sm_name'),
                           title=c['title'],description=description,category=category,priority=c['priority'],rule_id=RULE_VERSION+':'+c['rule'],
                           reason=c['reason'],kind=c['kind'],score=c['score'],url=url if fetchable else '',attachment_url=url,
                           attachment_fetchable=fetchable,date=published.date().isoformat(),published_at=published.isoformat(),
                           time=raw['an_dt']+' IST',raw=raw,summary='',manual=False,evidence=None))
    return result
