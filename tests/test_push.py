"""Offline fault injection and validation tests. Synthetic fixtures never enter the live runtime."""
import csv
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs,urlsplit

from app.adapters import IST,SourceClient,SourceError,classify,parse_announcements,parse_eod,priority
from app.engine import configuration,ensure_document,holdings,run_refresh
from app.store import BusyRefresh,Store,utcnow
from app.views import live_data


class FixtureClient:
    def __init__(self,store,day,fail=None):self.store=store;self.day=day;self.fail=fail
    def get(self,url,kind,limit=None):
        if kind=='eod':
            output=io.StringIO();writer=csv.writer(output)
            writer.writerow(['SYMBOL','SERIES','DATE1','CLOSE_PRICE','PREV_CLOSE','TTL_TRD_QNTY'])
            for company in holdings():writer.writerow([company['ticker'],'EQ',self.day.strftime('%d-%b-%Y'),'105.25','100','12345'])
            body=output.getvalue().encode()
        else:
            ticker=parse_qs(urlsplit(url).query)['symbol'][0]
            if ticker==self.fail:raise SourceError('Synthetic HTTP 503 fault injection; not a real provider outcome')
            body=json.dumps([{'symbol':ticker,'seq_id':'fixture-1','an_dt':self.day.strftime('%d-%b-%Y')+' 12:30:00',
                             'desc':'Financial Results','attchmntText':'Financial results for the quarter',
                             'attchmntFile':'https://nsearchives.nseindia.com/corporate/fixture.pdf','sm_name':ticker}]).encode()
        source=self.store.source({'url':url,'final_url':url,'retrieved_at':utcnow(),'http_status':200,'kind':'synthetic-test:'+kind,'ok':True,'fixture':True},body)
        return source,body


