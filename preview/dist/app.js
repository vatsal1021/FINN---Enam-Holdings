'use strict';
const IS_LIVE = document.querySelector('meta[name="finn-mode"]')?.content === 'live';
const STORAGE_KEY = IS_LIVE ? 'finn-live-v2' : 'finn-preview-v1';
const $ = (selector) => document.querySelector(selector);
const escapeHTML = (value = '') => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = (n) => '₹' + n.toLocaleString('en-IN', {minimumFractionDigits:2, maximumFractionDigits:2});
const badgeText = {saved:'Saved sources', stale:'Stale call', partial:'Partial coverage', missing:'Not loaded', attention:'For review', routine:'Routine', unreviewed:'Unreviewed'};
const badge = (status, text) => `<span class="badge ${escapeHTML(status)}">${escapeHTML(text || badgeText[status] || status)}</span>`;
const dateLabel = date => new Date(date + 'T12:00:00+05:30').toLocaleDateString('en-GB', {day:'numeric', month:'short'});
const defaults = {route:'digest', period:IS_LIVE?'day':'week', digestCompany:'all', digestView:'all', filtersOpen:false, alertSettingsOpen:false, search:'', sort:'name', company:'INFY', question:'snapshot', positions:{digest:0, companies:0, investigate:0}, read:[]};
let data, ui = structuredClone(defaults), loading = false, modalOrigin = null, modalY = 0, toastTimer, scrollTimer;

try {
  const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
  if (saved) ui = {...defaults, ...saved, positions:{...defaults.positions, ...saved.positions}};
} catch { /* A disabled browser store does not prevent use. */ }
if (!['digest','companies','investigate'].includes(ui.route)) ui.route = 'digest';
history.scrollRestoration = 'manual';

