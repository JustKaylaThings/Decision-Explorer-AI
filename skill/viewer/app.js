// Decision Explorer AI logic. Reads window.DT_DATA (set by data.js) and renders an apple.com-style
// card grid grouped by phase, with a modal sheet for one decision at a time. Edit styles.css for
// looks. Loaded as a classic script so index.html opens by double-click (file://) — no server.
// Read the decision JSON files directly at runtime (d28 revised): fetch manifest.json for the
// list of filenames, then fetch + parse each decision file. Requires the folder to be served
// over http:// (e.g. `python3 -m http.server`); file:// blocks these fetches.
let RAW = [];            // decisions, filled in by init()
let AXIS = '';           // optional second grouping dimension ('' = off)
let PROJECT = 'Decisions';

const SENT_VAR = { '+':'var(--pos)', '-':'var(--neg)', '~':'var(--neu)' };
const SENT_MARK = { '+':'✓', '-':'✗', '~':'~' };
const esc = s => (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const chosenOf = d => (d.options||[]).find(o => o.chosen);
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function fmtDate(s, withTime){
  if (!s) return '';
  const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?/);
  if (!m) return esc(s);
  let out = MONTHS[+m[2]-1] + ' ' + (+m[3]) + ', ' + m[1];
  if (withTime && m[4]) out += ' · ' + m[4] + ':' + m[5];
  return out;
}
function fmtTime(s){  // time-only "13:12", or '' when the stamp carries no time
  const m = String(s||'').match(/[T ](\d{2}):(\d{2})/);
  return m ? m[1] + ':' + m[2] : '';
}
// What a card/row shows in its date slot: the time alone in the "Last 24 hours" bucket (where the
// day is a given), otherwise the date; falls back to the date if no time was stamped (d38 stream).
function cardDate(s, time){ return time ? (fmtTime(s) || fmtDate(s, false)) : fmtDate(s, false); }
// Last activity = the most recent of the decision's own date and any revision dates.
const lastActivity = d => {
  let m = d.date || '';
  (d.history || []).forEach(h => { if (h.date && h.date > m) m = h.date; });
  return m;
};
const PHASE_ORDER = ['Requirements','Design','Implementation','Testing','Deployment','Maintenance'];
// A coordinated, evenly-muted family tuned to sit with the teal accent (d27).
const PHASE_C = { Requirements:'#5b9bd5', Design:'#9b87d4', Implementation:'#35b1a0',
                  Testing:'#d2a456', Deployment:'#4aa9bf', Maintenance:'#d88c6b' };
const phaseOf = d => d.phase || 'Unphased';
const phaseColor = p => PHASE_C[p] || '#8e8e93';
const areaOf = d => d.area || '';
const versionOf = d => d.version || '';
// Compare version strings newest-first: numeric dotted parts (1.10 > 1.9), text falls back to locale.
function cmpVersion(a, b){
  const pa = String(a).split(/[.\-]/), pb = String(b).split(/[.\-]/);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++){
    const na = parseInt(pa[i], 10), nb = parseInt(pb[i], 10);
    const bothNum = !isNaN(na) && !isNaN(nb);
    if (bothNum){ if (na !== nb) return nb - na; }
    else { const c = (pb[i]||'').localeCompare(pa[i]||''); if (c) return c; }
  }
  return 0;
}
function orderPhases(present){
  return PHASE_ORDER.filter(p => present.includes(p))
    .concat(present.filter(p => !PHASE_ORDER.includes(p)).sort());
}
function matches(d, f){
  if (!f) return true;
  const hay = [d.title, d.phase, d.category, d.version, d.rationale, d.question,
    (d.options||[]).map(o => o.label + ' ' + (o.tradeoffs||[]).map(t => t.criterion + ' ' + (t.note||'')).join(' ')).join(' ')
  ].join(' ').toLowerCase();
  return hay.includes(f.toLowerCase());
}

let activeId = null;          // the decision shown in the open sheet, or null
let sortMode = 'recent';      // default view: newest-activity first (the "what changed lately" question)
let filter = '';
let openOnly = false;
let builtOnly = false;        // isolate just the decided-but-not-built decisions (d43)
let dueOnly = false;          // isolate just the decisions whose review-by date has passed (d14)
let areaFilter = '';
let verFilter = '';           // selected app version; '' = all
let catFilter = new Set();    // selected categories (multi-select); empty = all
let collapsed = new Set();    // section names folded shut in the list (persists across re-renders)
let viewMode = (function(){ try { return localStorage.getItem('dt-view')==='list' ? 'list' : 'cards'; } catch(e){ return 'cards'; } })();

const isOpen = d => d.status === 'open';
// Decided but not yet built into the app: an optional flag, kept separate from open/decided so a
// decided decision can still be marked unshipped (d43). Absent or true → built; only built===false
// marks it unbuilt, so the surfaces below stay dormant for projects that never set it.
const isUnbuilt = d => d.built === false;
// Due for review: an optional 'reviewBy' date (YYYY-MM-DD) on a decision you made provisionally
// ("revisit later"). Most decisions set none and stay calm; a decision is "due" only once that date
// has arrived (reviewBy <= today). Like built (d43), every surface below stays dormant — invisible —
// for projects and decisions that never set the field (d14).
function todayISO(){ const n = new Date(), z = x => String(x).padStart(2,'0');
  return n.getFullYear() + '-' + z(n.getMonth()+1) + '-' + z(n.getDate()); }
const reviewByOf = d => (d.reviewBy ? String(d.reviewBy).slice(0,10) : '');
const isDue = d => { const r = reviewByOf(d); return !!r && r <= todayISO(); };
const passes = d => matches(d, filter)
  && (!areaFilter || areaOf(d) === areaFilter)
  && (!verFilter || versionOf(d) === verFilter)
  && (!catFilter.size || catFilter.has(d.category || ''));