class PushTests(unittest.TestCase):
    def setUp(self):
        self.test_root=Path(__file__).resolve().parents[1]/'runtime'/'test-temporary'
        self.test_root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=self.test_root);self.store=Store(self.temp.name)
        self.day=datetime.now(IST).date()-timedelta(days=1)
    def tearDown(self):
        assert Path(self.temp.name).resolve().is_relative_to(self.test_root.resolve())
        self.temp.cleanup()
    def run_job(self,tickers=None,fail=None):
        symbols,start,end,asof=configuration(tickers,self.day.isoformat(),self.day.isoformat(),self.day.isoformat())
        job=self.store.begin_job(symbols,start.isoformat(),end.isoformat(),asof.isoformat())
        return run_refresh(self.store,job,client=FixtureClient(self.store,self.day,fail),document_limit=0)
    def test_duplicate_refresh_retains_one_event_and_first_seen(self):
        first=self.run_job(['INFY']);event=self.store.rows('filings')[0]
        second=self.run_job(['INFY'])
        self.assertEqual((first['inserted'],second['inserted'],second['updated']),(1,0,1))
        self.assertEqual(len(self.store.rows('filings')),1)
        self.assertEqual(self.store.rows('filings')[0]['first_seen'],event['first_seen'])
        self.assertEqual(len(self.store.rows('quotes')),1)
    def test_one_source_failure_accounts_for_all_fifteen(self):
        job=self.run_job(fail='HDFCBANK')
        self.assertEqual(job['status'],'partial');self.assertEqual(job['completed'],15)
        self.assertEqual(job['companies_passed'],14)
        checks=self.store.rows('checks');self.assertEqual(len(checks),15)
        failed=next(c for c in checks if c['ticker']=='HDFCBANK')
        self.assertEqual(failed['filings_status'],'failed');self.assertIsNone(failed['filing_count'])
        self.assertEqual(len(self.store.rows('quotes')),15)
    def test_global_active_lease_reuses_instead_of_duplicate(self):
        self.store.begin_job(['INFY'],self.day.isoformat(),self.day.isoformat(),self.day.isoformat())
        with self.assertRaises(BusyRefresh):self.store.begin_job(['CERA'],self.day.isoformat(),self.day.isoformat(),self.day.isoformat())
    def test_eod_date_units_calculation_and_zero_base(self):
        body=('SYMBOL,SERIES,DATE1,CLOSE_PRICE,PREV_CLOSE,TTL_TRD_QNTY\nINFY,EQ,'+self.day.strftime('%d-%b-%Y')+',105.25,100,12345\nCERA,EQ,'+self.day.strftime('%d-%b-%Y')+',10,0,0\n').encode()
        values=parse_eod(body,self.day)
        self.assertAlmostEqual(values['INFY']['change_pct'],5.25)
        self.assertEqual(values['INFY']['price_unit'],'INR/share');self.assertEqual(values['INFY']['volume_unit'],'shares')
        self.assertIsNone(values['CERA']['change_pct'])
        with self.assertRaises(SourceError):parse_eod(body,self.day-timedelta(days=1))
        with self.assertRaises(SourceError):parse_eod(b'<html>Blocked</html>',self.day)
        with self.assertRaises(SourceError):parse_eod(body.replace(b'105.25',b'NaN'),self.day)
    def test_wrong_company_and_attachment_host_rejected(self):
        row={'symbol':'CERA','an_dt':self.day.strftime('%d-%b-%Y')+' 12:00:00','attchmntFile':'https://nsearchives.nseindia.com/corporate/a.pdf'}
        with self.assertRaises(SourceError):parse_announcements(json.dumps([row]).encode(),'INFY',self.day,self.day)
        # An unsupported or missing attachment no longer hides the company's whole feed: the filing stays as
        # metadata, and the attachment is never fetched.
        row['symbol']='INFY';row['attchmntFile']='http://127.0.0.1/private'
        events=parse_announcements(json.dumps([row,{**row,'seq_id':'text-only','attchmntFile':''}]).encode(),'INFY',self.day,self.day)
        self.assertEqual(len(events),2)
        self.assertTrue(all(e['url']=='' and not e['attachment_fetchable'] for e in events))
        store=self.store;store.put('filings',events[0]['id'],events[0],ticker='INFY',published=events[0]['published_at'])
        doc=ensure_document(store,events[0]['id'],client=FixtureClient(store,self.day))
        self.assertEqual(doc['status'],'failed');self.assertIn('no NSE-hosted attachment',doc['error'])
        self.assertEqual([s for s in store.rows('sources') if '127.0.0.1' in s['url']],[])
    def test_rules_keep_unknowns_visible_and_do_not_hide_management_change(self):
        self.assertEqual(priority('Financial Results','')[0],'attention')
        self.assertEqual(priority('Updates','CFO resignation')[0],'attention')
        self.assertEqual(priority('Updates','Newspaper publication')[0],'routine')
        self.assertEqual(priority('Updates','Unrecognised event')[0],'unreviewed')
    def test_scheduled_results_are_not_labelled_as_delivered_results(self):
        ordinary=priority('Board Meeting Intimation','A meeting is scheduled to consider financial results')
        self.assertEqual(ordinary[:2],('routine','scheduled-results'))
        capital=priority('Updates','The meeting is scheduled to consider financial results and raising of funds')
        self.assertEqual(capital[:2],('attention','planned-corporate'))
        actual=priority('Financial Results','The Board meeting held today approved financial results')
        self.assertEqual(actual[:2],('attention','results'))
    def test_configuration_rejects_today_future_and_unbounded_requests(self):
        today=datetime.now(IST).date()
        with self.assertRaises(ValueError):configuration(['INFY'],asof=today.isoformat())
        with self.assertRaises(ValueError):configuration(['NOT-IN-PORTFOLIO'])
        with self.assertRaises(ValueError):configuration(['INFY'],start=(today-timedelta(days=20)).isoformat(),end=today.isoformat())
    def test_incomplete_pdf_never_becomes_an_evidence_passage(self):
        self.run_job(['INFY'])
        store=self.store
        class PartialPDF:
            def get(self,url,kind,limit=None):
                body=b'%PDF-1.4 partial response without a trailer'
                return store.source({'url':url,'final_url':url,'http_status':200,'retrieved_at':utcnow(),'ok':True,'fixture':True},body),body
        doc=ensure_document(store,self.store.rows('filings')[0]['id'],client=PartialPDF())
        self.assertEqual(doc['status'],'failed');self.assertEqual(doc['pages'],[])
        self.assertNotIn('excerpt',doc)
        self.assertIn('end-of-file',doc['error'])
        self.assertEqual(self.store.get('sources',doc['source_id'])['validation'],'failed')
    def test_restart_and_snapshot_recovery_preserve_actual_dates(self):
        self.run_job(['INFY'])
        again=Store(self.temp.name);self.assertEqual(len(again.rows('filings')),1)
        snapshot=Path(self.temp.name)/'snapshot.gz';again.export_snapshot(snapshot)
        restored=Store(Path(self.temp.name)/'restored');self.assertTrue(restored.restore_snapshot(snapshot))
        quote=restored.rows('quotes')[0];self.assertEqual(quote['date'],self.day.isoformat())
        self.assertTrue(restored.get('meta','recovery'));self.assertFalse(restored.blob_path(restored.rows('sources')[0]['sha256']).exists())
        self.assertEqual(live_data(restored)['coverage']['checked'],1)
    def test_actual_failed_response_stays_excluded(self):
        self.run_job(['INFY']);store=self.store
        body=(Path(__file__).parent/'fixtures'/'sunpharma-incomplete-response.bin').read_bytes()
        self.assertEqual(len(body),131072);self.assertTrue(body.startswith(b'%PDF-'))
        self.assertNotIn(b'%%EOF',body[-4096:])
        class ActualFailedSample:
            def get(self,url,kind,limit=None):
                return store.source({'url':url,'final_url':url,'http_status':200,'retrieved_at':utcnow(),'ok':True,'fixture':'actual previously failed response'},body),body
        doc=ensure_document(store,store.rows('filings')[0]['id'],client=ActualFailedSample())
        self.assertEqual(doc['status'],'failed');self.assertNotIn('excerpt',doc)
        self.assertIn('end-of-file',doc['error'])
    def test_downloader_handles_short_reads_and_rejects_truncated_length(self):
        class Response:
            status=200;url='https://nsearchives.nseindia.com/test'
            def __init__(self,length):self.headers={'Content-Length':str(length)};self.parts=[b'first',b'second',b'']
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,amount):return self.parts.pop(0)
        class Opener:
            def __init__(self,length):self.length=length
            def open(self,*args,**kwargs):return Response(self.length)
        with patch('app.adapters.build_opener',return_value=Opener(11)):
            source,body=SourceClient(self.store).get('https://nsearchives.nseindia.com/test','unit-test')
            self.assertEqual(body,b'firstsecond');self.assertEqual(source['bytes'],11)
        with patch('app.adapters.build_opener',return_value=Opener(100)):
            with self.assertRaises(SourceError) as captured:SourceClient(self.store).get('https://nsearchives.nseindia.com/test','unit-test')
            source=self.store.get('sources',captured.exception.request_id)
            self.assertFalse(source['ok']);self.assertEqual(source['bytes'],11)
            self.assertIn('Content-Length',source['validation_error'])
    def test_reference_taxonomy_ranks_material_filings_and_buries_paperwork(self):
        cases={
            ('Analysts/Institutional Investor Meet/Con. Call Updates','Transcript of the discussion on the Unaudited Financial Results for the quarter'):('earnings_call','transcript','attention'),
            ('General Updates',"Audio recording of the discussion on the Unaudited Financial Results at the analyst meet"):('earnings_call','recording','routine'),
            ('Allotment of Securities','allotment of 7683981 securities pursuant to Qualified Institution Placement'):('fund_raise','fund-raise','attention'),
            ('ESOP/ESOS/ESPS','Allotment of 4675598 Shares.'):('unclassified','employee-shares','routine'),
            ('Dividend','Board approves Interim Dividend of Rs. 19 per equity share'):('dividend','dividend','attention'),
            ('Record Date','Record date for the purpose of Dividend is 03-Nov-2026.'):('dividend','record-date','routine'),
            ('Bagging/Receiving of orders/contracts','informed the Exchange about Bagging/Receiving of orders/contracts'):('press_release','order-win','attention'),
            ('Action(s) taken or orders passed','informed the Exchange about Action(s) taken or orders passed'):('litigation','litigation','attention'),
            ('Appointment','Appointment of Mr X as Non- Executive Director of the company'):('management_change','management','attention'),
            ('Press Release','press release titled "Financial Results Q2 and H1 FY 2026-27"'):('results','results-press','attention'),
            ('Copy of Newspaper Publication','Copy of Newspaper Publication'):('unclassified','publication','routine'),
        }
        for (category,description),(kind,rule,tier) in cases.items():
            c=classify(category,description)
            self.assertEqual((c['kind'],c['rule'],c['priority']),(kind,rule,tier),description)
        self.assertGreater(classify('Outcome of Board Meeting','financial results for the quarter')['score'],classify('Updates','Transcript')['score'])
        self.assertEqual(classify('Updates',"regarding 'Infosys wins award'")['title'],'Infosys wins award')
    def test_sunday_file_serving_previous_session_falls_back_instead_of_failing(self):
        friday=self.day
        while friday.weekday()!=4:friday-=timedelta(days=1)
        sunday=friday+timedelta(days=2)
        store=self.store
        class SundayClient(FixtureClient):
            def get(self,url,kind,limit=None):
                if kind=='eod':
                    # NSE serves Friday's rows at Sunday's URL; Saturday is missing.
                    requested=datetime.strptime(url.rsplit('_',1)[1][:8],'%d%m%Y').date()
                    if requested.weekday()==5:raise SourceError('HTTP 404 [request fixture]')
                    self.day=friday
                return super().get(url,kind,limit)
        job=store.begin_job(['INFY'],friday.isoformat(),friday.isoformat(),sunday.isoformat())
        job=run_refresh(store,job,client=SundayClient(store,friday),document_limit=0,history_sessions=0)
        self.assertEqual(job['eod_date'],friday.isoformat())
        self.assertEqual([q['date'] for q in store.rows('quotes')],[friday.isoformat()])
    def test_history_backfill_builds_volume_baseline_and_never_fails_refresh(self):
        store=self.store
        class HistoryClient(FixtureClient):
            def get(self,url,kind,limit=None):
                if kind=='eod':
                    requested=datetime.strptime(url.rsplit('_',1)[1][:8],'%d%m%Y').date()
                    output=io.StringIO();writer=csv.writer(output)
                    writer.writerow(['SYMBOL','SERIES','DATE1','CLOSE_PRICE','PREV_CLOSE','TTL_TRD_QNTY'])
                    volume='30000' if requested==target else '10000'
                    writer.writerow(['INFY','EQ',requested.strftime('%d-%b-%Y'),'103','100',volume])
                    body=output.getvalue().encode()
                    return store.source({'url':url,'final_url':url,'retrieved_at':utcnow(),'http_status':200,'kind':'synthetic-test:eod','ok':True,'fixture':True},body),body
                return super().get(url,kind,limit)
        target=self.day
        while target.weekday()>=5:target-=timedelta(days=1)
        job=store.begin_job(['INFY'],target.isoformat(),target.isoformat(),target.isoformat())
        job=run_refresh(store,job,client=HistoryClient(store,target),document_limit=0,history_sessions=6)
        self.assertEqual(job['status'],'complete');self.assertEqual(len(job['eod_history']['added']),6)
        market=next(c for c in live_data(store)['companies'] if c['ticker']=='INFY')['market']
        self.assertTrue(market['baseline_ready']);self.assertEqual(market['volume_avg'],10000);self.assertEqual(market['volume_ratio'],3.0)
        # Re-running requests nothing already stored.
        again=store.begin_job(['INFY'],target.isoformat(),target.isoformat(),target.isoformat())
        again=run_refresh(store,again,client=HistoryClient(store,target),document_limit=0,history_sessions=6)
        self.assertEqual(again['eod_history']['requested'],0)
        class Broken(HistoryClient):
            def get(self,url,kind,limit=None):
                if kind=='eod' and target.strftime('%d%m%Y') not in url:raise RuntimeError('unexpected adapter fault')
                return super().get(url,kind,limit)
        fresh=Store(Path(self.temp.name)/'broken')
        job=fresh.begin_job(['INFY'],target.isoformat(),target.isoformat(),target.isoformat())
        store=fresh;job=run_refresh(fresh,job,client=Broken(fresh,target),document_limit=0,history_sessions=6)
        self.assertEqual(job['status'],'complete');self.assertIn('error',job['eod_history'])
    def test_snapshot_filings_are_relabelled_with_current_rules(self):
        self.run_job(['INFY'])
        event=self.store.rows('filings')[0]
        event.update(rule_id='push-v2:unknown',priority='unreviewed',title='Updates',category='Allotment of Securities',description='allotment pursuant to Qualified Institution Placement')
        event.pop('kind',None);event.pop('attachment_fetchable',None)
        self.store.put('filings',event['id'],event,ticker='INFY',published=event['published_at'])
        shown=live_data(self.store)['events'][0]
        self.assertEqual((shown['kind'],shown['priority'],shown['title']),('fund_raise','attention','Fund raising'))
        self.assertTrue(shown['attachment_fetchable'])


if __name__=='__main__':unittest.main()
