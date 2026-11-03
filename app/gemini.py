"""Fixed Gemini Free-Tier model transport. Secrets never enter URLs, storage or errors."""
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.request import Request,build_opener,HTTPRedirectHandler

MODEL='gemini-3.5-flash-lite'
ENDPOINT='https://generativelanguage.googleapis.com/v1beta/models/'+MODEL+':generateContent'
ROOT=Path(__file__).resolve().parents[1]


def load_key():
    # Parse only this one named value, never source/evaluate a shell dotenv file.
    key=os.environ.get('GEMINI_API_KEY','').strip()
    if key:return key
    path=ROOT/'.env.local'
    if not path.is_file():return ''
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        name,separator,value=line.partition('=')
        if separator and name.strip()=='GEMINI_API_KEY':
            value=value.strip()
            if len(value)>=2 and value[0]==value[-1] and value[0] in ('\x22','\x27'):value=value[1:-1]
            return value.strip()
    return ''


class ModelUnavailable(Exception):pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ModelUnavailable('Gemini redirect rejected; no credential forwarded')


class GeminiClient:
    def __init__(self,key=None):self._key=load_key() if key is None else key
    def __repr__(self):return 'GeminiClient(model='+MODEL+', credentials=<redacted>)'
    @property
    def configured(self):return bool(self._key)
    def generate(self,system,payload,schema,max_tokens=1600):
        if not self.configured:raise ModelUnavailable('Gemini key is not configured on the server')
        request_body={'systemInstruction':{'parts':[{'text':system}]},
            'contents':[{'role':'user','parts':[{'text':json.dumps(payload,ensure_ascii=False)}]}],
            'generationConfig':{'responseMimeType':'application/json','responseJsonSchema':schema,
                'temperature':.1,'maxOutputTokens':max_tokens,'thinkingConfig':{'thinkingLevel':'minimal'}}}
        request=Request(ENDPOINT,data=json.dumps(request_body).encode('utf-8'),method='POST',
            headers={'Content-Type':'application/json','x-goog-api-key':self._key})
        started=time.monotonic()
        try:
            with build_opener(NoRedirect()).open(request,timeout=35) as response:
                raw=response.read(100_001)
                if len(raw)>100_000:raise ModelUnavailable('Gemini response exceeded the bounded response limit')
                if self._key.encode() in raw:raise ModelUnavailable('Secret-like provider output rejected')
                result=json.loads(raw)
        except HTTPError as error:
            # Never expose the provider body, request object, headers or arbitrary exception text.
            labels={400:'request configuration rejected',401:'credentials rejected',403:'project/model access denied',
                    404:'selected model unavailable',429:'free quota/rate limit reached; no paid fallback'}
            error.close()
            raise ModelUnavailable('Gemini HTTP '+str(error.code)+': '+labels.get(error.code,'provider unavailable')) from None
        except (URLError,TimeoutError,OSError):raise ModelUnavailable('Gemini network/timeout failure; retrieval remains available') from None
        except (ValueError,KeyError):raise ModelUnavailable('Gemini returned an unreadable response') from None
        if not isinstance(result,dict):raise ModelUnavailable('Gemini returned an invalid response structure')
        candidates=result.get('candidates',[])
        if not isinstance(candidates,list) or any(not isinstance(c,dict) for c in candidates):raise ModelUnavailable('Gemini returned invalid candidates')
        if not candidates or candidates[0].get('finishReason')!='STOP':raise ModelUnavailable('Gemini answer blocked or incomplete; no partial answer published')
        text=''.join(p.get('text','') for p in candidates[0].get('content',{}).get('parts',[]) if not p.get('thought'))
        if self._key in text:raise ModelUnavailable('Secret-like provider output rejected')
        try:answer=json.loads(text)
        except ValueError:raise ModelUnavailable('Gemini did not return valid structured JSON') from None
        return answer,{'model':MODEL,'seconds':round(time.monotonic()-started,3),
            'usage':{k:v for k,v in result.get('usageMetadata',{}).items() if k in ('promptTokenCount','candidatesTokenCount','thoughtsTokenCount','totalTokenCount') and isinstance(v,int)},
            'model_version':result.get('modelVersion',MODEL)}


def status():
    return {'available':bool(load_key()),'provider':'Google Gemini','model':MODEL,
            'reason':'Server-side source-grounded Gemini answers; fixed model, no tools or paid fallback.' if load_key() else 'Gemini key is not configured; original passage search remains available.'}


def smoke():
    schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
    answer,metadata=GeminiClient().generate('Return only the requested JSON.',{'instruction':'Set ok to true.'},schema,max_tokens=128)
    if answer!={'ok':True}:raise ModelUnavailable('Minimal structured-output check failed')
    report={'status':'passed','check':'minimal real structured Gemini call','answer':answer,**metadata}
    (ROOT/'app'/'verification'/'gemini-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':
    try:smoke()
    except ModelUnavailable as error:print(json.dumps({'status':'unavailable','error':str(error)}));raise SystemExit(1)