function byRecency(a, b){
  const da = lastActivity(a), db = lastActivity(b);
  if (da && db) return da < db ? 1 : da > db ? -1 : 0;
  if (da) return -1; if (db) return 1; return 0;
}

// ---- header / hero text ----
function setHeader(){
  const t = document.getElementById('title'); if (t) t.textContent = PROJECT;
  const ht = document.getElementById('heroTitle'); if (ht) ht.textContent = PROJECT;
  document.title = PROJECT + ' — Decision Explorer AI';
  // Count every decision-event: each logged decision plus each revision is a decision that was made,
  // so the headline reflects the true total, not just the created count (d38).
  const logged = RAW.length;
  const revisions = RAW.reduce((n, d) => n + ((d.history || []).length), 0);
  const made = logged + revisions;
  const openN = RAW.filter(isOpen).length;
  const unbuiltN = RAW.filter(isUnbuilt).length;
  const dueN = RAW.filter(isDue).length;
  const hs = document.getElementById('heroSub');
  if (!hs) return;
  if (!logged){ hs.textContent = 'No decisions logged yet'; return; }
  const parts = [logged + ' created'];
  if (revisions) parts.push(revisions + ' revision' + (revisions===1?'':'s'));
  if (openN) parts.push(openN + ' open');
  if (unbuiltN) parts.push(unbuiltN + ' not built');
  if (dueN) parts.push(dueN + ' due for review');
  hs.innerHTML = `<span class="hero-count">${made} decision${made===1?'':'s'} made</span><span class="hero-break">${parts.join(' · ')}</span>`;
}

// ---- cards ----
// cardHTML/rowHTML take an optional opts: { date } overrides the shown date (the Recent
// event stream dates a decision card at its creation, not last-activity); { hideRev } drops the
// "revised" badge there, since each revision is now its own card (d38).
function cardHTML(d, opts){
  opts = opts || {};
  const p = phaseOf(d), ch = chosenOf(d), pc = phaseColor(p);
  const rev = (!opts.hideRev && d.history && d.history.length) ? '<span class="card-rev">revised</span>' : '';
  const sup = isSuperseded(d) ? '<span class="card-rev card-superseded">superseded</span>' : '';
  const build = isUnbuilt(d) ? '<span class="card-build">Not built yet</span>' : '';
  const due = isDue(d) ? '<span class="card-due">Due for review</span>' : '';
  const shown = ('date' in opts) ? opts.date : lastActivity(d);
  return `<article class="dt-item card${isOpen(d)?' is-open':''}${isUnbuilt(d)?' is-unbuilt':''}${isDue(d)?' is-due':''}" data-id="${esc(d.id)}" tabindex="0">
    <div class="card-head">
      <span class="phase-pill" style="color:${pc};background:${pc}22">${esc(p)}</span>
      <span class="card-id">${esc(d.id)}</span>
      ${shown?`<span class="card-date">${cardDate(shown,opts.time)}</span>`:''}
    </div>
    <h3 class="card-title">${esc(d.title)}</h3>
    <div class="card-chosen${ch?'':' open'}">${ch?'✓ '+esc(ch.label):'Open — undecided'}</div>
    ${d.rationale?`<p class="card-why">${esc(d.rationale)}</p>`:''}
    <div class="card-foot">${build}${due}${d.category?`<span class="card-cat">${esc(d.category)}</span>`:''}${versionOf(d)?`<span class="card-ver">v${esc(versionOf(d))}</span>`:''}${rev}${sup}</div>
  </article>`;
}
function rowHTML(d, opts){
  opts = opts || {};
  const p = phaseOf(d), ch = chosenOf(d), pc = phaseColor(p);
  const rev = (!opts.hideRev && d.history && d.history.length) ? '<span class="row-rev">revised</span>' : '';
  const sup = isSuperseded(d) ? '<span class="row-rev row-superseded">superseded</span>' : '';
  const build = isUnbuilt(d) ? '<span class="row-build">Not built</span>' : '';
  const due = isDue(d) ? '<span class="row-due">Due</span>' : '';
  const shown = ('date' in opts) ? opts.date : lastActivity(d);
  return `<div class="dt-item row${isOpen(d)?' is-open':''}${isUnbuilt(d)?' is-unbuilt':''}${isDue(d)?' is-due':''}" data-id="${esc(d.id)}" tabindex="0">
    <span class="row-dot" style="background:${pc}"></span>
    <span class="row-id">${esc(d.id)}</span>
    <div class="row-main">
      <span class="row-title">${esc(d.title)}</span>
      <span class="row-chosen${ch?'':' open'}">${ch?'✓ '+esc(ch.label):'Open — undecided'}</span>
    </div>
    ${build}${due}${d.category?`<span class="row-cat">${esc(d.category)}</span>`:''}${versionOf(d)?`<span class="row-ver">v${esc(versionOf(d))}</span>`:''}${rev}${sup}
    ${shown?`<span class="row-date">${cardDate(shown,opts.time)}</span>`:''}
    <span class="row-arrow">›</span>
  </div>`;
}
// A revision shown as its own slim card in the Recent stream, linking back to its parent
// decision and opening straight to the revision-history fold (d38).
function revCardHTML(d, h, hi, time){
  return `<article class="dt-item card revcard" data-id="${esc(d.id)}" data-openfold="history" data-revidx="${hi}" tabindex="0">
    <div class="card-head">
      <span class="revcard-kind">↻ Revision</span>
      <span class="card-id">${esc(d.id)}</span>
      ${h.date?`<span class="card-date">${cardDate(h.date,time)}</span>`:''}
    </div>
    <h3 class="card-title">${esc(d.title)}</h3>
    <p class="card-why">${esc(h.reason || (h.from?'was “'+h.from+'”':''))}</p>
    <div class="card-foot"><span class="revcard-link">See in timeline ›</span></div>
  </article>`;
}
function revRowHTML(d, h, hi, time){
  const p = phaseOf(d), pc = phaseColor(p);
  return `<div class="dt-item row revrow" data-id="${esc(d.id)}" data-openfold="history" data-revidx="${hi}" tabindex="0">
    <span class="row-dot" style="background:${pc}"></span>
    <span class="row-id">${esc(d.id)}</span>
    <div class="row-main">
      <span class="row-title"><span class="revrow-kind">↻ Revision</span>${esc(d.title)}</span>
      <span class="row-chosen">${esc(h.reason || (h.from?'was “'+h.from+'”':''))}</span>
    </div>
    ${h.date?`<span class="row-date">${cardDate(h.date,time)}</span>`:''}
    <span class="row-arrow">›</span>
  </div>`;
}
// Revision history as a vertical timeline (d39): Now (current state) at top, each change below it
// newest-first with its reason and the state it moved away from, down to Created at the bottom.
function revTimeline(d){
  const ch = chosenOf(d), hist = d.history || [];
  let h = '<div class="rev-timeline">';
  h += `<div class="rev-node rev-now"><span class="rev-dot"></span><div class="rev-body">
    <div class="rev-when">Now</div>
    <div class="rev-state">${ch?'✓ '+esc(ch.label):'Open — undecided'}</div></div></div>`;
  for (let i = hist.length - 1; i >= 0; i--){
    const x = hist[i];
    h += `<div class="rev-node" data-rev="${i}"><span class="rev-dot"></span><div class="rev-body">
      <div class="rev-when">${x.date?fmtDate(x.date,true):'—'}</div>
      ${x.reason?`<div class="rev-reason">${esc(x.reason)}</div>`:''}
      ${x.from?`<div class="rev-from">was “${esc(x.from)}”</div>`:''}</div></div>`;
  }
  h += `<div class="rev-node rev-created"><span class="rev-dot"></span><div class="rev-body">
    <div class="rev-when">Created${d.date?' · '+fmtDate(d.date,true):''}</div></div></div>`;
  return h + '</div>';
}
function sectionWrap(name, color, innerCards, count, pinned){
  const isCol = collapsed.has(name);
  const inner = viewMode === 'list' ? `<div class="dlist">${innerCards}</div>` : `<div class="grid">${innerCards}</div>`;
  return `<section class="phase-sec${pinned?' '+pinned:''}${isCol?' collapsed':''}">
    <header class="sec-head" data-sec="${esc(name)}" role="button" tabindex="0" aria-expanded="${isCol?'false':'true'}">
      <span class="sec-caret" aria-hidden="true">▾</span><span class="sec-dot" style="background:${color}"></span>
      <h2 class="sec-name">${esc(name)} (${count})</h2></header>
    <div class="sec-body">${inner}</div>
  </section>`;
}
function sectionHTML(name, color, items, pinned){
  const cards = items.map(d => viewMode === 'list' ? rowHTML(d) : cardHTML(d)).join('');
  return sectionWrap(name, color, cards, items.length, pinned);
}
function toggleSection(name){ collapsed.has(name) ? collapsed.delete(name) : collapsed.add(name); buildList(); }