function persist() {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(ui)); } catch { /* optional persistence */ }
}
function snapshot() { return structuredClone(ui); }
function currentHash() { return '#' + ui.route + (ui.route === 'investigate' ? '/' + ui.company : ''); }
function remember() {
  if ($('#evidence').open) return;
  if (!$('#evidence').open) ui.positions[ui.route] = window.scrollY;
  persist();
  history.replaceState({ui:snapshot()}, '', currentHash());
}
function announce(message) {
  $('#toast').textContent = message; $('#toast').classList.add('visible');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').classList.remove('visible'), 3200);
}
function company(ticker = ui.company) { return data.companies.find(c => c.ticker === ticker); }
function navigate(route, ticker, reset = false) {
  remember();
  ui.route = route;
  if (ticker) { if (ui.company !== ticker) ui.positions.investigate = 0; ui.company = ticker; ui.question = 'snapshot'; }
  if (reset) ui.positions[route] = 0;
  history.pushState({ui:snapshot()}, '', currentHash());
  persist(); render();
  requestAnimationFrame(() => { window.scrollTo(0, ui.positions[route] || 0); $('#main').focus({preventScroll:true}); });
}
function sampleNote() {
  if (IS_LIVE) return liveSourceNote();
  return `<div class="sample-note"><strong>Saved samples · October 2026.</strong> Manually authored summaries and priorities. No live feed or AI response.</div>`;
}
function companyOptions(selected, includeAll = false) {
  return (includeAll ? `<option value="all">All 15 companies</option>` : '') + [...data.companies].sort((a,b) => a.name.localeCompare(b.name)).map(c => `<option value="${c.ticker}" ${selected===c.ticker?'selected':''}>${escapeHTML(c.name)} · ${c.ticker}</option>`).join('');
}
function filteredEvents() {
  const starts = {week:'2026-10-22', month:'2026-10-01', day:'2026-10-29', empty:'2026-10-30'};
  const end = ui.period === 'empty' ? '2026-10-30' : '2026-10-29';
  return data.events.filter(e => e.date >= (starts[ui.period] || starts.week) && e.date <= end && (ui.digestCompany === 'all' || e.ticker === ui.digestCompany))
    .sort((a,b) => b.time.localeCompare(a.time));
}
function eventAction(e) {
  return `<button class="primary" data-event="${e.id}">${e.evidence?'Review evidence':'Open filing'} <span aria-hidden="true">↗</span></button>`;
}
function eventCard(e) {
  return `<article class="card event-card attention" data-testid="event-${e.id}">
    <div class="card-meta"><span class="ticker">${escapeHTML(e.ticker)}</span><span>${dateLabel(e.date)} · ${badge('attention')}</span></div>
    <h3>${escapeHTML(e.title)}</h3>${IS_LIVE?'<div class="small-label">EXCHANGE DESCRIPTION · NOT AN AI SUMMARY</div>':''}<p>${escapeHTML(IS_LIVE?e.description:e.summary)}</p>
    <div class="why"><strong>Why it is here</strong>${escapeHTML(e.reason)}</div>
    ${IS_LIVE&&e.document_error?`<div class="state-label"><strong>Attachment unavailable.</strong> ${escapeHTML(e.document_error)} Original source remains accessible.</div>`:''}
    <div class="card-actions">${eventAction(e)}<button class="arrow-button" data-investigate="${e.ticker}">Investigate <span aria-hidden="true">→</span></button></div>
    ${ui.read.includes(e.id)?'<div class="read-mark">✓ Evidence opened in this session</div>':''}
  </article>`;
}
function routineItem(e) {
  return `<article class="routine-item" data-testid="event-${e.id}"><div class="card-meta"><span class="ticker">${e.ticker}</span><span>${dateLabel(e.date)} · ${badge(e.priority)}</span></div>
    <h3>${escapeHTML(e.title)}</h3><p>${escapeHTML(e.reason)}</p><div class="routine-actions"><button class="text-button" data-event="${e.id}">${e.evidence?'Read notice':'Open filing details'} ↗</button><button class="arrow-button" data-investigate="${e.ticker}">Company →</button></div></article>`;
}
function renderDigest() {
  if (IS_LIVE) return renderLiveDigest();
  const events = filteredEvents(), attention = events.filter(e=>e.priority==='attention'), other = events.filter(e=>e.priority!=='attention');
  $('#main').innerHTML = `<span class="eyebrow">YOUR PORTFOLIO BRIEF</span><h1>Your portfolio,<br>in focus.</h1><p class="subhead">What deserves a closer look across your fifteen companies.</p>${sampleNote()}
    <div class="summary-strip" aria-label="Saved example counts"><div><strong>${attention.length}</strong><small>items for review</small></div><div><strong>${other.length}</strong><small>other saved filings</small></div><div><strong>4<span class="denominator"> / 15</span></strong><small>companies sampled</small></div></div>
    <details class="filter-panel" id="digest-filters" ${ui.filtersOpen?'open':''}><summary>Filter filings <span>${{week:'22–29 Oct',month:'October',day:'29 Oct',empty:'30 Oct'}[ui.period]} · ${ui.digestCompany==='all'?'All companies':ui.digestCompany}</span></summary><div class="controls"><label>Saved date window<select id="digest-period" aria-label="Saved date window"><option value="week" ${ui.period==='week'?'selected':''}>22–29 Oct 2026</option><option value="month" ${ui.period==='month'?'selected':''}>October 2026</option><option value="day" ${ui.period==='day'?'selected':''}>29 Oct 2026</option><option value="empty" ${ui.period==='empty'?'selected':''}>30 Oct · empty sample</option></select></label><label>Company<select id="digest-company" aria-label="Digest company">${companyOptions(ui.digestCompany,true)}</select></label></div>
    <div class="segmented" aria-label="Filing category">${[['all','All filings'],['attention','For review'],['other','Other & routine']].map(([value,label])=>`<button data-filter="${value}" aria-pressed="${ui.digestView===value}">${label}</button>`).join('')}</div></details>
    <div class="refresh-row"><span class="small-label">${loading?'SIMULATED LOADING STATE':'SAVED EXAMPLES · TIMES IN IST'}</span><button class="text-button" id="refresh" ${loading?'disabled':''}>${loading?'Loading saved sample…':'Replay loading ↻'}</button></div>
    <div id="digest-results" aria-live="polite" aria-busy="${loading}">${loading ? `<p class="brief-note">Preview simulation · no network refresh is running.</p>${[1,2].map(()=>'<div class="skeleton" aria-hidden="true"><div></div><div></div><div></div><div></div></div>').join('')}` : digestResults(events, attention, other)}</div>
    <div class="coverage-note"><span aria-hidden="true">◌</span><div><strong>Coverage, not silence.</strong> Eight selected filing examples from three companies; market-data samples for four. The other eleven companies have not been loaded. This is not a complete exchange feed. <button class="text-button" data-route="companies">Inspect all 15 →</button></div></div>`;
}
function digestResults(events, attention, other) {
  const showAttention = ui.digestView !== 'other', showOther = ui.digestView !== 'attention';
  if (!(showAttention && attention.length) && !(showOther && other.length)) {
    return `<div class="empty"><div class="empty-symbol" aria-hidden="true">—</div><h2>No saved items in this view.</h2><p>${events.length?'The current category has no examples.':'No examples match these filters. This does not establish that no exchange announcements occurred.'}</p><button class="primary" id="reset-digest">Show sample window</button></div>`;
  }
  return `${showAttention && attention.length ? `<div class="section-heading"><h2>Worth a closer look</h2><small>${attention.length} saved examples</small></div>${attention.map(eventCard).join('')}`:''}
    ${showOther && other.length ? `<div class="section-heading"><h2>Other filings</h2><small>${other.length} available</small></div><p class="brief-note">Routine and unreviewed items stay accessible. Priority is manually assigned for this preview.</p>${other.map(routineItem).join('')}`:''}`;
}
function renderCompanies() {
  if (IS_LIVE) return renderLiveCompanies();
  $('#main').innerHTML = `<span class="eyebrow">YOUR RESEARCH UNIVERSE</span><h1>Fifteen companies.<br>One place to start.</h1><p class="subhead">A mock portfolio. Open any company to inspect its saved research coverage.</p>${sampleNote()}
    <div class="field search-wrap"><span aria-hidden="true">⌕</span><input id="company-search" type="search" aria-label="Search 15 companies" placeholder="Search company or NSE ticker" value="${escapeHTML(ui.search)}" autocomplete="off"></div>
    <div class="list-toolbar"><span id="company-count" class="small-label"></span><label>Sort <select id="company-sort" aria-label="Sort companies"><option value="name" ${ui.sort==='name'?'selected':''}>Company A–Z</option><option value="move-desc" ${ui.sort==='move-desc'?'selected':''}>Day move ↓</option><option value="move-asc" ${ui.sort==='move-asc'?'selected':''}>Day move ↑</option><option value="coverage" ${ui.sort==='coverage'?'selected':''}>Saved coverage first</option></select></label></div>
    <div class="coverage-note"><span aria-hidden="true">◷</span><div><strong>EOD: 29 Oct 2026.</strong> Official NSE close and volume saved for 4/15. Day move uses previous close. Missing values remain unavailable.</div></div>
    <div id="company-results" class="company-list"></div><p class="small-print">Prices: INR/share. Volume: traded shares. No holdings, position sizes, portfolio returns or live prices are implied.</p>`;
  renderCompanyResults();
}
function change(c) { return c.quote ? (IS_LIVE ? c.quote.change_pct : c.quote.previous>0 ? (c.quote.close / c.quote.previous - 1) * 100 : null) : null; }
function renderCompanyResults() {
  const term = ui.search.trim().toLowerCase();
  let rows = data.companies.filter(c => (c.name+' '+c.ticker+' '+c.sector).toLowerCase().includes(term));
  rows.sort((a,b) => {
    if (ui.sort.startsWith('move')) {
      if (change(a)===null || change(b)===null) return Number(change(a)===null) - Number(change(b)===null) || a.name.localeCompare(b.name);
      return (change(a)-change(b))*(ui.sort==='move-desc'?-1:1);
    }
    if (ui.sort==='volume') { const r=c=>c.market?.baseline_ready&&typeof c.market.volume_ratio==='number'?c.market.volume_ratio:-1; return r(b)-r(a) || a.name.localeCompare(b.name); }
    if (ui.sort==='coverage') return (IS_LIVE ? Number(a.coverage!=='saved')-Number(b.coverage!=='saved') : Number(!data.briefs[a.ticker])-Number(!data.briefs[b.ticker])) || a.name.localeCompare(b.name);
    return a.name.localeCompare(b.name);
  });
  $('#company-count').textContent = `${rows.length} of 15 companies`;
  $('#company-results').innerHTML = rows.length ? rows.map(c => `<button class="company-row" data-investigate="${c.ticker}" data-testid="company-${c.ticker}" aria-label="Investigate ${escapeHTML(c.name)}"><span class="monogram" aria-hidden="true">${escapeHTML(c.name.split(' ').map(n=>n[0]).join('').slice(0,2))}</span><span class="company-copy"><strong>${escapeHTML(c.name)}</strong><small>${c.ticker} · ${escapeHTML(c.sector)}</small>${badge(c.coverage,IS_LIVE?(c.coverage==='saved'?'Sources fetched':c.coverage==='partial'?'Check coverage':'Not checked'):null)}</span><span class="company-price">${c.quote?`${money(c.quote.close)}<small class="${change(c)>=0?'up':'down'}">${change(c)===null?'Change unavailable':(change(c)>=0?'+':'')+change(c).toFixed(2)+'%'}</small>${IS_LIVE?'<small>'+(c.market?.baseline_ready&&typeof c.market.volume_ratio==='number'?'Vol '+c.market.volume_ratio.toFixed(1)+'× avg · ':'')+dateLabel(c.quote.date)+'</small>':''}`:'<small>Price unavailable</small>'}<small aria-hidden="true">Open →</small></span></button>`).join('') : `<div class="empty"><h2>No matching company.</h2><p>Search one of the fifteen selected names or NSE tickers.</p><button class="secondary" id="clear-search">Clear search</button></div>`;
}
function renderInvestigate() {
  if (IS_LIVE) return renderLiveInvestigate();
  const c = company(), brief = data.briefs[c.ticker];
  let facts = brief?.facts || [];
  if (ui.question==='management') facts = facts.filter(f=>!['Business','Annual-report context'].includes(f.label));
  $('#main').innerHTML = `<button class="back-link" id="return-view">← Back to previous view</button><div class="eyebrow">COMPANY INVESTIGATION</div>
    <div class="field"><label for="research-company">Selected company</label><select id="research-company">${companyOptions(ui.company)}</select></div>
    <div class="company-identity"><span class="monogram" aria-hidden="true">${c.name.split(' ').map(n=>n[0]).join('').slice(0,2)}</span><div><h1 class="company-title">${escapeHTML(c.name)}</h1><small>NSE: ${c.ticker} · ${escapeHTML(c.sector)}</small></div></div>
    ${c.quote?`<div class="quote-strip"><strong>${money(c.quote.close)}</strong><span class="${change(c)>=0?'up':'down'}">${change(c)>=0?'+':''}${change(c).toFixed(2)}%</span><small>EOD · 29 Oct 2026</small></div><p class="brief-note">Volume: ${c.quote.volume.toLocaleString('en-IN')} shares · <a href="${c.quote.source}" target="_blank" rel="noopener noreferrer">NSE daily file ↗</a></p>`:''}
    ${sampleNote()}
    ${brief?`<div class="coverage-note"><span aria-hidden="true">${c.coverage==='saved'?'◉':'◷'}</span><div><strong>${badgeText[c.coverage]}.</strong> ${escapeHTML(brief.coverage)}</div></div>
      <div class="small-label">CHOOSE A SAVED RESEARCH VIEW</div><div class="question-grid"><button data-question="snapshot" aria-pressed="${ui.question==='snapshot'}">Business & key observations</button><button data-question="management" aria-pressed="${ui.question==='management'}">Management comments & gaps</button></div>
      <article class="card brief-card"><span class="eyebrow">MANUALLY AUTHORED SAMPLE BRIEF</span><h2 class="brief-headline">${escapeHTML(brief.headline)}</h2><p class="brief-note">${escapeHTML(brief.date)}</p>${facts.map(f=>`<section class="fact"><div class="fact-label">${escapeHTML(f.label)}</div><p>${escapeHTML(f.text)}</p><button class="cite" data-evidence="${f.evidence}">↗ Evidence · ${escapeHTML(data.evidence[f.evidence].label)}</button></section>`).join('')}</article>
      <div class="section-heading"><h2>Source coverage</h2><small>${brief.documents.length} saved documents</small></div><div class="source-list">${brief.documents.map(id=>sourceRow(id)).join('')}</div>`:
      `<div class="empty"><div class="empty-symbol" aria-hidden="true">◌</div><h2>No research loaded.</h2><p>${escapeHTML(c.name)} is in the mock portfolio, but its documents and prices were not saved in the experiments. No AI answer or company conclusions have been generated.</p><button class="primary" data-investigate="INFY">Try the Infosys sample</button></div>`}
    <p class="small-print">Preview only: choosing a view selects saved, manually written content. There is no live research engine, company discovery, model call or refresh. This preview does not satisfy the final generalisation requirement.</p>`;
}
function sourceRow(id) {
  const doc = data.documents[id];
  return `<button class="source-row" data-document="${id}"><span aria-hidden="true">▧</span><span><strong>${escapeHTML(doc.title)}</strong><small>${escapeHTML(doc.kind)} · ${escapeHTML(doc.date)}</small></span>${badge(doc.status, doc.status==='saved'?'Saved':null)}<span aria-hidden="true">↗</span></button>`;
}
function render() {
  if (!data) return;
  $('.bottom-nav').querySelectorAll('button').forEach(b=>{ if (b.dataset.route===ui.route) b.setAttribute('aria-current','page'); else b.removeAttribute('aria-current'); });
  if (ui.route==='digest') renderDigest(); else if (ui.route==='companies') renderCompanies(); else renderInvestigate();
}

