"""Small SQLite store with immutable raw responses and explicit refresh leases."""
import gzip
import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class BusyRefresh(Exception):
    def __init__(self, job):
        self.job = job


class Store:
    TABLES = ('sources', 'quotes', 'filings', 'documents', 'checks', 'jobs', 'research')
    LOCAL_TABLES = ('answers','model_calls')  # Private local cache/audit; never exported into bootstrap.

    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / 'raw').mkdir(exist_ok=True)
        self.path = self.directory / 'finn.sqlite3'
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS quotes(id TEXT PRIMARY KEY, ticker TEXT, session TEXT, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS quote_ticker ON quotes(ticker,session);
                CREATE TABLE IF NOT EXISTS filings(id TEXT PRIMARY KEY, ticker TEXT, published TEXT, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS filing_ticker ON filings(ticker,published);
                CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,event_id TEXT,checked_at TEXT,payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS document_event ON documents(event_id,checked_at);
                CREATE TABLE IF NOT EXISTS checks(id TEXT PRIMARY KEY,ticker TEXT,job_id TEXT,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,status TEXT,started_at TEXT,expires_at TEXT,payload TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS one_running_refresh ON jobs(status) WHERE status='running';
                CREATE TABLE IF NOT EXISTS meta(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS research(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS answers(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS model_calls(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE VIRTUAL TABLE IF NOT EXISTS research_chunks USING fts5(doc_id UNINDEXED, ticker UNINDEXED, page UNINDEXED, chunk_id UNINDEXED, text);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:yield db
        finally:db.close()

    def put(self, table, key, payload, **columns):
        if table not in self.TABLES + self.LOCAL_TABLES + ('meta',):
            raise ValueError('Unknown storage table')
        fields = {'id': key, **columns, 'payload': json.dumps(payload, ensure_ascii=False)}
        keys = list(fields)
        with self.connect() as db:
            db.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)}) ON CONFLICT(id) DO UPDATE SET " + ','.join(f'{k}=excluded.{k}' for k in keys if k!='id'), list(fields.values()))

    def get(self, table, key):
        if table not in self.TABLES + self.LOCAL_TABLES + ('meta',): raise ValueError('Unknown storage table')
        with self.connect() as db:
            row = db.execute(f'SELECT payload FROM {table} WHERE id=?', (key,)).fetchone()
        return json.loads(row['payload']) if row else None

    def rows(self, table):
        if table not in self.TABLES + self.LOCAL_TABLES: raise ValueError('Unknown storage table')
        with self.connect() as db:
            return [json.loads(r['payload']) for r in db.execute(f'SELECT payload FROM {table}')]

    def blob_path(self, sha):
        if len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha): raise ValueError('Invalid content hash')
        return self.directory / 'raw' / (sha + '.bin')

    def source(self, record, body):
        record = dict(record, id=uuid.uuid4().hex, sha256=hashlib.sha256(body).hexdigest(), bytes=len(body), validation='pending')
        path = self.blob_path(record['sha256'])
        if not path.exists():
            temporary = path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
            temporary.write_bytes(body)
            temporary.replace(path)
        self.put('sources', record['id'], record)
        return record

    def validate_source(self, source_id, ok, error=None):
        row=self.get('sources',source_id)
        row.update(validation='passed' if ok else 'failed',validation_error=error)
        self.put('sources',source_id,row)

    def active_job(self):
        with self.connect() as db:
            row=db.execute("SELECT payload FROM jobs WHERE status='running'").fetchone()
        if not row: return None
        job=json.loads(row['payload'])
        if job['expires_at'] < utcnow():
            job.update(status='interrupted',finished_at=utcnow(),error='Refresh lease expired; source outcomes may be incomplete.')
            self.save_job(job)
            return None
        return job

    def begin_job(self, tickers, start, end, asof):
        active=self.active_job()
        if active: raise BusyRefresh(active)
        now=datetime.now(timezone.utc)
        job=dict(id=uuid.uuid4().hex,status='running',started_at=now.isoformat(),expires_at=(now+timedelta(minutes=6)).isoformat(),
                 tickers=tickers,start=start,end=end,requested_eod=asof,completed=0,errors=[],finished_at=None)
        try:
            self.put('jobs',job['id'],job,status=job['status'],started_at=job['started_at'],expires_at=job['expires_at'])
        except sqlite3.IntegrityError:
            raise BusyRefresh(self.active_job())
        return job

    def save_job(self, job):
        self.put('jobs',job['id'],job,status=job['status'],started_at=job['started_at'],expires_at=job['expires_at'])

    def latest_job(self):
        jobs=self.rows('jobs')
        return max(jobs,key=lambda j:j['started_at']) if jobs else None

    def export_snapshot(self, destination):
        # Public source records only. Raw PDFs, cookies, env and user/browser state are never exported.
        snapshot={'format':1,'exported_at':utcnow(),'tables':{t:self.rows(t) for t in self.TABLES}}
        with gzip.open(destination,'wt',encoding='utf-8') as f:json.dump(snapshot,f,ensure_ascii=False)
        return snapshot

    def restore_snapshot(self, path):
        if self.rows('jobs') or not Path(path).exists(): return False
        with gzip.open(path,'rt',encoding='utf-8') as f: snapshot=json.load(f)
        if snapshot.get('format')!=1: raise ValueError('Unsupported recovery snapshot')
        for table, rows in snapshot['tables'].items():
            if table not in self.TABLES: continue
            for row in rows:
                if table=='quotes':
                    self.put(table,row['id'],row,ticker=row['ticker'],session=row['date'])
                elif table=='filings':self.put(table,row['id'],row,ticker=row['ticker'],published=row['published_at'])
                elif table=='documents':self.put(table,row['id'],row,event_id=row['event_id'],checked_at=row['checked_at'])
                elif table=='checks':self.put(table,row['id'],row,ticker=row['ticker'],job_id=row['job_id'])
                elif table=='research':self.put(table,row['ticker'],row)
                elif table=='jobs':
                    if row['status']=='running':row.update(status='interrupted',error='Interrupted snapshot job')
                    self.save_job(row)
                else:self.put(table,row['id'],row)
        self.put('meta','recovery',{'restored_at':utcnow(),'snapshot_exported_at':snapshot['exported_at'],
                                  'note':'Restored dated source metadata/text. Raw response/PDF files are not bundled. New retrieval timestamps change only after real requests.'})
        return True