// Build the Filter drawer contents + update the button's active state and count badge.
function renderFilters(){
  const pop = document.getElementById('filterPop');
  const openN = RAW.filter(isOpen).length;
  const unbuiltN = RAW.filter(isUnbuilt).length;
  const dueN = RAW.filter(isDue).length;
  let h = '';
  if (openN || unbuiltN || dueN){
    h += `<div class="fp-sec"><div class="fp-h">Show</div>`;
    if (openN) h += `<button class="fp-opt${openOnly?' on':''}" data-toggle="open"><span class="fp-check">✓</span>Open decisions only<span class="fp-n">${openN}</span></button>`;
    if (unbuiltN) h += `<button class="fp-opt${builtOnly?' on':''}" data-toggle="built"><span class="fp-check">✓</span>Not built yet only<span class="fp-n">${unbuiltN}</span></button>`;
    if (dueN) h += `<button class="fp-opt${dueOnly?' on':''}" data-toggle="due"><span class="fp-check">✓</span>Due for review only<span class="fp-n">${dueN}</span></button>`;
    h += `</div>`;
  }
  if (AXIS){
    const vals = [...new Set(RAW.map(areaOf).filter(Boolean))].sort();
    if (vals.length){
      h += `<div class="fp-sec"><div class="fp-h">${esc(AXIS)}</div>
        <button class="fp-opt${!areaFilter?' on':''}" data-area=""><span class="fp-check">✓</span>All</button>`
        + vals.map(v => `<button class="fp-opt${areaFilter===v?' on':''}" data-area="${esc(v)}"><span class="fp-check">✓</span>${esc(v)}</button>`).join('')
        + `</div>`;
    }
  }
  const vers = [...new Set(RAW.map(versionOf).filter(Boolean))].sort(cmpVersion);
  if (vers.length){
    h += `<div class="fp-sec"><div class="fp-h">Version</div>
      <button class="fp-opt${!verFilter?' on':''}" data-ver=""><span class="fp-check">✓</span>All</button>`
      + vers.map(v => {
          const n = RAW.filter(d => versionOf(d) === v).length;
          return `<button class="fp-opt${verFilter===v?' on':''}" data-ver="${esc(v)}"><span class="fp-check">✓</span>v${esc(v)}<span class="fp-n">${n}</span></button>`;
        }).join('')
      + `</div>`;
  }
  const cats = [...new Set(RAW.map(d => d.category).filter(Boolean))].sort();
  if (cats.length){
    h += `<div class="fp-sec"><div class="fp-h">Category</div>`
      + cats.map(c => {
          const n = RAW.filter(d => d.category === c).length;
          return `<button class="fp-opt${catFilter.has(c)?' on':''}" data-cat="${esc(c)}"><span class="fp-check">✓</span>${esc(c)}<span class="fp-n">${n}</span></button>`;
        }).join('')
      + `</div>`;
  }
  const active = (openOnly?1:0) + (builtOnly?1:0) + (dueOnly?1:0) + (areaFilter?1:0) + (verFilter?1:0) + catFilter.size;
  pop.innerHTML = h || '<div class="fp-sec"><div class="fp-h">No filters available</div></div>';
  const foot = document.getElementById('filterFoot');      // pinned footer: always visible, never scrolls away
  if (foot){
    foot.hidden = !active;
    const clr = document.getElementById('clearFilters');
    if (clr) clr.textContent = active ? `Clear filters (${active})` : 'Clear filters';
  }
  const badge = document.getElementById('filterBadge');
  badge.textContent = active ? String(active) : '';
  document.getElementById('filterBtn').classList.toggle('active', active > 0);
}

