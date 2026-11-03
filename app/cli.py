import argparse
import json
import os
from pathlib import Path
from .engine import configuration, run_refresh
from .store import BusyRefresh, Store
from .adapters import priority,priority_title
from .store import utcnow


def main():
    parser=argparse.ArgumentParser(description='Real-source refresh. Never reads the experiment cache or invokes a model.')
    parser.add_argument('command',choices=['refresh','status','export','rerank','research','query'])
    parser.add_argument('--tickers',nargs='+');parser.add_argument('--start');parser.add_argument('--end');parser.add_argument('--asof')
    parser.add_argument('--data-dir',default=os.environ.get('FINN_DATA_DIR','runtime'))
    parser.add_argument('--documents',type=int,default=2)
    parser.add_argument('--output',default='app/bootstrap.json.gz')
    parser.add_argument('--force',action='store_true');parser.add_argument('--question',default='What are the business segments and management outlook?')
    args=parser.parse_args();store=Store(args.data_dir)
    if args.command in ('research','query'):
        from .research import begin_research,run_research,retrieve
        if not args.tickers:parser.error('Research/query requires --tickers')
        for ticker in args.tickers:
            if args.command=='research':
                job,reused=begin_research(store,ticker,args.force)
                if not reused:job=run_research(store,job)
                print(json.dumps({'cached':reused,**job},indent=2),flush=True)
            else:print(json.dumps(retrieve(store,ticker,args.question),indent=2),flush=True)
    elif args.command=='refresh':
        symbols,start,end,asof=configuration(args.tickers,args.start,args.end,args.asof)
        try:job=store.begin_job(symbols,start.isoformat(),end.isoformat(),asof.isoformat())
        except BusyRefresh as error:print(json.dumps({'active':error.job}));return
        print('STARTED '+json.dumps(job),flush=True)
        print(json.dumps(run_refresh(store,job,document_limit=args.documents),indent=2))
    elif args.command=='rerank':
        rows=store.rows('filings')
        for event in rows:
            tier,rule,reason=priority(event['category'],event['description'])
            event.update(priority=tier,rule_id='push-v2:'+rule,reason=reason,title=priority_title(rule,event['category']),rule_updated_at=utcnow())
            store.put('filings',event['id'],event,ticker=event['ticker'],published=event['published_at'])
        print(json.dumps({'reranked':len(rows),'rule_version':'push-v2','source_requests':0,'retrieval_times_unchanged':True}))
    elif args.command=='export':
        snapshot=store.export_snapshot(args.output)
        print(json.dumps({'snapshot':args.output,'exported_at':snapshot['exported_at'],'counts':{k:len(v) for k,v in snapshot['tables'].items()},'bytes':Path(args.output).stat().st_size}))
    else:
        print(json.dumps({'latest_job':store.latest_job(),'counts':{k:len(store.rows(k)) for k in store.TABLES}},indent=2))


if __name__=='__main__':main()
