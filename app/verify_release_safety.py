"""Read-only Git/worktree secret scan. Prints locations only, never matching secret bytes."""
import gzip
import json
import re
import subprocess
from pathlib import Path
from .gemini import load_key
from .store import utcnow

ROOT=Path(__file__).resolve().parents[1]

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
    key=load_key().encode();violations=[];checked=0
    patterns=[rb'AIza[0-9A-Za-z_-]{35}',rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'github_pat_[A-Za-z0-9_]{30,}',
              rb'sk-(?:proj-)?[A-Za-z0-9_-]{30,}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
    def scan(data,location):
        nonlocal checked
        checked+=1
        if data.startswith(b'\x1f\x8b'):
            try:data+=gzip.decompress(data)
            except (OSError,EOFError):pass
        if key and key in data:violations.append({'location':location,'kind':'actual configured key'})
        if any(re.search(pattern,data) for pattern in patterns):violations.append({'location':location,'kind':'credential-shaped material'})
    paths=git('ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0')
    for name in filter(None,paths):
        path=ROOT/name
        if path.is_file():scan(path.read_bytes(),'worktree:'+name)
    objects=git('rev-list','--objects','--all').decode().splitlines()
    # Inspect commits/tags as well as every historical blob. Trees carry filenames only.
    for entry in objects:
        oid=entry.split(' ',1)[0];kind=git('cat-file','-t',oid).strip()
        if kind in (b'blob',b'commit',b'tag'):scan(git('cat-file','-p',oid),'history:'+entry)
    ignored=subprocess.run(['git','check-ignore','-q','.env.local'],cwd=ROOT).returncode==0
    tracked_env=bool(git('ls-files','.env','.env.local').strip())
    if not ignored or tracked_env:violations.append({'location':'.env.local','kind':'not private/ignored'})
    report={'checked_at':utcnow(),'passed':not violations,'objects_and_files_checked':checked,
            'git_history_objects':len(objects),'configured_key_present':bool(key),'env_local_ignored':ignored,
            'env_tracked':tracked_env,'violations':violations,
            'scope':'Exact configured-key bytes and common credential formats in all Git history blobs/commits and tracked/pending public files, including gzip contents. Not a guarantee against every possible secret format.'}
    (ROOT/'app/verification/secret-scan.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)

if __name__=='__main__':main()