function buildList(){
  const root = document.getElementById('list');
  renderFilters();
  if (!RAW.length){ root.innerHTML = '<div class="empty-state">No decisions logged yet.<br>Use <code>/decision-tree add</code>.</div>'; return; }

  // Isolation mode: "open only" / "not built only" / "due for review only" collapse the list to just those groups.
  if (openOnly || builtOnly || dueOnly){
    let only = '';
    if (openOnly){
      const items = RAW.filter(d => isOpen(d) && passes(d)).sort(byRecency);
      if (items.length) only += sectionHTML('Open', 'var(--neg)', items, 'pinned');
    }
    if (builtOnly){
      const items = RAW.filter(d => isUnbuilt(d) && passes(d)).sort(byRecency);
      if (items.length) only += sectionHTML('Not built yet', 'var(--build)', items, 'pinned pinned-build');
    }
    if (dueOnly){
      const items = RAW.filter(d => isDue(d) && passes(d)).sort(byRecency);
      if (items.length) only += sectionHTML('Due for review', 'var(--due)', items, 'pinned pinned-due');
    }
    const labels = [openOnly?'open':'', builtOnly?'unbuilt':'', dueOnly?'due for review':''].filter(Boolean).join(' or ');
    root.innerHTML = only || '<div class="empty-state">No '+labels+' decisions'+(filter?' match “'+esc(filter)+'”':'')+'.</div>';
    return;
  }

  // Pinned groups sit above the framework so what's unresolved (open, d13), decided-but-unshipped
  // (unbuilt, d43), or due for another look (reviewBy, d14) is always in view; each hides when empty.
  const pinnedOpen = RAW.filter(d => isOpen(d) && passes(d));
  const pinnedUnbuilt = RAW.filter(d => isUnbuilt(d) && passes(d));
  const pinnedDue = RAW.filter(d => isDue(d) && passes(d));
  let html = (pinnedOpen.length ? sectionHTML('Open', 'var(--neg)', pinnedOpen, 'pinned') : '')
           + (pinnedUnbuilt.length ? sectionHTML('Not built yet', 'var(--build)', pinnedUnbuilt, 'pinned pinned-build') : '')
           + (pinnedDue.length ? sectionHTML('Due for review', 'var(--due)', pinnedDue, 'pinned pinned-due') : '');
  let body = '';

  if (sortMode === 'recent'){
    // Recent is an event stream: each decision's creation AND each revision is its own card,
    // so every decision-event is visible without opening the decision to read its history (d38).
    // Revision cards link back to the parent decision and open straight to its history fold.
    // Events split into age buckets relative to when the page is open, each with its own count.
    const events = [];
    RAW.filter(passes).forEach(d => {
      events.push({ date: d.date || '', html: (t) => viewMode === 'list' ? rowHTML(d, {date:d.date, hideRev:true, time:t}) : cardHTML(d, {date:d.date, hideRev:true, time:t}) });
      (d.history || []).forEach((h, hi) => {
        events.push({ date: h.date || '', html: (t) => viewMode === 'list' ? revRowHTML(d, h, hi, t) : revCardHTML(d, h, hi, t) });
      });
    });
    if (events.length){
      events.sort((a, b) => (b.date || '').localeCompare(a.date || ''));   // newest first; undated sink
      const DAY = 86400000, now = Date.now();
      const cuts = [['Last 24 hours', DAY], ['Last 7 days', 7*DAY], ['Last 30 days', 30*DAY], ['Earlier', Infinity]];
      const groups = cuts.map(() => []);
      events.forEach(ev => {
        const t = ev.date ? new Date(ev.date).getTime() : NaN;
        const age = isNaN(t) ? Infinity : now - t;        // undated → Infinity → falls to "Earlier"
        let i = cuts.findIndex(([, c]) => age < c); if (i < 0) i = cuts.length - 1;
        groups[i].push(ev);
      });
      cuts.forEach(([name], i) => {
        if (groups[i].length) body += sectionWrap(name, 'var(--accent)', groups[i].map(ev => ev.html(i === 0)).join(''), groups[i].length, false);  // i===0 is "Last 24 hours" → show time (d38 stream)
      });
    }
  } else if (sortMode === 'area' && AXIS){
    const groups = {};
    RAW.forEach(d => { const a = areaOf(d) || 'Unassigned'; (groups[a] = groups[a] || []).push(d); });
    Object.keys(groups).sort((a,b) => a==='Unassigned'?1 : b==='Unassigned'?-1 : a.localeCompare(b)).forEach(a => {
      const items = groups[a].filter(passes);
      if (items.length) body += sectionHTML(a, 'var(--faint)', items, false);
    });
  } else if (sortMode === 'version'){
    const groups = {};
    RAW.forEach(d => { const v = versionOf(d) || 'Unversioned'; (groups[v] = groups[v] || []).push(d); });
    Object.keys(groups).sort((a,b) => a==='Unversioned'?1 : b==='Unversioned'?-1 : cmpVersion(a,b)).forEach(v => {
      const items = groups[v].filter(passes);
      if (items.length) body += sectionHTML(v==='Unversioned'?v:'v'+v, 'var(--accent)', items, false);
    });
  } else {
    const groups = {};
    RAW.forEach(d => { const p = phaseOf(d); (groups[p] = groups[p] || []).push(d); });
    orderPhases(Object.keys(groups)).forEach(p => {
      const items = groups[p].filter(passes);
      if (items.length) body += sectionHTML(p, phaseColor(p), items, false);
    });
  }
  if (!html && !body) body = '<div class="empty-state">No decisions match “'+esc(filter)+'”.</div>';
  root.innerHTML = html + body;
}

