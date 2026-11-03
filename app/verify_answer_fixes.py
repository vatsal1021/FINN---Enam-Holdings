"""Rerun only the three material cases from the existing audit, retaining the first pass."""
import json
from pathlib import Path
from .answers import answer_question
from .store import Store,utcnow
from .verify_answers import CASES,wait_for_pacing

ROOT=Path(__file__).resolve().parents[1]

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--only',nargs='+',default=['A04','A06','A07'],choices=['A04','A06','A07'])
    selected=parser.parse_args().only
    store=Store(ROOT/'runtime');path=ROOT/'app/verification/gemini-cases.json'
    report=json.loads(path.read_text(encoding='utf-8'))
    before_calls=len(store.rows('model_calls'));before_sources=len(store.rows('sources'))
    original=ROOT/'app/verification/gemini-cases-before-release.json'
    if not original.exists():original.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    report.setdefault('release_reruns',[]).append({'started_at':utcnow(),'case_ids':selected})
    for case_id,ticker,question,history in CASES:
        if case_id not in selected:continue
        wait_for_pacing(store)
        try:
            result=answer_question(store,ticker,question,history);answer=result['answer'];content=answer['content']
            text=' '.join(c['text'] for c in content['claims']).casefold()
            passed=answer['status']=='ready'
            if case_id=='A04':passed=passed and '61%' in text and '80%' in text and ('greenfield' in text or 'project' in text)
            if case_id=='A06':passed=passed and all(t in text for t in ['decorative','industrial','international','home'])
            if case_id=='A07':passed=passed and content['status']=='partial' and bool(content['gaps'])
            cited={c['evidence_id'] for claim in content['claims'] for c in claim['citations']}
            row={'id':case_id,'ticker':ticker,'question':question,'history':history,'passed':passed,'answer':answer,
                 'audit_evidence':[p for p in result['passages'] if p['id'] in cited]}
        except Exception as error:
            # Transport/validation errors are already redacted; never print arbitrary provider objects.
            from .gemini import ModelUnavailable
            from .answers import CitationRejected
            if not isinstance(error,(ModelUnavailable,CitationRejected,ValueError)):raise
            row={'id':case_id,'ticker':ticker,'question':question,'passed':False,'error':str(error)}
        report['cases']=[row if c['id']==case_id else c for c in report['cases']]
        report['release_reruns'][-1].update(new_model_calls=len(store.rows('model_calls'))-before_calls,
            source_requests=len(store.rows('sources'))-before_sources)
        report.update(passed=sum(c['passed'] for c in report['cases']),total=len(report['cases']),manual_review='pending')
        path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        print(json.dumps({k:v for k,v in row.items() if k!='audit_evidence'}),flush=True)
    print(json.dumps(report['release_reruns'][-1]),flush=True)

if __name__=='__main__':main()
