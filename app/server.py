"""Local / free-host source service. Shared mobile assets; bounded refresh and research."""
import argparse
import json
import mimetypes
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .engine import configuration, ensure_document, run_refresh
from .store import BusyRefresh, Store, utcnow
from .views import evidence_for, live_data, public_document
from .research import begin_research,run_research,retrieve,symbol,research_job
from .answers import answer_question,CitationRejected
from .gemini import status as model_status,ModelUnavailable

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'preview'/'dist'


class App:
    def __init__(self,directory):
        self.store=Store(directory)
        self.store.restore_snapshot(ROOT/'app'/'bootstrap.json.gz')
        self.token=secrets.token_urlsafe(24)
        self.lock=threading.Lock();self.document_lock=threading.Lock()
        self.last_trigger=0;self.triggers=[]
        self.research_triggers=[]

    def start_research(self,body):
        ticker=symbol(body.get('ticker'))
        with self.lock:
            now=time.monotonic();self.research_triggers=[t for t in self.research_triggers if now-t<86400]
            if len(self.research_triggers)>=30:raise ValueError('Research discovery limit reached; stored passages remain searchable')
            job,reused=begin_research(self.store,ticker,force=False)
            if not reused:
                self.research_triggers.append(now)
                threading.Thread(target=run_research,args=(self.store,job),daemon=True,name='finn-research').start()
            return job,reused

    def start_refresh(self,body=None,automatic=False):
        body=body or {}
        with self.lock:
            active=self.store.active_job()
            if active:return active,True
            now=time.monotonic()
            self.triggers=[t for t in self.triggers if now-t<86400]
            if len(self.triggers)>=24:raise ValueError('Daily refresh limit reached; cached sources remain available')
            if now-self.last_trigger<60:raise ValueError('Wait 60 seconds between completed refresh triggers')
            tickers,start,end,asof=configuration(body.get('tickers'),body.get('start'),body.get('end'),body.get('asof'))
            try:job=self.store.begin_job(tickers,start.isoformat(),end.isoformat(),asof.isoformat())
            except BusyRefresh as error:return error.job,True
            self.last_trigger=now;self.triggers.append(now)
            threading.Thread(target=run_refresh,args=(self.store,job),daemon=True,name='finn-refresh').start()
            return job,False

    def maybe_refresh(self):
        # Request-driven catch-up: no cron, keep-alive pings or claims of work while a free service sleeps.
        if os.environ.get('FINN_AUTO_REFRESH','1')!='1' or self.store.active_job():return
        latest=self.store.latest_job()
        stamp=latest.get('finished_at') if latest else None
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(stamp)).total_seconds() if stamp else float('inf')
        if age>3600:
            try:self.start_refresh(automatic=True)
            except ValueError:pass


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version='FINN/0.2'

        def send(self,status,body=b'',mime='application/json; charset=utf-8',headers=None):
            if isinstance(body,(dict,list)):body=json.dumps(body,ensure_ascii=False).encode('utf-8')
            if isinstance(body,str):body=body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers()
            if self.command!='HEAD':self.wfile.write(body)

        def do_HEAD(self):self.do_GET()

        def do_GET(self):
            try:self.get_route()
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception as error:
                self.send(500,{'error':f'{type(error).__name__}: {error}'})

        def get_route(self):
            parsed=urlsplit(self.path);path=unquote(parsed.path);query=parse_qs(parsed.query)
            if path=='/health':return self.send(200,{'status':'ok','mode':'real-source push and cited company research','model_enabled':model_status()['available']})
            if path=='/api/data':
                app.maybe_refresh();payload=live_data(app.store);payload['refreshToken']=app.token
                return self.send(200,payload)
            if path.startswith('/api/jobs/'):
                job=app.store.get('jobs',path.rsplit('/',1)[-1])
                return self.send(200 if job else 404,job or {'error':'Job not found'})
            if path.startswith('/api/research/jobs/'):
                job=research_job(app.store,path.rsplit('/',1)[-1])
                return self.send(200 if job else 404,job or {'error':'Research job not found'})
            if path.startswith('/api/research/'):
                try:ticker=symbol(path.rsplit('/',1)[-1])
                except ValueError as error:return self.send(400,{'error':str(error)})
                job=app.store.get('research',ticker)
                # "Not loaded yet" is a normal state, not an error: the UI starts discovery from it.
                return self.send(200,job or {'ticker':ticker,'status':'not_loaded','documents':[]})
            if path.startswith('/api/filings/') and path.endswith('/evidence'):
                event_id=path.split('/')[3]
                if not app.store.get('filings',event_id):return self.send(404,{'error':'Unknown filing'})
                with app.document_lock:doc=ensure_document(app.store,event_id)
                if doc['status']!='ready':return self.send(422,{'error':doc.get('error'),'document':doc})
                return self.send(200,{'document':public_document(app.store,doc),'evidence':evidence_for(doc)})
            if path.startswith('/api/documents/'):
                doc=app.store.get('documents',path.rsplit('/',1)[-1])
                return self.send(200 if doc else 404,public_document(app.store,doc,full=True) if doc else {'error':'Unknown document'})
            if path.startswith('/files/') and path.endswith('.pdf'):
                doc=app.store.get('documents',path.rsplit('/',1)[-1][:-4])
                if not doc or doc['status']!='ready':return self.send(404,{'error':'Validated PDF not available'})
                source=app.store.blob_path(doc['sha256'])
                if not source.exists():return self.send(302,b'',headers={'Location':doc['url']})
                return self.send(200,source.read_bytes(),'application/pdf',{'Content-Disposition':'inline; filename="'+doc['id']+'.pdf"'})
            if path=='/data.json':
                demo=json.loads((ASSETS/'data.json').read_text(encoding='utf-8'))
                for doc in demo['documents'].values():
                    doc['pdf']=doc['pdf'].replace('/documents/','/demo-files/')
                    if doc.get('pageImage'):doc['pageImage']=doc['pageImage'].replace('/evidence/','/demo-evidence/')
                return self.send(200,demo)
            if path.startswith(('/demo-files/','/demo-evidence/')):
                routes=json.loads((ROOT/'preview'/'document_routes.json').read_text(encoding='utf-8'))
                original_path=path.replace('/demo-files/','/documents/').replace('/demo-evidence/','/evidence/')
                filename=routes.get(original_path)
                if filename:
                    local=(ROOT/filename).resolve()
                    if local.is_relative_to((ROOT/'experiments'/'samples').resolve()) and local.exists():
                        return self.send(200,local.read_bytes(),mimetypes.guess_type(local.name)[0] or 'application/octet-stream')
                    # Clean checkout has no feasibility archive. PDF links still resolve to the original source.
                    if path.startswith('/demo-files/'):
                        doc=json.loads((ASSETS/'data.json').read_text(encoding='utf-8'))['documents'].get(path.rsplit('/',1)[-1][:-4])
                        if doc:return self.send(302,b'',headers={'Location':doc['url']})
                return self.send(404,{'error':'Demo archive asset unavailable'})
            filename='index.html' if path in ('/','/index.html') else path.lstrip('/')
            if filename not in {'index.html','source.html','app.js','live.js','pull.js','style.css','source.js'}:return self.send(404,{'error':'Not found'})
            content=(ASSETS/filename).read_bytes()
            mime=mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            if filename.endswith('.html'):
                live=query.get('demo')!=['1']
                text=content.decode('utf-8').replace('<head>','<head><meta name="finn-mode" content="'+('live' if live else 'demo')+'">')
                if live:text=text.replace('LOCAL PREVIEW','FETCHED DATA').replace('Local preview','Real-source workspace').replace('saved preview data','stored source data')
                content=text.encode('utf-8');mime+='; charset=utf-8'
            self.send(200,content,mime)

        def do_POST(self):
            path=urlsplit(self.path).path
            if path not in {'/api/refresh','/api/research','/api/research/query','/api/research/answer'}:return self.send(404,{'error':'Not found'})
            if not secrets.compare_digest(self.headers.get('X-FINN-Token',''),app.token):return self.send(403,{'error':'Refresh token missing or invalid; reload the page'})
            origin=self.headers.get('Origin')
            if origin and urlsplit(origin).netloc!=self.headers.get('Host'):return self.send(403,{'error':'Cross-origin refresh rejected'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.send(415,{'error':'Use application/json'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16384:raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError('Refresh configuration must be an object')
                if path=='/api/research/answer':
                    try:return self.send(200,answer_question(app.store,body.get('ticker'),body.get('question'),body.get('history')))
                    except (ModelUnavailable,CitationRejected) as error:
                        result=retrieve(app.store,body.get('ticker'),body.get('question'))
                        result['answer']={'status':'unavailable','error':str(error),'content':None}
                        return self.send(200,result)
                if path=='/api/research/query':return self.send(200,retrieve(app.store,body.get('ticker'),body.get('question')))
                job,reused=app.start_research(body) if path=='/api/research' else app.start_refresh(body)
                self.send(202,{'job':job,'reused':reused})
            except (ValueError,TypeError) as error:self.send(400,{'error':str(error)})
    return Handler


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','8766')))
    parser.add_argument('--host',default='0.0.0.0' if os.environ.get('RENDER') else '127.0.0.1')
    parser.add_argument('--data-dir',default=os.environ.get('FINN_DATA_DIR',str(ROOT/'runtime')))
    parser.add_argument('--no-auto-refresh',action='store_true',help='Inspect stored real data without automatic upstream requests; manual refresh remains available')
    args=parser.parse_args()
    if args.no_auto_refresh:os.environ['FINN_AUTO_REFRESH']='0'
    app=App(args.data_dir)
    server=ThreadingHTTPServer((args.host,args.port),make_handler(app));server.daemon_threads=True
    print(f'FINN real-source workspace: http://{args.host}:{args.port}',flush=True)
    print('Dated interaction demo: /?demo=1 · Gemini: '+('configured' if model_status()['available'] else 'unavailable')+' · request-driven refresh only',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