// ---- options-compared matrix (criteria down the side, options across the top) ----
function tradeoffMatrix(d){
  const opts = d.options || [];
  if (!opts.length || !opts.some(o => (o.tradeoffs||[]).length))
    return '<div class="tr-empty">No tradeoffs recorded.</div>';
  const firstSeen = new Map();
  opts.forEach(o => (o.tradeoffs||[]).forEach(t => { if (!firstSeen.has(t.criterion)) firstSeen.set(t.criterion, firstSeen.size); }));
  const weighedBy = c => opts.filter(o => (o.tradeoffs||[]).some(t => t.criterion===c)).length;
  const criteria = [...firstSeen.keys()].sort((a,b) => weighedBy(b)-weighedBy(a) || firstSeen.get(a)-firstSeen.get(b));
  const at = (o,c) => (o.tradeoffs||[]).find(t => t.criterion===c);
  let h = '<div class="cmp-wrap"><table class="cmp"><thead><tr><th class="cmp-corner"></th>';
  opts.forEach(o => { h += `<th class="cmp-opt${o.chosen?' chosen':''}">${o.chosen?'<span class="cmp-tick">✓</span> ':''}${esc(o.label)}</th>`; });
  h += '</tr></thead><tbody>';
  criteria.forEach(c => {
    h += `<tr><th class="cmp-crit">${esc(c)}</th>`;
    opts.forEach(o => {
      const t = at(o, c);
      if (!t){ h += `<td class="cmp-cell empty" data-opt="${esc(o.label)}">·</td>`; return; }
      h += `<td class="cmp-cell${o.chosen?' chosen':''}" data-opt="${esc(o.label)}"><span class="s" style="color:${SENT_VAR[t.sentiment]||'var(--muted)'}">${SENT_MARK[t.sentiment]||esc(t.sentiment)}</span>${t.note?` <span class="cmp-note">${esc(t.note)}</span>`:''}</td>`;
    });
    h += '</tr>';
  });
  return h + '</tbody></table></div>';
}
// Revision lineage (d55): a revision is its own decision (decimal id, e.g. d47.1) that names the
// decision it revises in `supersedes`. The reverse ("Revised by") is derived, so the original file
// is never edited.
const revisedBy = id => RAW.filter(x => (x.supersedes || []).includes(id)).map(x => x.id).sort();
const isSuperseded = d => revisedBy(d.id).length > 0;
function depRows(ids, dir){
  if (!ids.length) return `<div class="dep-empty">${dir==='up'?'No upstream dependencies':'No downstream decisions'}</div>`;
  return ids.map(id => {
    const dd = RAW.find(x => x.id===id); if (!dd) return '';
    return `<div class="dep-row" data-jump="${esc(id)}"><span class="dep-arrow">${dir==='up'?'↑':'↓'}</span>
      <span class="dep-name">${esc(dd.title)}</span>${dd.category?`<span class="pill">${esc(dd.category)}</span>`:''}</div>`;
  }).join('');
}
// Downstream impact as a loop-safe tree: each decision appears once, under the first parent
// that reaches it. Parents are collapsed by default so only the direct dependents show.
function downstreamTree(rootId){
  const visited = new Set([rootId]);
  return (function kids(id){
    const out = [];
    RAW.filter(x => (x.dependsOn||[]).includes(id)).map(x => x.id).sort().forEach(k => {
      if (visited.has(k)) return;       // check at processing time so a node lands under one parent only
      visited.add(k); out.push({ id:k, children:kids(k) });
    });
    return out;
  })(rootId);
}
const descCount = node => node.children.reduce((n, c) => n + 1 + descCount(c), 0);
const treeTotal = nodes => nodes.reduce((n, c) => n + 1 + descCount(c), 0);
function downNode(node){
  const dd = RAW.find(x => x.id===node.id); if (!dd) return '';
  const has = node.children.length > 0, n = has ? descCount(node) : 0;
  return `<div class="dep-node${has?' collapsed':''}">
    <div class="dep-row" data-jump="${esc(node.id)}">
      ${has ? `<span class="dep-caret" role="button" tabindex="0" aria-label="Expand">▸</span>`
            : `<span class="dep-caret leaf">↓</span>`}
      <span class="dep-name">${esc(dd.title)}</span>${dd.category?`<span class="pill">${esc(dd.category)}</span>`:''}
      ${has?`<span class="dep-count">+${n}</span>`:''}
    </div>${has?`<div class="dep-children">${node.children.map(downNode).join('')}</div>`:''}
  </div>`;
}
function downRows(nodes){
  if (!nodes.length) return `<div class="dep-empty">No downstream decisions</div>`;
  return nodes.map(downNode).join('');
}

