'use strict';
// Real-source mode uses the same navigation, list, cards, dialog and return-state machinery.
let livePollTimer, filingTicket=0, livePollFailures=0;
const ALERT_KEY='finn-alert-settings-v1', SEEN_KEY='finn-alerts-seen-v1', NOTIFIED_KEY='finn-alerts-notified-v1';
const DEFAULT_ALERTS={price:3,volume:2,kinds:['results','management_change','M&A','fund_raise','litigation','credit_rating','pledging','bonus_split']};
const ALERT_KIND_ORDER=['results','management_change','M&A','fund_raise','litigation','credit_rating','pledging','insider_trading','bonus_split','dividend','capex','press_release','earnings_call'];

function readLocal(key,fallback){try{const value=JSON.parse(localStorage.getItem(key)||'null');return value??fallback;}catch{return fallback;}}
function writeLocal(key,value){try{localStorage.setItem(key,JSON.stringify(value));}catch{/* optional per-device preference */}}
function istTime(value) {
  if(!value)return 'Not retrieved';
  const date=new Date(value);if(Number.isNaN(date.getTime()))return 'Not retrieved';
  return new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'}).format(date)+' IST';
}
const shares=n=>typeof n==='number'?n.toLocaleString('en-IN'):'—';
const kindLabel=k=>data.kinds?.[k]||'Filing';
function alertSettings() {
  const saved=readLocal(ALERT_KEY,{})||{};
  const price=Number(saved.price),volume=Number(saved.volume);
  return {price:price>=0.5&&price<=50?price:DEFAULT_ALERTS.price,volume:volume>=1.1&&volume<=20?volume:DEFAULT_ALERTS.volume,
    kinds:Array.isArray(saved.kinds)?saved.kinds.filter(k=>ALERT_KIND_ORDER.includes(k)):DEFAULT_ALERTS.kinds};
}
function saveAlertSettings(update){writeLocal(ALERT_KEY,{...alertSettings(),...update});}
function seenAlerts(){return new Set(readLocal(SEEN_KEY,[]));}
function markSeen(ids){writeLocal(SEEN_KEY,[...new Set([...seenAlerts(),...ids])].slice(-600));}

function liveSourceNote() {
  return `<div class="sample-note"><strong>Official NSE filings and end-of-day prices.</strong> Updated ${escapeHTML(istTime(data.job?.finished_at||data.job?.started_at))}. ${data.autoRefreshEnabled?'':'Manual refresh mode. '}<a href="/?demo=1" target="_blank" rel="noopener">Dated interaction demo ↗</a></div>`;
}
function periodEvents(period,ticker) {
  const now=new Date(data.now).getTime(),span=period==='day'?86400000:7*86400000;
  return data.events.filter(e=>(!ticker||e.ticker===ticker)&&(ticker||ui.digestCompany==='all'||e.ticker===ui.digestCompany)&&
    (period==='window'?e.date>=data.window.start&&e.date<=data.window.end:new Date(e.published_at).getTime()>=now-span));
}
// The brief's default is the last 24 hours; a quiet day falls back to the week instead of an empty screen.
function digestScope() {
  const period=['day','week','window'].includes(ui.period)?ui.period:'day';
  let events=periodEvents(period),fellBack=false;
  if(period==='day'&&!events.length){const week=periodEvents('week');if(week.length){events=week;fellBack=true;}}
  return {events,fellBack,period:fellBack?'week':period};
}
function liveFilteredEvents(ticker){return periodEvents(['day','week','window'].includes(ui.period)?ui.period:'day',ticker).sort((a,b)=>b.published_at.localeCompare(a.published_at));}
const byImportance=(a,b)=>(b.score||0)-(a.score||0)||b.published_at.localeCompare(a.published_at);
const periodName=p=>({day:'last 24 hours',week:'last 7 days',window:'stored window'}[p]||'last 24 hours');