function showEvidence({evidenceId, eventId, docId, quote}, push = true, update = false) {
  const event = data.events.find(e=>e.id===eventId);
  const ev = data.evidence[evidenceId || event?.evidence];
  const doc = data.documents[docId || ev?.doc];
  const title = ev?.label || event?.title || doc?.title;
  const page = ev?.page || doc?.pages[0]?.number;
  if (!update) { modalOrigin = document.activeElement; modalY = window.scrollY; }
  if (push) {
    remember();
    history.pushState({ui:snapshot(), modal:{evidenceId,eventId,docId,quote}}, '', currentHash()+'/evidence');
  }
  if (eventId && !ui.read.includes(eventId)) { ui.read.push(eventId); persist(); }
  const ticker = event?.ticker || doc?.ticker || ev?.ticker;
  const sourceURL = doc?.url || event?.url || event?.attachment_url || (ticker ? 'https://www.nseindia.com/get-quotes/equity?symbol='+encodeURIComponent(ticker) : 'https://www.nseindia.com/companies-listing/corporate-filings-announcements');
  const host = (() => { try { return new URL(sourceURL).hostname; } catch { return 'Exchange record'; } })();
  const context = ev?.context || doc?.note || (IS_LIVE?'Exchange metadata is available. The original attachment will be fetched and validated before a passage is shown. No AI summary is generated.':'Only exchange metadata was saved for this example. No PDF passage or AI summary is available. The original filing may contain information not reflected in this preview.');
  const passage = quote || ev?.passage || doc?.pages[0]?.text;
  $('#evidence-content').innerHTML = `<div class="drawer-head"><div><span class="eyebrow">${doc?'PRIMARY-SOURCE EVIDENCE':'SAVED EXCHANGE METADATA'}</span><h2 id="evidence-title">${escapeHTML(title)}</h2></div><button class="close-drawer" id="close-evidence" aria-label="Close evidence and return">×</button></div>
    <div class="drawer-body"><dl class="source-meta"><dt>Document</dt><dd>${escapeHTML(doc?.title || event?.category)}</dd><dt>Period / date</dt><dd>${escapeHTML(doc?.period || event?.time)}${doc?' · '+escapeHTML(doc.date):IS_LIVE?'':' IST'}</dd>${page?`<dt>PDF page</dt><dd>${page} of ${doc.pageCount} · <a href="/source.html?doc=${doc.id}&page=${page}${IS_LIVE?'':'&demo=1'}" target="_blank" rel="noopener">Read saved page ↗</a></dd>`:''}<dt>Source</dt><dd>${escapeHTML(host)}</dd><dt>${IS_LIVE?'Retrieved':'Saved on'}</dt><dd>${IS_LIVE?escapeHTML(istTime(doc?.retrieved || event?.retrieved_at)):'30 Oct 2026 · experiment sample'}</dd></dl>
    ${doc?.status && !['saved','ready'].includes(doc.status)?`<div class="state-label"><strong>${badgeText[doc.status] || doc.status}.</strong> ${escapeHTML(doc.note)}</div>`:''}
    <p class="drawer-context">${escapeHTML(context)}</p>
    ${passage?`<div class="small-label">ORIGINAL SOURCE PASSAGE · WHITESPACE MAY BE NORMALISED</div><blockquote class="source-passage ${passage.length>1300?'long':''}">${escapeHTML(passage)}</blockquote>`:`<div class="state-label"><strong>${IS_LIVE?'Passage not loaded.':'Passage not saved.'}</strong> Exchange description below is metadata, not an extracted filing passage.</div><blockquote class="source-passage">${escapeHTML(event.description)}</blockquote>`}
    ${doc?.pageImage && page===9?`<div class="small-label">ORIGINAL PDF PAGE · TAP TO ENLARGE</div><a href="${doc.pageImage}" target="_blank" rel="noopener"><img class="source-image" src="${doc.pageImage}" alt="KPR Mill original consolidated financial-results table, PDF page 9, amounts in INR lakh"></a>`:''}
    ${doc?.note && doc.status==='saved'?`<p class="drawer-context">${escapeHTML(doc.note)}</p>`:''}
    ${doc?`<details><summary class="text-button">Saved source identity</summary><p class="small-print">SHA-256: ${doc.sha256}<br>Retrieved UTC: ${escapeHTML(doc.retrieved)}<br>Original URL: ${escapeHTML(doc.url)}</p></details>`:''}
    <p class="drawer-return">Sources open in a new tab. Close this drawer to return to the same reading position.</p></div>
    <div class="drawer-footer">${doc?`<a class="secondary" href="${doc.pdf}#page=${page}" target="_blank" rel="noopener">${IS_LIVE&&doc.has_file===false?'Original PDF':'Saved filing PDF'} ↗</a>`:''}<a class="primary" href="${escapeHTML(sourceURL)}" target="_blank" rel="noopener noreferrer">Original source ↗</a></div>`;
  if (!update) {document.body.style.position = 'fixed'; document.body.style.top = `-${modalY}px`; document.body.style.width = '100%'; $('#evidence').showModal();}
  $('#evidence').scrollTop = 0; $('#close-evidence').focus({preventScroll:true});
}
function closeModal() {
  if (!$('#evidence').open) return;
  $('#evidence').close();
  document.body.style.position = ''; document.body.style.top = ''; document.body.style.width = '';
  window.scrollTo(0, modalY);
  modalOrigin?.focus?.({preventScroll:true});
}