function sheetHTML(d){
  const ch = chosenOf(d), p = phaseOf(d);
  const upstream = d.dependsOn || [], downTree = downstreamTree(d.id), downTotal = treeTotal(downTree);
  const supersedes = d.supersedes || [], supersededBy = revisedBy(d.id);
  const revised = d.history && d.history.length;
  const meta = [d.category, (AXIS && d.area) ? d.area : '', d.version ? 'v'+d.version : '', d.date ? fmtDate(d.date,true) : '']
    .filter(Boolean).map(m => `<span class="d-meta">${esc(m)}</span>`).join('');
  let h = `<button class="sheet-close" aria-label="Close">✕</button>`;
  h += `<div class="d-eyebrow">
    <span class="phase-chip" style="--pc:${phaseColor(p)}"><span class="pdot"></span>${esc(p)}</span>
    <span class="d-id">${esc(d.id)}</span>
    ${meta}
    ${d.status==='open'?'<span class="tag open">open</span>':''}
    ${d.built===false?'<span class="tag unbuilt">not built yet</span>':''}
    ${isDue(d)?'<span class="tag due">due for review</span>':''}
    ${supersededBy.length?'<span class="tag superseded">superseded</span>':''}
    ${revised?'<span class="tag revised" data-open-fold="history">revised</span>':''}</div>`;
  h += `<h2 class="d-title">${esc(d.title)}</h2>`;
  if (d.question) h += `<p class="d-question">${esc(d.question)}</p>`;
  h += `<div class="answer${ch?'':' open'}${ch&&d.built===false?' unbuilt':''}">
    <span class="answer-mark">${ch?'✓':'!'}</span>
    <div>
      <div class="answer-cap">${ch?(d.built===false?'Chosen · not built yet':'Chosen'):'Status'}</div>
      <div class="answer-val">${ch?esc(ch.label):'Still open — no option chosen yet'}</div>
      ${ch&&d.built===false?'<div class="answer-build">Decided, but not yet built into the app.</div>':''}
    </div></div>`;
  // Review-by note (d14): shows the scheduled date when set. Subtle while it's in the future,
  // escalated to "Due for review" once the date has passed. Nothing renders when no date is set.
  if (reviewByOf(d))
    h += `<div class="review-note${isDue(d)?' due':''}">${isDue(d)?'⟳ Due for review — set on '+fmtDate(reviewByOf(d)):'⟳ Review by '+fmtDate(reviewByOf(d))}</div>`;
  if (d.rationale)
    h += `<section class="block"><div class="eyebrow">Why</div><p class="why-text">${esc(d.rationale)}</p></section>`;
  if (downTotal || upstream.length || supersedes.length || supersededBy.length){
    h += `<section class="block impact">`;
    if (supersedes.length)   h += `<div class="imp-grp"><div class="eyebrow">Revises</div>${depRows(supersedes,'up')}</div>`;
    if (supersededBy.length) h += `<div class="imp-grp"><div class="eyebrow">Revised by</div>${depRows(supersededBy,'down')}</div>`;
    if (downTotal) h += `<div class="imp-grp"><div class="eyebrow">Affects${downTotal>1?`<span class="eyebrow-n">${downTotal} downstream</span>`:''}</div>${downRows(downTree)}</div>`;
    if (upstream.length)    h += `<div class="imp-grp"><div class="eyebrow">Depends on</div>${depRows(upstream,'up')}</div>`;
    h += `</section>`;
  }
  const nopt = (d.options||[]).length;
  h += `<section class="fold" data-open="1"><header class="fold-head"><span class="caret">▾</span><span class="eyebrow">Options compared${nopt?`<span class="eyebrow-n">${nopt}</span>`:''}</span></header><div class="fold-body">${tradeoffMatrix(d)}</div></section>`;
  if (revised)
    h += `<section class="fold" data-open="0" data-fold="history"><header class="fold-head"><span class="caret">▸</span><span class="eyebrow">Revision history<span class="eyebrow-n">${d.history.length}</span></span></header><div class="fold-body">${revTimeline(d)}</div></section>`;
  return h;
}

