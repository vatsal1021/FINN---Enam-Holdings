"""Offline PDF and data inspection; no network. All pages use one-based PDF numbering."""
import json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'samples'
sys.path.insert(0,str(ROOT.parent/'tmp/pdf-render-tools'))
import pymupdf
pymupdf.TOOLS.mupdf_display_errors(False);pymupdf.TOOLS.mupdf_display_warnings(False)

def main():
    docs=[];requests=[json.loads(x) for x in (OUT/'requests.jsonl').read_text().splitlines()]
    for f in sorted(OUT.glob('*.pdf')):
        textfile=Path(str(f)+'.text.json')
        if not textfile.exists():continue
        pages=json.loads(textfile.read_text(encoding='utf-8'))
        row=dict(file=f.name,pages=len(pages),text_pages=sum(len(re.sub(r'\s','',x['text']))>=50 for x in pages),chars=sum(len(x['text']) for x in pages),request=next((r for r in requests if Path(r['file']).name==f.name),None))
        docs.append(row)
    (OUT/'document-inventory.json').write_text(json.dumps(docs,indent=2))
    selected=next(OUT.glob('KPRMILL-filing-*.pdf'))
    doc=pymupdf.open(selected)
    for n in [3,9]:
        p=doc[n-1];p.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(str(OUT/f'KPRMILL-financial-pdf-page-{n}.png'))
        (OUT/f'KPRMILL-financial-pdf-page-{n}.words.json').write_text(json.dumps(p.get_text('words'),ensure_ascii=False))
        try:
            tables=p.find_tables();found=[t.extract() for t in tables.tables]
            (OUT/f'KPRMILL-financial-pdf-page-{n}.tables.json').write_text(json.dumps(found,ensure_ascii=False,indent=2))
            print('TABLES',n,len(found))
        except Exception as e:print('TABLE_EXTRACTION_FAIL',n,type(e).__name__,str(e))
        # Text-based detection is a separate experiment; success does not mean correct cells.
        text_tables=p.find_tables(strategy='text',min_words_vertical=2,min_words_horizontal=1)
        (OUT/f'KPRMILL-page-{n}-text-tables.json').write_text(json.dumps([t.extract() for t in text_tables.tables],indent=2))
    for name in ['CERA-annual-0-20261030T074835558662Z.pdf','KPRMILL-annual-0-20261030T075214666203Z.pdf','INFY-annual-0-20261030T074606259596Z.pdf','APOLLOHOSP-annual-0-20261030T075352025017Z.pdf']:
        pages=json.loads(Path(str(OUT/name)+'.text.json').read_text(encoding='utf-8'));hits=[]
        for x in pages:
            t=re.sub(r'\s+',' ',x['text'])
            if re.search('statement of profit and loss|financial highlights|revenue from operations',t,re.I):hits.append(dict(pdf_page=x['pdf_page'],excerpt=t[:900]))
        (OUT/(name+'.financial-candidates.json')).write_text(json.dumps(hits,indent=2))
        print(name,'CANDIDATE_PAGES',[x['pdf_page'] for x in hits][:20])
    print('DOCUMENTS',len(docs))

if __name__=='__main__':main()