document.addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button || !data) return;
  if (button.dataset.route) navigate(button.dataset.route);
  else if (button.dataset.investigate) navigate('investigate', button.dataset.investigate);
  else if (button.dataset.evidence) showEvidence({evidenceId:button.dataset.evidence});
  else if (button.dataset.document) showEvidence({docId:button.dataset.document});
  else if (button.dataset.event) {
    const e = data.events.find(e=>e.id===button.dataset.event);
    if (!e) { announce('That filing has moved after an update. Showing the latest list.'); render(); return; }
    if(IS_LIVE)openLiveEvent(e.id);else showEvidence({eventId:e.id, evidenceId:e.evidence});
  } else if (button.dataset.filter) { ui.digestView = button.dataset.filter; renderDigest(); remember(); }
  else if (button.dataset.question) { ui.question=button.dataset.question; const y=window.scrollY; renderInvestigate(); window.scrollTo(0,y); remember(); }
  else if (button.id==='close-evidence') history.back();
  else if (button.id==='refresh') {
    if(IS_LIVE){refreshLive();return;}
    loading=true; renderDigest();
    setTimeout(()=>{loading=false;if(ui.route==='digest')renderDigest();announce('Loading replay complete · saved data unchanged');}, 1500);
  } else if (button.id==='reset-digest') { ui.period='week';ui.digestCompany='all';ui.digestView='all';renderDigest();remember(); }
  else if (button.id==='clear-search') { ui.search='';$('#company-search').value='';renderCompanyResults();remember();$('#company-search').focus(); }
  else if (button.id==='return-view') { if (history.state?.ui && history.length>1) history.back(); else navigate('companies'); }
});
document.addEventListener('change', event => {
  if (!data) return;
  if (event.target.id==='digest-period') { ui.period=event.target.value;renderDigest();remember(); }
  else if (event.target.id==='digest-company') { ui.digestCompany=event.target.value;renderDigest();remember(); }
  else if (event.target.id==='company-sort') { ui.sort=event.target.value;renderCompanyResults();remember(); }
  else if (event.target.id==='research-company') { ui.company=event.target.value;ui.question='snapshot';ui.positions.investigate=0;renderInvestigate();window.scrollTo(0,0);remember(); }
});
document.addEventListener('input', event => {
  if (event.target.id==='company-search') { ui.search=event.target.value;renderCompanyResults();remember(); }
});
document.addEventListener('toggle', event => {if(event.target.id==='digest-filters'){ui.filtersOpen=event.target.open;persist();}},true);
$('.wordmark').addEventListener('click', event=>{event.preventDefault();if(data)navigate('digest');});
$('#evidence').addEventListener('cancel', event=>{event.preventDefault();history.back();});
$('#evidence').addEventListener('keydown', event=>{
  if(event.key!=='Tab') return;
  const targets=[...$('#evidence').querySelectorAll('button,a[href],summary,[tabindex="0"]')].filter(el=>el.getClientRects().length && !el.disabled);
  const first=targets[0],last=targets[targets.length-1],active=document.activeElement;
  if(event.shiftKey && (active===first || !$('#evidence').contains(active))) {event.preventDefault();last?.focus();}
  else if(!event.shiftKey && (active===last || !$('#evidence').contains(active))) {event.preventDefault();first?.focus();}
});
$('#evidence').addEventListener('click', event=>{if(event.target===$('#evidence')){const r=event.target.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)history.back();}});
window.addEventListener('popstate', event => {
  const read = ui.read;
  const hadModal = $('#evidence').open;
  closeModal();
  if (event.state?.ui) ui = {...defaults, ...event.state.ui};
  ui.read = [...new Set([...ui.read, ...read])];
  persist();
  if (event.state?.modal) { render();requestAnimationFrame(()=>{window.scrollTo(0,ui.positions[ui.route]||0);showEvidence(event.state.modal,false);}); }
  else if (!hadModal) { render();requestAnimationFrame(()=>window.scrollTo(0,ui.positions[ui.route]||0)); }
  // Closing a drawer deliberately leaves the existing DOM/focus and exact scroll intact.
});
window.addEventListener('scroll', ()=>{if(!data||$('#evidence').open)return;clearTimeout(scrollTimer);scrollTimer=setTimeout(remember,100);},{passive:true});
window.addEventListener('pagehide', ()=>{if(data&&!$('#evidence').open)remember();});

(async function start() {
  try {
    const response = await fetch(IS_LIVE?'/api/data':'/data.json');
    if (!response.ok) throw new Error('Saved data could not be loaded');
    data=await response.json();
    if (!IS_LIVE && !company()) ui.company='INFY';
    const hash=location.hash.slice(1).split('/');
    if (['digest','companies','investigate'].includes(hash[0])) ui.route=hash[0];
    if (ui.route==='investigate' && ((IS_LIVE && /^[A-Z0-9][A-Z0-9&-]{0,24}$/.test(hash[1]||'')) || data.companies.some(c=>c.ticker===hash[1]))) ui.company=hash[1];
    history.replaceState({ui:snapshot()},'',currentHash());render();
    if(IS_LIVE&&data.activeJob)pollLiveJob();
    requestAnimationFrame(()=>window.scrollTo(0,ui.positions[ui.route]||0));
  } catch(error) {
    $('#main').innerHTML=`<div class="empty"><h1>Saved sample unavailable.</h1><p>The local data file could not be loaded. Check that the Python server is running and reload this page.</p><a class="primary" href="/">Reload preview</a></div>`;
    console.error(error);
  }
})();