// ---- sheet open / close ----
const sheet = document.getElementById('sheet');
const sheetBody = document.getElementById('sheetBody');
function openSheet(id, openFold, revIdx){
  const d = RAW.find(x => x.id===id); if (!d) return;
  activeId = id;
  sheetBody.innerHTML = sheetHTML(d);
  sheetBody.scrollTop = 0;
  sheet.classList.add('open');
  document.body.classList.add('no-scroll');
  if (decodeURIComponent((location.hash||'').replace(/^#/,'')) !== id) location.hash = encodeURIComponent(id);
  if (openFold){  // a revision card opens straight to the history fold (d38)
    const s = sheetBody.querySelector('.fold[data-fold="'+openFold+'"]');
    if (s){ s.dataset.open = '1'; const c = s.querySelector('.caret'); if (c) c.textContent = '▾'; s.scrollIntoView({block:'nearest'}); }
  }
  if (revIdx != null && revIdx !== ''){  // highlight the exact change you clicked in the timeline (d39)
    const node = sheetBody.querySelector('.rev-node[data-rev="'+revIdx+'"]');
    if (node){ node.classList.add('rev-hit'); node.scrollIntoView({block:'nearest'}); }
  }
}
function closeSheet(){
  sheet.classList.remove('open');
  document.body.classList.remove('no-scroll');
  activeId = null;
  if (location.hash) history.replaceState(null, '', location.pathname + location.search);
}
const selectDecision = openSheet;  // alias

// ---- events ----
document.getElementById('list').addEventListener('click', e => {
  const head = e.target.closest('.sec-head');
  if (head){ toggleSection(head.dataset.sec); return; }
  const it = e.target.closest('.dt-item'); if (it) openSheet(it.dataset.id, it.dataset.openfold, it.dataset.revidx);
});
document.getElementById('list').addEventListener('keydown', e => {
  const head = e.target.closest('.sec-head');
  if (head && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); toggleSection(head.dataset.sec); return; }
  if (e.key === 'Enter'){ const it = e.target.closest('.dt-item'); if (it){ e.preventDefault(); openSheet(it.dataset.id, it.dataset.openfold, it.dataset.revidx); } }
});
sheet.addEventListener('click', e => {
  if (e.target === sheet || e.target.closest('.sheet-close')){ closeSheet(); return; }
  const fh = e.target.closest('.fold-head');
  if (fh){ const s = fh.parentElement; const open = s.dataset.open==='1';
    s.dataset.open = open?'0':'1'; fh.querySelector('.caret').textContent = open?'▸':'▾'; return; }
  const badge = e.target.closest('[data-open-fold]');
  if (badge){ const s = sheet.querySelector('.fold[data-fold="'+badge.dataset.openFold+'"]');
    if (s){ s.dataset.open='1'; const c = s.querySelector('.caret'); if (c) c.textContent='▾'; s.scrollIntoView({block:'nearest'}); } return; }
  const car = e.target.closest('.dep-caret:not(.leaf)');
  if (car){ const node = car.closest('.dep-node'); const open = node.classList.toggle('collapsed')===false;
    car.textContent = open?'▾':'▸'; car.setAttribute('aria-label', open?'Collapse':'Expand'); return; }
  const j = e.target.closest('[data-jump]');
  if (j){ openSheet(j.dataset.jump); }
});

const search = document.getElementById('search');
search.addEventListener('input', () => { filter = search.value.trim(); buildList(); });
const filterBtn = document.getElementById('filterBtn');
const filterDrawer = document.getElementById('filterDrawer');
function openFilter(){
  filterDrawer.classList.add('open');
  filterBtn.setAttribute('aria-expanded', 'true');
  document.body.classList.add('no-scroll');
}
function closeFilter(){
  filterDrawer.classList.remove('open');
  filterBtn.setAttribute('aria-expanded', 'false');
  if (!sheet.classList.contains('open')) document.body.classList.remove('no-scroll');
}
filterBtn.addEventListener('click', e => { e.stopPropagation(); filterDrawer.classList.contains('open') ? closeFilter() : openFilter(); });
filterDrawer.addEventListener('click', e => {
  // backdrop or close button dismisses the drawer
  if (e.target === filterDrawer || e.target.closest('#filterClose')){ closeFilter(); return; }
  const opt = e.target.closest('.fp-opt');
  if (opt){
    if (opt.dataset.toggle === 'open') openOnly = !openOnly;
    else if (opt.dataset.toggle === 'built') builtOnly = !builtOnly;
    else if (opt.dataset.toggle === 'due') dueOnly = !dueOnly;
    else if (opt.hasAttribute('data-area')) areaFilter = opt.dataset.area;
    else if (opt.hasAttribute('data-ver')) verFilter = opt.dataset.ver;
    else if (opt.hasAttribute('data-cat')){ const c = opt.dataset.cat; catFilter.has(c) ? catFilter.delete(c) : catFilter.add(c); }
    buildList();  // re-renders the drawer (renderFilters) so checks/badge update; stays open
    return;
  }
  if (e.target.closest('#clearFilters')){ openOnly = false; builtOnly = false; dueOnly = false; areaFilter = ''; verFilter = ''; catFilter.clear(); buildList(); }
});
// Sort dropdown: a single button that opens a popover menu of grouping modes (d30 revised).
// The mode list is dynamic — "By <axis>" and "By version" appear only when they apply.
const sortWrap = document.getElementById('sortWrap');
const sortBtn = document.getElementById('sortBtn');
function sortOptions(){
  const opts = [['recent', 'Recent'], ['phase', 'By phase']];
  if (AXIS) opts.push(['area', 'By ' + AXIS]);
  if (RAW.some(versionOf)) opts.push(['version', 'By version']);
  return opts;
}
function buildSortMenu(){
  const opts = sortOptions();
  document.getElementById('sortMenu').innerHTML = opts.map(([v, l]) =>
    `<button class="sort-opt${v===sortMode?' on':''}" role="option" aria-selected="${v===sortMode}" data-sort="${v}"><span class="sort-check">✓</span>${esc(l)}</button>`
  ).join('');
  const cur = opts.find(([v]) => v === sortMode) || opts[0];
  document.getElementById('sortCur').textContent = cur[1];
}
function closeSortMenu(){ sortWrap.classList.remove('open'); sortBtn.setAttribute('aria-expanded', 'false'); }
sortBtn.addEventListener('click', e => {
  e.stopPropagation();
  const open = sortWrap.classList.toggle('open');
  sortBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
});
document.getElementById('sortMenu').addEventListener('click', e => {
  const b = e.target.closest('.sort-opt'); if (!b) return;
  sortMode = b.dataset.sort;
  closeSortMenu(); buildSortMenu(); buildList();
});
document.addEventListener('click', e => { if (!sortWrap.contains(e.target)) closeSortMenu(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeSortMenu(); });
// Show the app icon (in the top bar and the hero) when one is present in the folder.
// Tries the _project.json "icon" first, then common filenames; stays hidden if none load.
function resolveAppIcon(preferred){
  const imgs = [...document.querySelectorAll('.app-icon')]; if (!imgs.length) return;
  const tries = [preferred, 'icon.svg', 'icon.png', 'favicon.svg', 'favicon.png', 'favicon.ico'].filter(Boolean);
  const hideAll = () => imgs.forEach(im => { im.hidden = true; });
  if (!tries.length){ hideAll(); return; }
  let i = 0;
  const probe = new Image();
  probe.onload  = () => imgs.forEach(im => { im.src = probe.src; im.hidden = false; });
  probe.onerror = () => { i++; if (i < tries.length) probe.src = tries[i]; else hideAll(); };
  probe.src = tries[0];
}

const themeBtn = document.getElementById('theme');
function syncTheme(){
  const t = document.documentElement.getAttribute('data-theme');
  themeBtn.textContent = t === 'light' ? '☾' : '☀';
  themeBtn.title = t === 'light' ? 'Switch to dark' : 'Switch to light';
}
themeBtn.addEventListener('click', () => {
  const next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('dt-theme', next); } catch(e) {}
  syncTheme();
});
syncTheme();

// View toggle: card grid <-> compact list, a segmented control (remembered between visits).
const viewSeg = document.getElementById('viewSeg');
function syncView(){
  viewSeg.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x.dataset.view === viewMode));
}
viewSeg.addEventListener('click', e => {
  const b = e.target.closest('.tab'); if (!b || b.dataset.view === viewMode) return;
  viewMode = b.dataset.view === 'list' ? 'list' : 'cards';
  try { localStorage.setItem('dt-view', viewMode); } catch(e) {}
  syncView();
  buildList();
});
syncView();

