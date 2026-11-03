'use strict';
const safe = s => String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
(async()=>{
  const main=document.querySelector('#source-main');
  try {
    const live=document.querySelector('meta[name="finn-mode"]')?.content==='live';
    const params=new URLSearchParams(location.search);
    const response=await fetch(live?'/api/documents/'+encodeURIComponent(params.get('doc')):'/data.json');if(!response.ok)throw new Error('Data unavailable');
    const data=await response.json();const doc=live?data:data.documents[params.get('doc')];
    if(!doc)throw new Error('Saved document not found');
    const page=Number(params.get('page'))||doc.pages[0].number;const selected=doc.pages.find(p=>p.number===page);
    document.title=doc.title+' · saved source';
    main.innerHTML=`<span class="eyebrow">FINN · RETRIEVED PRIMARY SOURCE</span><h1>${safe(doc.title)}</h1><p class="subhead">${safe(doc.kind)} · ${safe(doc.period)} · ${safe(doc.date)}</p><div class="sample-note"><strong>${live?'Retrieved UTC: '+safe(doc.retrieved):'Saved on 30 Oct 2026.'}</strong> Extracted source text, not an AI answer. PDF page numbers refer to the physical file. Close this source tab to return to your unchanged workspace.</div><div class="reader-actions"><a class="primary" href="${safe(doc.url)}" target="_blank" rel="noopener noreferrer">Original source ↗</a><a class="secondary" href="${doc.pdf}#page=${page}" target="_blank" rel="noopener">Open saved full PDF ↗</a><a class="secondary" href="/${live?'':'?demo=1'}#digest">Open workspace</a></div><p class="drawer-context">${safe(doc.note)}</p>${selected?`<section class="reader-page"><h2>PDF page ${page} of ${doc.pageCount}</h2>${doc.pageImage&&page===9?`<a href="${doc.pageImage}" target="_blank" rel="noopener"><img class="source-image" src="${doc.pageImage}" alt="Original consolidated results table, INR lakh"></a>`:''}<blockquote class="source-passage">${safe(selected.text)}</blockquote></section>`:'<p>This page was not extracted. Open the saved full PDF to inspect it.</p>'}<details><summary class="text-button">Source provenance</summary><p class="small-print">Original URL: ${safe(doc.url)}<br>Retrieved UTC: ${safe(doc.retrieved)}<br>SHA-256: ${doc.sha256}</p></details>`;
  } catch(error) { main.innerHTML='<h1>Saved source unavailable.</h1><p>Check the document link and local server.</p><a class="secondary" href="/">Return to preview</a>';console.error(error); }
})();
