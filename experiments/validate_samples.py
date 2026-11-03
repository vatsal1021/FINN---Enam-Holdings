"""Offline evidence checks against downloaded responses, not tests of a future app."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent/'samples'
official=json.loads((P/'official-eod-2026-10-29.json').read_text())
rows={x['SYMBOL']:x for x in official['raw_rows']}
results=[]
for t in ['INFY','KPRMILL','CERA','APOLLOHOSP']:
    assert rows[t]['DATE1']=='29-Oct-2026'
    assert float(rows[t]['CLOSE_PRICE'])>0 and int(rows[t]['TTL_TRD_QNTY'])>0
    y=json.loads((P/f'{t}-prices.json').read_text())
    assert y['currency']=='INR' and y['exchange_timezone']=='Asia/Kolkata'
    x=next(x for x in y['observations'] if x['date']=='2026-10-29')
    if t=='CERA':
        assert x['close'] is None and x['volume'] is None
        result='Yahoo missing; official source provides complete values'
    else:
        assert abs(x['close']-float(rows[t]['CLOSE_PRICE']))<.001
        assert x['volume']==int(rows[t]['TTL_TRD_QNTY'])
        result='Yahoo matches official close/volume on this date'
    results.append(dict(ticker=t,date='2026-10-29',close_inr=float(rows[t]['CLOSE_PRICE']),volume_shares=int(rows[t]['TTL_TRD_QNTY']),result=result))
requests=[json.loads(x) for x in (P/'requests.jsonl').read_text().splitlines()]
for r in requests:
    f=P.parent/r['file']
    assert hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256']
growth=(205011.98/191525.12-1)*100
assert 7<=growth<=8
summary=dict(label='Dated local feasibility checks; not live application data',date='2026-10-30',price_checks=results,request_integrity_checks=len(requests),cera_revenue_growth_percent=growth,limitations=['One EOD cross-check only; no split/corporate-action adjustment validation','Cera growth uses manually verified standalone annual figures; not an automated guidance verdict','Cloud retrieval, full portfolio coverage, model quality and source reuse rights not verified'])
(P/'validation-results.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