// Deep-linking: …/index.html#d5 opens straight into that decision's sheet.
function decisionFromHash(){
  const id = decodeURIComponent((location.hash || '').replace(/^#/, ''));
  return RAW.some(x => x.id === id) ? id : null;
}
window.addEventListener('hashchange', () => {
  const id = decisionFromHash();
  if (id){ if (id !== activeId) openSheet(id); }
  else if (sheet.classList.contains('open')) closeSheet();
});

// ---- load the decision data live, then start ----
// manifest.json lists the filenames; each decision's JSON is fetched + parsed directly.
async function loadData(){
  const [proj, names] = await Promise.all([
    fetch('_project.json').then(r => r.ok ? r.json() : {}).catch(() => ({})),
    fetch('manifest.json').then(r => r.ok ? r.json() : null).catch(() => null)
  ]);
  if (!Array.isArray(names)) throw new Error('manifest unavailable');
  const decisions = (await Promise.all(
    names.map(n => fetch(n).then(r => r.ok ? r.json() : null).catch(() => null))
  )).filter(Boolean);
  return { project: proj.project || 'Decisions', axis: proj.secondaryAxis || '', icon: proj.icon || '', hideTemplateLink: !!proj.hideTemplateLink, decisions, expected: names.length };
}
function showLoadError(){
  const hs = document.getElementById('heroSub'); if (hs) hs.textContent = '';
  document.getElementById('list').innerHTML = `<div class="empty-state">
    Couldn’t read the decision files.<br><br>
    This viewer loads the JSON over <code>http://</code>. In this folder, run<br>
    <code>python3 -m http.server</code><br>then open <code>http://localhost:8000/</code><br><br>
    Opening <code>index.html</code> by double-click uses <code>file://</code>, which the browser blocks from reading local files.</div>`;
}
async function init(){
  let data;
  try { data = await loadData(); }
  catch(e){ showLoadError(); return; }
  if (data.expected > 0 && data.decisions.length === 0){ showLoadError(); return; }
  PROJECT = data.project; AXIS = data.axis; RAW = data.decisions;
  setHeader();
  resolveAppIcon(data.icon);
  // Let a cloned project hide the "Get the free template" promo via _project.json (d51).
  if (data.hideTemplateLink){ const tl = document.getElementById('templateLink'); if (tl) tl.remove(); }
  // Build the Sort menu — "By <axis>" (d26) and "By version" (d36) entries appear only when they apply.
  buildSortMenu();
  buildList();
  const fromHash = decisionFromHash();
  if (fromHash) openSheet(fromHash);
}
init();

// Within an open sheet, ← / → step to the previous / next decision in the visible order.
function visibleCardIds(){ return [...document.querySelectorAll('.phase-sec:not(.collapsed) .dt-item')].map(el => el.dataset.id); }
function stepSheet(dir){
  const ids = visibleCardIds(); if (!ids.length) return;
  let i = ids.indexOf(activeId); if (i === -1) i = dir > 0 ? -1 : 0;
  openSheet(ids[Math.max(0, Math.min(ids.length-1, i+dir))]);
}
function toggleHelp(force){
  const el = document.getElementById('kbhelp');
  el.classList.toggle('open', force !== undefined ? force : !el.classList.contains('open'));
}
document.getElementById('kbhelp').addEventListener('click', e => { if (e.target.id === 'kbhelp') toggleHelp(false); });
document.getElementById('help').addEventListener('click', () => toggleHelp());
document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && (e.key === '?' || e.key === '/')){ e.preventDefault(); toggleHelp(); return; }
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  const car = e.target.closest && e.target.closest('.dep-caret:not(.leaf)');
  if (car && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault();
    const node = car.closest('.dep-node'), open = node.classList.toggle('collapsed')===false;
    car.textContent = open?'▾':'▸'; car.setAttribute('aria-label', open?'Collapse':'Expand'); return; }
  const tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea'){
    if (e.key === 'Escape'){ if (search.value){ search.value=''; filter=''; buildList(); } search.blur(); }
    else if (e.key === 'Enter'){ const ids = visibleCardIds(); if (ids.length) openSheet(ids[0]); search.blur(); e.preventDefault(); }
    return;
  }
  if (e.key === 'Escape'){ if (filterDrawer.classList.contains('open')) closeFilter(); else if (sheet.classList.contains('open')) closeSheet(); else toggleHelp(false); }
  else if (e.key === '/'){ e.preventDefault(); search.focus(); }
  else if (sheet.classList.contains('open') && (e.key === 'ArrowRight' || e.key === 'ArrowDown')){ e.preventDefault(); stepSheet(1); }
  else if (sheet.classList.contains('open') && (e.key === 'ArrowLeft' || e.key === 'ArrowUp')){ e.preventDefault(); stepSheet(-1); }
});