function computeAlerts(events) {
  const settings=alertSettings(),alerts=[];
  for(const c of data.companies) {
    if(ui.digestCompany!=='all'&&c.ticker!==ui.digestCompany)continue;
    const q=c.quote,m=c.market;if(!q)continue;
    if(typeof q.change_pct==='number'&&Math.abs(q.change_pct)>=settings.price)
      alerts.push({id:`price:${c.ticker}:${q.date}`,type:'price',ticker:c.ticker,date:q.date,rank:300+Math.abs(q.change_pct),dir:q.change_pct>0?'up':'down',
        title:`${q.change_pct>0?'Up':'Down'} ${Math.abs(q.change_pct).toFixed(1)}% in a day`,
        detail:`Closed at ${money(q.close)} on ${dateLabel(q.date)}, from ${money(q.previous)}. Your threshold: ±${settings.price}%.`});
    if(m?.baseline_ready&&typeof m.volume_ratio==='number'&&m.volume_ratio>=settings.volume)
      alerts.push({id:`volume:${c.ticker}:${q.date}`,type:'volume',ticker:c.ticker,date:q.date,rank:200+m.volume_ratio,
        title:`Volume ${m.volume_ratio.toFixed(1)}× its recent average`,
        detail:`${shares(q.volume)} shares traded on ${dateLabel(q.date)} vs ${shares(m.volume_avg)} average over the previous ${m.baseline_sessions} sessions. Your threshold: ${settings.volume}×.`});
  }
  for(const e of events) if(e.priority==='attention'&&settings.kinds.includes(e.kind))
    alerts.push({id:'filing:'+e.id,type:'filing',ticker:e.ticker,date:e.date,event:e,rank:e.score||0,title:e.title,detail:e.reason});
  return alerts.sort((a,b)=>b.rank-a.rank||b.date.localeCompare(a.date));
}
function baselineNote() {
  const ready=data.companies.filter(c=>c.market?.baseline_ready).length;
  if(ready)return ready<data.companies.length?`<p class="brief-note">Volume alerts cover ${ready}/15 companies; the rest are still building price history.</p>`:'';
  const have=Math.max(0,...data.companies.map(c=>c.market?.baseline_sessions||0));
  return `<p class="brief-note">Volume alerts start once 5 earlier trading sessions are stored (now ${have}). History is fetched with each refresh.</p>`;
}
function alertRow(a,seen) {
  const icon={price:a.dir==='up'?'▲':'▼',volume:'≋',filing:'◆'}[a.type];
  const fresh=!seen.has(a.id);
  const actions=a.type==='filing'
    ?`<button class="primary compact" data-event="${escapeHTML(a.event.id)}" data-alert="${escapeHTML(a.id)}">Open filing ↗</button>`
    :'';
  return `<article class="alert-row ${a.type} ${a.dir||''}" data-testid="alert-${escapeHTML(a.id)}"><span class="alert-icon" aria-hidden="true">${icon}</span><div class="alert-copy">
    <div class="card-meta"><span class="ticker">${escapeHTML(a.ticker)}</span><span>${fresh?'<span class="badge new">New</span> ':''}${dateLabel(a.date)}${a.type==='filing'?' · '+escapeHTML(kindLabel(a.event.kind)):''}</span></div>
    <h3>${escapeHTML(a.title)}</h3><p>${escapeHTML(a.detail)}</p>
    <div class="routine-actions">${actions}<button class="arrow-button" data-investigate="${escapeHTML(a.ticker)}" data-alert="${escapeHTML(a.id)}">Investigate <span aria-hidden="true">→</span></button></div></div></article>`;
}
function alertSettingsPanel() {
  const s=alertSettings(),notifications='Notification' in window;
  const permission=notifications?Notification.permission:'unsupported';
  return `<details class="alert-settings" id="alert-settings" ${ui.alertSettingsOpen?'open':''}><summary>Alert settings <span>±${s.price}% · ${s.volume}× volume · ${s.kinds.length} filing types</span></summary>
    <div class="threshold-grid"><label for="alert-price">Price move in a day of at least<span class="threshold-input"><input id="alert-price" type="number" inputmode="decimal" min="0.5" max="50" step="0.5" value="${s.price}"><span>%</span></span></label>
    <label for="alert-volume">Volume of at least<span class="threshold-input"><input id="alert-volume" type="number" inputmode="decimal" min="1.1" max="20" step="0.1" value="${s.volume}"><span>× average</span></span></label></div>
    <fieldset class="kind-grid"><legend>Alert me about these filings</legend>${ALERT_KIND_ORDER.map(k=>`<label><input type="checkbox" data-alert-kind="${escapeHTML(k)}" ${s.kinds.includes(k)?'checked':''}> ${escapeHTML(kindLabel(k))}</label>`).join('')}</fieldset>
    <div class="settings-actions">${notifications?`<button class="secondary compact" id="alert-notify" ${permission!=='default'?'disabled':''}>${permission==='granted'?'Browser notifications on':permission==='denied'?'Notifications blocked in browser':'Notify me on this device'}</button>`:''}<button class="text-button" id="alert-reset">Reset to defaults</button></div>
    <p class="brief-note">Saved on this device. Alerts are checked each time the data refreshes${notifications?'; with notifications on, new alerts also arrive while this tab is open':''}.</p></details>`;
}
function renderAlerts(events) {
  const alerts=computeAlerts(events),seen=seenAlerts(),fresh=alerts.filter(a=>!seen.has(a.id));
  return `<section class="alerts" aria-labelledby="alerts-heading"><div class="section-heading"><h2 id="alerts-heading">Alerts</h2><small>${alerts.length?`${alerts.length} triggered${fresh.length?' · '+fresh.length+' new':''}`:'None triggered'}</small></div>
    ${alertSettingsPanel()}${baselineNote()}
    ${alerts.length?alerts.map(a=>alertRow(a,seen)).join('')+(fresh.length?`<button class="text-button" id="alerts-seen">Mark all as seen</button>`:''):
      `<div class="quiet-note">Nothing crossed your thresholds in the ${periodName(digestScope().period)}. Adjust them in Alert settings.</div>`}</section>`;
}
function coverageWarning() {
  const failed=data.companies.filter(c=>c.coverage==='partial').map(c=>c.ticker),missing=data.companies.filter(c=>!c.check).map(c=>c.ticker);
  if(!failed.length&&!missing.length)return '';
  return `<div class="state-label"><strong>${failed.length+missing.length} of 15 didn’t fully update:</strong> ${escapeHTML([...failed,...missing].join(', '))}. Their last saved data is still shown; details under Source coverage.</div>`;
}
function liveCoverage() {
  return `<details class="coverage-details"><summary>Source coverage · ${data.coverage.checked}/15 checked</summary>
    <p class="brief-note">Last attempt per company. “0 returned” means NSE answered with no filings; “failed” means the request itself did not succeed.</p>
    <p class="brief-note">Attachments: ${data.coverage.attachmentsReady} read; ${data.coverage.attachmentsFailed} unavailable; ${data.coverage.attachmentsNotRequested} fetched on first open.</p>
    ${data.companies.map(c=>`<div class="coverage-row"><strong>${c.ticker}</strong><div>${c.check?`<span>Price: ${c.check.eod_status==='passed'?escapeHTML(c.check.eod_date):'failed'}${c.market?` · ${c.market.baseline_sessions} earlier sessions`:''}</span><span>Filings: ${c.check.filings_status==='passed'?c.check.filing_count+' returned':'failed / not checked'}</span><small>${escapeHTML(c.check.start)} → ${escapeHTML(c.check.end)} · ${escapeHTML(istTime(c.check.finished_at))}</small>${c.check.eod_error||c.check.filings_error?`<small class="source-error">${escapeHTML(c.check.eod_error||c.check.filings_error)}</small>`:''}`:'<span>Not refreshed yet</span>'}</div></div>`).join('')}
    ${data.recovery?`<p class="state-label">Started from a saved snapshot (${escapeHTML(istTime(data.recovery.snapshot_exported_at))}) after a server restart. Refresh fetches new data.</p>`:''}
    ${data.storage==='ephemeral'?'<p class="state-label">Free hosting: storage resets when the server sleeps. Data refreshes automatically when you open the app.</p>':''}
    </details>`;
}
function refreshRow() {
  const active=data.activeJob;
  return `<div class="refresh-row"><span class="small-label" id="refresh-status">${active?'UPDATING '+active.completed+'/'+active.tickers.length+' COMPANIES':'EXCHANGE TIMES IN IST'}</span><button class="text-button" id="refresh" ${active||loading?'disabled':''}>${active||loading?'Updating…':'Refresh ↻'}</button></div>`;
}
function renderLiveDigest() {
  const scope=digestScope(),alerts=computeAlerts(scope.events),alerted=new Set(alerts.filter(a=>a.type==='filing').map(a=>a.event.id));
  const attention=scope.events.filter(e=>e.priority==='attention'&&!alerted.has(e.id)).sort(byImportance);
  const other=scope.events.filter(e=>e.priority!=='attention').sort((a,b)=>b.published_at.localeCompare(a.published_at));
  const company=ui.digestCompany==='all'?'All companies':ui.digestCompany;
  $('#main').innerHTML=`<span class="eyebrow">YOUR PORTFOLIO BRIEF</span><h1>Your portfolio,<br>in focus.</h1>
    <p class="subhead">${alerts.length?`${alerts.length} alert${alerts.length>1?'s':''} and ${attention.length} other filing${attention.length===1?'':'s'} worth a look`:attention.length?`${attention.length} filing${attention.length>1?'s':''} worth a look`:'A quiet stretch'} in the ${periodName(scope.period)}.</p>${liveSourceNote()}
    <div class="summary-strip" aria-label="Digest counts"><div><strong>${alerts.length}</strong><small>alerts</small></div><div><strong>${attention.length}</strong><small>worth a look</small></div><div><strong>${other.length}</strong><small>routine</small></div></div>
    ${coverageWarning()}
    <details class="filter-panel" id="digest-filters" ${ui.filtersOpen?'open':''}><summary>Filter <span>${escapeHTML(periodName(scope.period))} · ${escapeHTML(company)}</span></summary><div class="controls"><label>Period<select id="digest-period" aria-label="Digest period"><option value="day" ${ui.period==='day'?'selected':''}>Last 24 hours</option><option value="week" ${ui.period==='week'?'selected':''}>Last 7 days</option><option value="window" ${ui.period==='window'?'selected':''}>Stored window · ${escapeHTML(data.window.start)} → ${escapeHTML(data.window.end)}</option></select></label><label>Company<select id="digest-company" aria-label="Digest company">${companyOptions(ui.digestCompany,true)}</select></label></div>
    <div class="segmented" aria-label="Filing category">${[['all','Everything'],['attention','Important'],['other','Routine']].map(([v,l])=>`<button data-filter="${v}" aria-pressed="${ui.digestView===v}">${l}</button>`).join('')}</div></details>
    ${refreshRow()}
    ${scope.fellBack?`<div class="quiet-note">No filings in the last 24 hours. Showing the last 7 days instead.</div>`:''}
    <div id="digest-results" aria-live="polite" aria-busy="${!!data.activeJob||loading}">${ui.digestView!=='other'?renderAlerts(scope.events):''}${liveDigestResults(scope.events,attention,other)}</div>
    ${liveCoverage()}<p class="small-print">Priority and “why it matters” notes come from transparent filing-type rules, not AI, and are not investment advice. Open the original filing before acting.</p>`;
}
function liveDigestResults(events,attention,other) {
  const showAttention=ui.digestView!=='other',showOther=ui.digestView!=='attention';
  if(!events.length)return `<div class="empty"><h2>No filings in this view.</h2><p>Try a longer period or all companies. If coverage failed above, a quiet view may be incomplete.</p><button class="primary" id="reset-digest">Show last 7 days</button></div>`;
  return `${showAttention?`<div class="section-heading"><h2>Worth a closer look</h2><small>${attention.length} filing${attention.length===1?'':'s'}</small></div>${attention.length?attention.map(liveEventCard).join(''):'<div class="quiet-note">Everything important is already in Alerts above.</div>'}`:''}
    ${showOther&&other.length?`<details class="routine-group" ${ui.digestView==='other'?'open':''}><summary>Routine & other filings <span>${other.length}</span></summary><p class="brief-note">Paperwork, meeting notices and unmatched filings. Kept here so nothing is lost.</p>${other.map(liveRoutineItem).join('')}</details>`:''}`;
}
function liveEventCard(e) {
  const text=e.description||'',short=text.length>280?text.slice(0,277).trimEnd()+'…':text;
  return `<article class="card event-card attention" data-testid="event-${escapeHTML(e.id)}">
    <div class="card-meta"><span class="ticker">${escapeHTML(e.ticker)}</span><span>${dateLabel(e.date)} · ${badge('attention',kindLabel(e.kind))}</span></div>
    <h3>${escapeHTML(e.title)}</h3><p class="filing-text">${escapeHTML(short)}</p>
    <div class="why"><strong>Why it matters</strong>${escapeHTML(e.reason)}</div>
    ${e.document_error?`<div class="state-label"><strong>Attachment unavailable.</strong> ${escapeHTML(e.document_error)}</div>`:''}
    <div class="card-actions">${eventAction(e)}<button class="arrow-button" data-investigate="${escapeHTML(e.ticker)}">Investigate <span aria-hidden="true">→</span></button></div>
    ${ui.read.includes(e.id)?'<div class="read-mark">✓ Opened</div>':''}
  </article>`;
}
function liveRoutineItem(e) {
  return `<article class="routine-item" data-testid="event-${escapeHTML(e.id)}"><div class="card-meta"><span class="ticker">${escapeHTML(e.ticker)}</span><span>${dateLabel(e.date)} · ${badge(e.priority,kindLabel(e.kind))}</span></div>
    <h3>${escapeHTML(e.title)}</h3><p>${escapeHTML(e.reason)}</p><div class="routine-actions"><button class="text-button" data-event="${escapeHTML(e.id)}">Open filing ↗</button><button class="arrow-button" data-investigate="${escapeHTML(e.ticker)}">Company →</button></div></article>`;
}
function renderLiveCompanies() {
  const dates=[...new Set(data.companies.filter(c=>c.quote).map(c=>c.quote.date))].sort();
  $('#main').innerHTML=`<span class="eyebrow">YOUR PORTFOLIO</span><h1>Fifteen companies.<br>One place to start.</h1><p class="subhead">Tap a company to research it from its annual report and earnings call.</p>${liveSourceNote()}
    <div class="field search-wrap"><span aria-hidden="true">⌕</span><input id="company-search" type="search" aria-label="Search 15 companies" placeholder="Search company or NSE ticker" value="${escapeHTML(ui.search)}" autocomplete="off"></div>
    <div class="list-toolbar"><span id="company-count" class="small-label"></span><label>Sort <select id="company-sort" aria-label="Sort companies">${[['name','Company A–Z'],['move-desc','Day move ↓'],['move-asc','Day move ↑'],['volume','Volume vs average'],['coverage','Fetched coverage first']].map(([v,l])=>`<option value="${v}" ${ui.sort===v?'selected':''}>${l}</option>`).join('')}</select></label></div>
    <div class="coverage-note"><span aria-hidden="true">◷</span><div><strong>End of day ${dates.length?dates.map(dateLabel).join(', '):'unavailable'}.</strong> ${data.companies.filter(c=>c.quote).length}/15 prices from NSE’s official daily file. Volume compared with the average of earlier sessions.</div></div><div id="company-results" class="company-list"></div>${liveCoverage()}`;
  renderCompanyResults();
}
function renderLiveInvestigate() {
  return renderPullInvestigate();
}
function eventIds(){return new Set((data?.events||[]).map(e=>e.id));}
async function refreshLive() {
  loading=true;renderLiveDigest();
  try {
    const response=await fetch('/api/refresh',{method:'POST',headers:{'Content-Type':'application/json','X-FINN-Token':data.refreshToken},body:JSON.stringify({tickers:ui.digestCompany==='all'?data.companies.map(c=>c.ticker):[ui.digestCompany]})});
    let result={};try{result=await response.json();}catch{/* non-JSON error page */}
    if(response.status===403)throw new Error('Session expired. Reload the page and try again.');
    if(!response.ok)throw new Error(result.error||'Refresh could not start');
    data.activeJob=result.job;loading=false;renderLiveDigest();pollLiveJob(true);
  } catch(error) {loading=false;renderLiveDigest();announce(error.message);}
}
// While a refresh runs only the status line changes, so the list never moves under the reader's thumb.
async function pollLiveJob(reset=false) {
  clearTimeout(livePollTimer);if(reset)livePollFailures=0;
  const before=eventIds();
  try {
    const response=await fetch('/api/data');if(!response.ok)throw new Error('Refresh status unavailable');
    const next=await response.json();livePollFailures=0;
    if(next.activeJob) {
      data.activeJob=next.activeJob;
      const status=$('#refresh-status');if(status)status.textContent='UPDATING '+next.activeJob.completed+'/'+next.activeJob.tickers.length+' COMPANIES';
      livePollTimer=setTimeout(pollLiveJob,2500);return;
    }
    data=next;
    const added=[...eventIds()].filter(id=>!before.has(id)).length;
    applyLiveUpdate(added);
    notifyNewAlerts();
    announce(next.job?.status==='complete'?`Updated${added?' · '+added+' new filing'+(added>1?'s':''):''}`:`Update finished with gaps · see Source coverage`);
  } catch(error) {
    if(++livePollFailures<=4){livePollTimer=setTimeout(pollLiveJob,3000*livePollFailures);return;}
    announce('Lost contact with the server. Pull to reload.');
  }
}
function applyLiveUpdate(added) {
  if($('#evidence').open||ui.route==='investigate')return; // never rebuild a page the reader is typing or reading in
  if(ui.route==='digest'&&added&&window.scrollY>400){showUpdateBanner(added);const status=$('#refresh-status');if(status)status.textContent='EXCHANGE TIMES IN IST';const button=$('#refresh');if(button){button.disabled=false;button.textContent='Refresh ↻';}return;}
  const y=window.scrollY;render();window.scrollTo(0,y);
}
function showUpdateBanner(added) {
  $('#update-banner')?.remove();
  document.body.insertAdjacentHTML('beforeend',`<button id="update-banner" class="update-banner">${added} new filing${added>1?'s':''} · Show ↑</button>`);
}
function notifyNewAlerts() {
  if(!('Notification' in window)||Notification.permission!=='granted')return;
  const alerts=computeAlerts(digestScope().events),seen=seenAlerts(),notified=new Set(readLocal(NOTIFIED_KEY,[]));
  const fresh=alerts.filter(a=>!seen.has(a.id)&&!notified.has(a.id));
  if(!fresh.length)return;
  try{new Notification('FINN · '+fresh.length+' new alert'+(fresh.length>1?'s':''),{body:fresh.slice(0,3).map(a=>a.ticker+': '+a.title).join('\n'),tag:'finn-alerts'});}catch{/* some mobile browsers need a service worker */}
  writeLocal(NOTIFIED_KEY,[...notified,...fresh.map(a=>a.id)].slice(-600));
}
async function openLiveEvent(eventId) {
  const event=data.events.find(e=>e.id===eventId);if(!event)return;
  const ticket=++filingTicket;
  showEvidence({eventId},true);
  if(!event.url){
    $('.drawer-body').insertAdjacentHTML('afterbegin',`<div class="state-label" role="status">${event.attachment_url?'This filing’s attachment is hosted outside NSE, so FINN does not download it. Use Original source below.':'Filed as text only, with no attachment. The exchange text is shown below.'}</div>`);
    return;
  }
  $('.drawer-body').insertAdjacentHTML('afterbegin','<div id="filing-request" class="state-label" role="status">Fetching the original filing from NSE…</div>');
  try {
    const response=await fetch('/api/filings/'+encodeURIComponent(eventId)+'/evidence');
    let result={};try{result=await response.json();}catch{throw new Error('Unexpected server response');}
    if(!response.ok)throw new Error(result.error||'Filing unavailable');
    data.documents[result.document.id]=result.document;data.evidence[result.evidence.id]=result.evidence;
    const stored=data.events.find(e=>e.id===eventId);if(stored)stored.evidence=result.evidence.id;
    if($('#evidence').open&&ticket===filingTicket)showEvidence({eventId,evidenceId:result.evidence.id},false,true);
  } catch(error) {
    const status=$('#filing-request');
    if($('#evidence').open&&ticket===filingTicket&&status)status.textContent='Could not read the attachment: '+error.message+' The original link below still works.';
  }
}
document.addEventListener('change',event=>{
  if(!IS_LIVE||!data)return;
  const t=event.target;
  if(t.id==='alert-price'||t.id==='alert-volume'){
    const value=Number(t.value);
    const ok=t.id==='alert-price'?value>=0.5&&value<=50:value>=1.1&&value<=20;
    if(!ok){announce(t.id==='alert-price'?'Use a price threshold between 0.5% and 50%':'Use a volume threshold between 1.1× and 20×');t.value=alertSettings()[t.id==='alert-price'?'price':'volume'];return;}
    saveAlertSettings({[t.id==='alert-price'?'price':'volume']:value});rerenderDigestInPlace('#'+t.id);
  } else if(t.dataset?.alertKind){
    const kinds=new Set(alertSettings().kinds);t.checked?kinds.add(t.dataset.alertKind):kinds.delete(t.dataset.alertKind);
    saveAlertSettings({kinds:[...kinds]});rerenderDigestInPlace(`[data-alert-kind="${t.dataset.alertKind}"]`);
  }
});
function rerenderDigestInPlace(focusSelector) {
  const y=window.scrollY;renderLiveDigest();window.scrollTo(0,y);
  if(focusSelector)$(focusSelector)?.focus({preventScroll:true});
}
document.addEventListener('toggle',event=>{if(event.target.id==='alert-settings'){ui.alertSettingsOpen=event.target.open;persist();}},true);
document.addEventListener('click',async event=>{
  if(!IS_LIVE||!data)return;
  const button=event.target.closest('button');if(!button)return;
  if(button.dataset.alert)markSeen([button.dataset.alert]);
  if(button.id==='alerts-seen'){markSeen(computeAlerts(digestScope().events).map(a=>a.id));rerenderDigestInPlace();announce('Alerts marked as seen');}
  else if(button.id==='alert-reset'){writeLocal(ALERT_KEY,DEFAULT_ALERTS);rerenderDigestInPlace();announce('Alert settings reset');}
  else if(button.id==='update-banner'){button.remove();render();window.scrollTo(0,0);}
  else if(button.id==='alert-notify'&&'Notification' in window){
    try{const permission=await Notification.requestPermission();
      if(permission==='granted'){writeLocal(NOTIFIED_KEY,computeAlerts(digestScope().events).map(a=>a.id));announce('Notifications on for this device');}
    }catch{announce('This browser does not allow notifications here');}
    rerenderDigestInPlace();
  }
});
