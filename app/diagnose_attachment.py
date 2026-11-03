"""Bounded one-attachment diagnostic. Never reruns the portfolio refresh."""
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.request import Request, urlopen
from .adapters import SourceClient, SourceError
from .engine import pdf_module
from .store import Store, utcnow


def inspect(body):
    result={'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'pdf_header':body.startswith(b'%PDF-'),
            'eof_near_end':b'%%EOF' in body[-4096:]}
    linear=re.search(rb'/Linearized\b.{0,150}?/L\s+(\d+)',body[:1500],re.S)
    result['linearized_declared_length']=int(linear[1]) if linear else None
    try:
        pdf=pdf_module().open(stream=body,filetype='pdf')
        result.update(pages=pdf.page_count,requires_password=bool(pdf.needs_pass),repaired=pdf.is_repaired)
        pdf.close()
    except Exception as error:result['parse_error']=str(error)
    return result


def main():
    store=Store('runtime');event_id='nse-SUNPHARMA-106836275'
    event=store.get('filings',event_id)
    if not event:raise SystemExit('Previously recorded Sun Pharma filing not found')
    failed=next(d for d in sorted(store.rows('documents'),key=lambda d:d['checked_at']) if d['event_id']==event_id and d['status']=='failed')
    old_source=store.get('sources',failed['source_id']);old_body=store.blob_path(old_source['sha256']).read_bytes()
    fixtures=Path('tests/fixtures');fixtures.mkdir(parents=True,exist_ok=True)
    (fixtures/'sunpharma-incomplete-response.bin').write_bytes(old_body)
    (fixtures/'sunpharma-incomplete-response.json').write_text(json.dumps({'source':old_source,'inspection':inspect(old_body),
        'note':'Actual failed response retained unchanged. Not a synthetic or successful filing. No assertion yet about whether truncation came from client or server.'},indent=2),encoding='utf-8')
    report={'checked_at':utcnow(),'url':event['url'],'exchange_declared_file_size':event['raw'].get('attFileSize'),
            'original_failed_response':inspect(old_body),'methods':[]}
    # Independent full read with the same ordinary request headers and no cache-busting/range tricks.
    started=time.monotonic();body=b''
    record={'url':event['url'],'final_url':event['url'],'kind':'attachment-diagnostic-single-read','retrieved_at':utcnow(),'ok':False}
    try:
        with urlopen(Request(event['url'],headers={'User-Agent':'FINN-Assignment/0.2','Accept':'*/*'}),timeout=20) as response:
            record.update(http_status=response.status,final_url=response.url,content_type=response.headers.get('Content-Type'),
                          content_length=response.headers.get('Content-Length'),content_range=response.headers.get('Content-Range'),
                          transfer_encoding=response.headers.get('Transfer-Encoding'))
            body=response.read(8_000_001)
            if len(body)>8_000_000:raise ValueError('Diagnostic size cap exceeded')
            record['ok']=True
    except Exception as error:
        body=getattr(error,'partial',body);record['error']=f'{type(error).__name__}: {error}'
    record['seconds']=round(time.monotonic()-started,3)
    record=store.source(record,body)
    inspection=inspect(body)
    store.validate_source(record['id'],bool(inspection.get('eof_near_end') and inspection.get('pages',0)>0 and not inspection.get('repaired')),record.get('error'))
    report['methods'].append({'method':'independent urllib read(limit+1), same headers','request':record,'inspection':inspection})
    try:
        adapter_record,adapter_body=SourceClient(store,timeout=20).get(event['url'],'attachment-diagnostic-adapter')
        adapter_inspection=inspect(adapter_body)
        store.validate_source(adapter_record['id'],bool(adapter_inspection.get('eof_near_end') and adapter_inspection.get('pages',0)>0 and not adapter_inspection.get('repaired')))
        report['methods'].append({'method':'app bounded chunk reader','request':adapter_record,'inspection':adapter_inspection})
    except SourceError as error:
        report['methods'].append({'method':'app bounded chunk reader','error':str(error),'request':store.get('sources',error.request_id) if error.request_id else None})
    dest=Path('app/verification/attachment-diagnostic.json');dest.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
