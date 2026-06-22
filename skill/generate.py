#!/usr/bin/env python3
"""Build the 'decision explorer' viewer from the decision JSON files.

Usage:
    python3 generate.py [decisions_dir] [out_dir_or_legacy_html_path]

Defaults to ./decisions as both the input and output folder.

The viewer is ONE SHARED template across all projects (d28 revised again). The code lives in a
single canonical folder — ~/.claude/skills/decision-tree/viewer/ — and every project's decisions/
folder just SYMLINKS to it. So updating the template once (edit the canonical files, or any
project's symlinked copy) shows up in every project automatically; the only thing local to a
project is its DATA. Files in a project's decisions/ folder:
  - manifest.json — GENERATED every run: the ordered list of decision filenames. The viewer
                  fetches it, then reads each decision's JSON file directly at runtime, so
                  decision *content* is never copied anywhere — edit a JSON and refresh. (local data)
  - _project.json, NNNN-*.json, icon — the project's own data (local).
  - index.html / styles.css / app.js — SYMLINKS to the canonical shared viewer (not real files).
  - graph.html  — a tiny redirect to index.html, kept so old links / the Stop hook still work.

The canonical viewer is seeded once from the templates bundled below if it doesn't exist yet;
after that the canonical files are the source of truth. Each regenerate self-heals the symlinks,
so a new project, a moved folder, or a broken link is fixed automatically on the next run.

Design (decisions d2 + d27, refined): an apple.com-style editorial layout — no top bar (the
light/dark + keyboard-help buttons float at the top of the page), a big centered hero whose
title carries an optional app-icon lockup to its left (shown only when an icon file is present),
a full-width search as the hero of one calm control bar with a Sort · Filter · View pill cluster
(d29/d30), decisions as cards or a compact list grouped by SDLC phase, and a focused modal sheet
that opens one decision at a time (chosen option + why, the options × tradeoffs comparison,
impact, and revision history).

The viewer reads the JSON files live over http://, so SERVE the folder (e.g. `python3 -m http.server`)
and open index.html there. Opening it by double-click (file://) is blocked by the browser from
reading local files (decision d28 revised; adopts the local-server option weighed in d8).
"""
import json
import sys
import os
import re


STYLES_CSS = r'''
:root {
  --bg:#000000; --surface:#1c1c1e; --card:#1c1c1e; --ink:#f5f5f7; --ink2:#c7c7cc;
  --muted:#98989d; --faint:#6e6e73; --line:#2a2a2c; --line2:#3a3a3c;
  --accent:#3bc4b6; --accent-soft:rgba(59,196,182,.14); --focus:rgba(59,196,182,.42);
  --nav-blur:rgba(0,0,0,.6);
  --pos:#54c98a; --neg:#f0746b; --neu:#dab35f;
  --pos-soft:rgba(84,201,138,.12); --neg-soft:rgba(240,116,107,.12);
  --shadow-sm:0 1px 2px rgba(0,0,0,.4); --shadow-card:0 1px 3px rgba(0,0,0,.3);
  --shadow-hover:0 14px 36px rgba(0,0,0,.55); --shadow-modal:0 30px 90px rgba(0,0,0,.65);
  --radius:14px; --radius-lg:20px; --radius-xl:26px;
}
:root[data-theme="light"] {
  --bg:#fbfbfd; --surface:#ffffff; --card:#ffffff; --ink:#1d1d1f; --ink2:#424245;
  --muted:#6e6e73; --faint:#86868b; --line:#e6e6e9; --line2:#d2d2d7;
  --accent:#0d8478; --accent-soft:rgba(13,132,120,.09); --focus:rgba(13,132,120,.28);
  --nav-blur:rgba(251,251,253,.72);
  --pos:#1f9e57; --neg:#d1453b; --neu:#9a7320;
  --pos-soft:rgba(31,158,87,.08); --neg-soft:rgba(209,69,59,.07);
  --shadow-sm:0 1px 2px rgba(0,0,0,.07); --shadow-card:0 2px 12px rgba(0,0,0,.05);
  --shadow-hover:0 14px 34px rgba(0,0,0,.1); --shadow-modal:0 30px 90px rgba(0,0,0,.2);
}
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
html,body { margin:0; min-height:100%; }
body { background:var(--bg); color:var(--ink);
       font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Segoe UI",Roboto,sans-serif;
       -webkit-font-smoothing:antialiased; -moz-osx-font-smoothing:grayscale; letter-spacing:-.01em; }
body.no-scroll { overflow:hidden; }

/* ---- floating top buttons (theme + help) ---- */
.topbtns { position:absolute; top:14px; right:18px; z-index:30; display:flex; gap:8px; }
.app-icon { border-radius:6px; object-fit:cover; flex:none; }
.app-icon[hidden] { display:none; }
.tab { font-size:12.5px; font-weight:500; padding:6px 14px; border-radius:980px; border:none;
       background:transparent; color:var(--muted); cursor:pointer; transition:color .15s,background .15s; }
.tab:hover { color:var(--ink); }
.tab.active { background:var(--surface); color:var(--ink); box-shadow:var(--shadow-sm); font-weight:600; }
.iconbtn { font-size:15px; line-height:1; width:32px; height:32px; border-radius:50%; border:none;
           background:var(--card); color:var(--muted); cursor:pointer; transition:color .15s,background .15s;
           display:inline-flex; align-items:center; justify-content:center; }
.iconbtn:hover { color:var(--ink); background:var(--line2); }

/* ---- page ---- */
main { max-width:1160px; margin:0 auto; padding:0 32px 120px; }

/* control bar above the list — sticks under the nav; search is the prominent element */
.toolbar { position:sticky; top:0; z-index:15; display:flex; align-items:center; flex-wrap:wrap;
           gap:10px 12px; padding:14px 0; margin-bottom:4px; background:var(--bg); border-bottom:1px solid var(--line); }
.tb-search { position:relative; flex:1 1 280px; }
.tb-search > svg { position:absolute; left:15px; top:50%; transform:translateY(-50%); width:17px; height:17px; color:var(--faint); pointer-events:none; }
.tb-search input { width:100%; font-size:14.5px; padding:10px 16px 10px 42px; border-radius:980px; outline:none;
           border:1px solid var(--line2); background:var(--card); color:var(--ink); transition:box-shadow .15s,background .15s,border-color .15s; }
.tb-search input::placeholder { color:var(--faint); }
.tb-search input:focus { background:var(--surface); border-color:var(--accent); box-shadow:0 0 0 3px var(--focus); }
.tb-search input::-webkit-search-cancel-button { -webkit-appearance:none; }
.tb-right { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }

/* segmented controls (Sort + View) — reuse the .tab pill styling */
.seg { display:inline-flex; align-items:center; gap:2px; background:var(--card); padding:2px;
       border-radius:980px; border:1px solid var(--line); }
.seg-lbl { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.5px;
           color:var(--faint); padding:0 7px 0 10px; user-select:none; }
.tab-icon { display:inline-flex; align-items:center; justify-content:center; padding:6px 11px; }
.tab-icon > svg { width:16px; height:16px; display:block; }

/* filter button + drawer */
.filter-wrap { position:relative; }
.filter-btn { display:inline-flex; align-items:center; gap:7px; font-size:13px; font-weight:500; padding:8px 14px;
              border-radius:980px; border:1px solid var(--line2); background:var(--card); color:var(--ink); cursor:pointer; transition:.15s; }
.filter-btn:hover { border-color:var(--ink2); }
.filter-btn.active { border-color:var(--accent); color:var(--accent); }
.filter-btn > svg { width:16px; height:16px; }
.filter-badge { min-width:18px; height:18px; padding:0 5px; border-radius:980px; background:var(--accent); color:#fff;
                font-size:11px; font-weight:700; display:inline-flex; align-items:center; justify-content:center; }
.filter-badge:empty { display:none; }
/* Filter drawer: same overlay treatment as the modal sheet, sliding in from the right (d30 revised). */
.drawer { position:fixed; inset:0; z-index:40; background:rgba(0,0,0,.45); opacity:0; pointer-events:none;
          transition:opacity .2s; -webkit-backdrop-filter:blur(5px); backdrop-filter:blur(5px); }
.drawer.open { opacity:1; pointer-events:auto; }
.drawer-card { position:absolute; top:0; right:0; height:100%; width:340px; max-width:88vw;
               background:var(--surface); border-left:1px solid var(--line); box-shadow:var(--shadow-modal);
               display:flex; flex-direction:column; transform:translateX(100%);
               transition:transform .26s cubic-bezier(.2,.7,.3,1); }
.drawer.open .drawer-card { transform:none; }
.drawer-head { display:flex; align-items:center; justify-content:space-between;
               padding:22px 22px 14px; border-bottom:1px solid var(--line); }
.drawer-title { font-size:19px; font-weight:600; letter-spacing:-.01em; }
.drawer-close { width:34px; height:34px; flex:none; border:none; border-radius:50%; background:var(--card);
                color:var(--muted); font-size:16px; cursor:pointer; display:inline-flex; align-items:center;
                justify-content:center; transition:.15s; }
.drawer-close:hover { background:var(--line2); color:var(--ink); }
.filter-pop { flex:1; overflow-y:auto; padding:10px 12px 18px; }
.fp-sec { padding:6px 4px 8px; }
.fp-sec + .fp-sec { border-top:1px solid var(--line); }
.fp-h { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.5px; color:var(--faint); padding:4px 10px 6px; }
.fp-opt { display:flex; align-items:center; gap:9px; width:100%; text-align:left; font-size:13.5px; padding:8px 10px;
          border:none; background:transparent; color:var(--ink); border-radius:9px; cursor:pointer; }
.fp-opt:hover { background:var(--card); }
.fp-check { width:14px; flex:none; color:var(--accent); font-weight:800; visibility:hidden; }
.fp-opt.on .fp-check { visibility:visible; }
.fp-n { margin-left:auto; color:var(--faint); font-size:12px; font-variant-numeric:tabular-nums; }
.drawer-foot { flex:none; border-top:1px solid var(--line); padding:12px 16px; background:var(--surface); }
.fp-clear { width:100%; font-size:13px; font-weight:500; padding:10px; border:1px solid var(--line2);
            background:var(--card); color:var(--ink2); border-radius:10px; cursor:pointer; transition:.15s; }
.fp-clear:hover { color:var(--neg); border-color:var(--neg); }

@media (max-width:680px){
  .tb-search { flex:1 1 100%; order:-1; max-width:none; }
  .tb-right { margin-left:auto; }
}

/* hero */
.hero { text-align:center; padding:72px 0 16px; }
.hero-name { display:flex; align-items:center; justify-content:center; gap:clamp(12px,2vw,20px); }
.hero-icon { width:clamp(46px,7vw,72px); height:clamp(46px,7vw,72px); border-radius:20px; box-shadow:var(--shadow-card); }
.hero h1 { font-size:clamp(40px,7vw,80px); font-weight:700; letter-spacing:-.035em; line-height:1.03; margin:0; }
.hero-sub { font-size:clamp(17px,2.1vw,21px); font-weight:400; color:var(--muted); letter-spacing:-.01em;
            margin:18px 0 0; }
.hero-filters { display:flex; justify-content:center; flex-wrap:wrap; gap:8px; margin-top:30px; }
.hero-filters:empty { display:none; }
.chip { font-size:12.5px; padding:5px 13px; border-radius:980px; cursor:pointer;
        border:1px solid var(--line2); background:transparent; color:var(--muted); transition:all .15s; }
.chip:hover { color:var(--ink); border-color:var(--ink2); }
.chip.active { color:#fff; background:var(--accent); border-color:var(--accent); }
.chip.open-chip.active { background:var(--neg); border-color:var(--neg); }
.chip-n { font-weight:700; margin-left:3px; }

/* phase sections */
.phase-sec { margin-top:60px; }
.phase-sec.pinned .sec-name { color:var(--neg); }
.sec-head { display:flex; align-items:center; gap:11px; margin-bottom:24px; padding-bottom:15px;
            border-bottom:1px solid var(--line); cursor:pointer; user-select:none; }
.sec-head:focus-visible { outline:none; box-shadow:0 0 0 3px var(--focus); border-radius:8px; }
.sec-caret { color:var(--faint); font-size:13px; line-height:1; flex:none; transition:transform .15s,color .15s; }
.sec-head:hover .sec-caret { color:var(--ink); }
.phase-sec.collapsed .sec-caret { transform:rotate(-90deg); }
.phase-sec.collapsed .sec-head { margin-bottom:0; }
.phase-sec.collapsed .sec-body { display:none; }
.sec-dot { width:11px; height:11px; border-radius:50%; flex:none; }
.sec-name { font-size:27px; font-weight:700; letter-spacing:-.022em; margin:0; }

/* card grid */
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:18px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:var(--radius-lg);
        padding:22px 22px 18px; cursor:pointer; display:flex; flex-direction:column; box-shadow:var(--shadow-card);
        transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease; }
.card:hover { transform:translateY(-3px); box-shadow:var(--shadow-hover); border-color:var(--line2); }
.card:focus-visible { outline:none; box-shadow:0 0 0 3px var(--focus); }
.card-head { display:flex; align-items:center; gap:8px; margin-bottom:14px; }
.phase-pill { font-size:10px; font-weight:700; letter-spacing:.5px; text-transform:uppercase;
              padding:3px 10px; border-radius:980px; }
.card-date { margin-left:auto; font-size:12px; color:var(--faint); font-variant-numeric:tabular-nums; }
.card-title { font-size:20px; font-weight:600; letter-spacing:-.02em; line-height:1.24; margin:0 0 13px; color:var(--ink); }
.card-chosen { font-size:14px; font-weight:600; color:var(--accent); line-height:1.4; margin-bottom:11px; }
.card-chosen.open { color:var(--neg); }
.card-why { font-size:14px; color:var(--ink2); line-height:1.55; margin:0;
            display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }
.card-foot { margin-top:15px; display:flex; gap:7px; align-items:center; flex-wrap:wrap; }
.card-cat, .card-rev { font-size:11px; padding:3px 9px; border-radius:980px; border:1px solid var(--line2); }
.card-cat { color:var(--muted); }
.card-rev { color:var(--neu); border-color:var(--neu); }

/* compact list view (alternative to the card grid) */
.dlist { border:1px solid var(--line); border-radius:var(--radius-lg); overflow:hidden; background:var(--card); box-shadow:var(--shadow-card); }
.row { display:flex; align-items:center; gap:14px; padding:14px 18px; cursor:pointer; border-bottom:1px solid var(--line); transition:background .12s; }
.row:last-child { border-bottom:none; }
.row:hover { background:var(--accent-soft); }
.row:focus-visible { outline:none; background:var(--accent-soft); box-shadow:inset 0 0 0 2px var(--focus); }
.row-dot { width:9px; height:9px; border-radius:50%; flex:none; }
.row-main { flex:1; min-width:0; display:flex; flex-direction:column; gap:2px; }
.row-title { font-size:15px; font-weight:600; letter-spacing:-.01em; color:var(--ink); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.row-chosen { font-size:12.5px; color:var(--accent); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.row-chosen.open { color:var(--neg); }
.row-cat, .row-rev { font-size:11px; padding:2px 9px; border-radius:980px; flex:none; }
.row-cat { color:var(--muted); border:1px solid var(--line2); }
.row-rev { color:var(--neu); border:1px solid var(--neu); }
.row-date { font-size:12px; color:var(--faint); flex:none; font-variant-numeric:tabular-nums; min-width:86px; text-align:right; }
.row-arrow { color:var(--faint); font-size:18px; line-height:1; flex:none; }
@media (max-width:680px){ .row-cat, .row-rev, .row-date { display:none; } }

.empty-state { color:var(--muted); text-align:center; padding:90px 20px; line-height:1.7; font-size:15px; }
code { background:var(--card); padding:2px 7px; border-radius:6px; font-size:13px; }

/* ---- modal sheet (one decision) ---- */
.sheet { position:fixed; inset:0; z-index:40; display:flex; align-items:flex-start; justify-content:center;
         padding:6vh 20px 30px; background:rgba(0,0,0,.45); opacity:0; pointer-events:none; transition:opacity .2s;
         -webkit-backdrop-filter:blur(5px); backdrop-filter:blur(5px); }
.sheet.open { opacity:1; pointer-events:auto; }
.sheet-card { position:relative; background:var(--surface); border:1px solid var(--line);
              border-radius:var(--radius-xl); width:100%; max-width:760px; max-height:88vh; overflow-y:auto;
              padding:44px 48px 52px; box-shadow:var(--shadow-modal);
              transform:translateY(20px) scale(.985); transition:transform .24s cubic-bezier(.2,.7,.3,1); }
.sheet.open .sheet-card { transform:none; }
.sheet-close { position:sticky; top:0; float:right; margin:-12px -16px 0 0; width:34px; height:34px; flex:none;
               border:none; border-radius:50%; background:var(--card); color:var(--muted); font-size:16px;
               cursor:pointer; display:inline-flex; align-items:center; justify-content:center; transition:.15s; }
.sheet-close:hover { background:var(--line2); color:var(--ink); }

.d-title { font-size:31px; font-weight:700; letter-spacing:-.025em; line-height:1.15; margin:0 30px 14px 0; }
.d-sub { display:flex; align-items:center; gap:8px; flex-wrap:wrap; font-size:12.5px; color:var(--muted); margin:0 0 26px; }
.d-sub .pdot { width:8px; height:8px; border-radius:50%; flex:none; }
.tag { font-size:10px; padding:2px 9px; border-radius:980px; border:1px solid var(--line2); }
.tag.open { color:var(--neg); border-color:var(--neg); }
.tag.revised { color:var(--neu); border-color:var(--neu); cursor:pointer; }

.chosen-box { background:var(--pos-soft); border-radius:var(--radius-lg); padding:20px 22px; margin-bottom:28px; }
.chosen-box.open { background:var(--neg-soft); }
.chosen-cap { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.7px; color:var(--muted); margin-bottom:6px; }
.chosen-val { font-size:18px; font-weight:600; color:var(--pos); line-height:1.4; letter-spacing:-.01em; }
.chosen-box.open .chosen-val { color:var(--neg); }
.chosen-box .why { margin-top:14px; font-size:14.5px; line-height:1.65; color:var(--ink2); }
.why-q { font-size:12.5px; color:var(--muted); font-style:italic; margin-top:12px; }
.why-q.sep { padding-top:12px; border-top:1px solid var(--line); }

.section { margin:0 0 24px; }
.lbl { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.7px; color:var(--faint); margin-bottom:8px; }
.lbl-n { font-weight:500; text-transform:none; letter-spacing:0; color:var(--faint); }
.section.impact { margin-bottom:16px; display:grid; gap:12px 28px;
                  grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); align-items:start; }
@media (max-width:560px){ .section.impact { grid-template-columns:1fr; } }

.dep-row { display:flex; align-items:center; gap:9px; padding:9px 2px; cursor:pointer; border-bottom:1px solid var(--line); }
.dep-row:last-child { border-bottom:none; }
.dep-row:hover .dep-name { color:var(--accent); }
.dep-arrow { color:var(--faint); font-size:13px; flex:none; }
.dep-name { font-size:13.5px; color:var(--ink2); flex:1; }
.dep-row.nested .dep-arrow { opacity:.55; }
.dep-row.nested .dep-name { color:var(--muted); font-size:12.5px; }
.dep-empty { font-size:13px; color:var(--faint); padding:6px 2px; }
.pill { font-size:10.5px; padding:3px 9px; border-radius:980px; color:var(--accent); background:var(--accent-soft); }

/* collapsible folds */
.fold { border-top:1px solid var(--line); }
.fold-head { display:flex; align-items:center; gap:8px; cursor:pointer; user-select:none; padding:14px 2px; }
.fold-head:hover .fold-lbl { color:var(--ink); }
.fold-head .caret { color:var(--faint); width:10px; font-size:10px; }
.fold-lbl { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.7px; color:var(--faint); }
.fold[data-open="0"] .fold-body { display:none; }
.fold-body { padding:2px 0 16px; }
.hist { font-size:13px; line-height:1.6; color:var(--muted); border-left:2px solid var(--neu); padding:2px 0 2px 13px; }
.hist .from { color:var(--ink2); }
.tr-empty { font-size:12.5px; color:var(--faint); }

/* options-compared matrix */
.cmp-wrap { overflow-x:auto; margin-top:2px; }
.cmp { border-collapse:collapse; width:100%; font-size:12.5px; }
.cmp th, .cmp td { text-align:left; vertical-align:top; padding:9px 11px; border-bottom:1px solid var(--line); }
.cmp-corner { border-bottom:1px solid var(--line2); }
.cmp-opt { font-size:12px; font-weight:700; color:var(--ink2); border-bottom:2px solid var(--line2); min-width:118px; white-space:normal; }
.cmp-opt.chosen { color:var(--pos); border-bottom-color:var(--pos); }
.cmp-tick { font-weight:800; }
.cmp-crit { color:var(--ink); font-weight:600; font-size:12px; min-width:116px; }
.cmp-cell { color:var(--ink2); line-height:1.45; }
.cmp-cell.chosen { background:var(--pos-soft); }
.cmp-cell.empty { color:var(--faint); text-align:center; }
.cmp-cell .s { font-weight:800; font-size:13.5px; margin-right:3px; }
.cmp-note { color:var(--muted); font-size:12px; }

@media (max-width:680px) {
  main { padding:0 18px 90px; }
  .sheet-card { padding:34px 24px 40px; }
  .d-title { font-size:26px; margin-right:24px; }
  /* comparison table -> stacked cards, no sideways scroll */
  .cmp-wrap { overflow-x:visible; }
  .cmp, .cmp thead, .cmp tbody, .cmp tr, .cmp th, .cmp td { display:block; width:auto; }
  .cmp thead { display:none; }
  .cmp tbody tr { border:1px solid var(--line); border-radius:var(--radius); padding:11px 13px; margin-bottom:10px; }
  .cmp tbody tr th, .cmp tbody tr td { border-bottom:none; padding:3px 0; }
  .cmp-crit { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.4px; color:var(--ink); margin-bottom:5px; }
  .cmp-cell.chosen { background:none; }
  .cmp-cell.empty { display:none; }
  .cmp-cell::before { content:attr(data-opt) " "; color:var(--faint); font-weight:600; margin-right:5px; }
  .cmp-cell.chosen::before { color:var(--pos); }
}

/* keyboard shortcuts overlay */
.kbhelp { position:fixed; inset:0; z-index:50; display:none; align-items:center; justify-content:center; background:rgba(0,0,0,.45); }
.kbhelp.open { display:flex; }
.kbhelp-card { background:var(--surface); border:1px solid var(--line2); border-radius:var(--radius-lg);
               padding:20px 24px; min-width:250px; box-shadow:var(--shadow-modal); }
.kbhelp-h { font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:.5px; color:var(--muted); margin-bottom:14px; }
.kbrow { display:flex; align-items:center; gap:9px; margin:9px 0; font-size:13px; }
.kbrow span { color:var(--muted); }
.kbrow kbd { font-family:inherit; font-size:11px; min-width:22px; text-align:center; padding:2px 7px;
             border:1px solid var(--line2); border-bottom-width:2px; border-radius:6px; background:var(--card); color:var(--ink); }
'''


INDEX_HTML = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Decision Explorer</title>
<link rel="stylesheet" href="styles.css">
<script>
  /* set the theme before paint so there's no flash */
  (function(){
    try {
      var t = localStorage.getItem('dt-theme');
      if (t !== 'light' && t !== 'dark')
        t = (window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', t);
    } catch(e) { document.documentElement.setAttribute('data-theme', 'dark'); }
  })();
</script>
</head>
<body>
<div class="topbtns">
  <button class="iconbtn" id="theme" title="Toggle light/dark">&#9728;</button>
  <button class="iconbtn" id="help" title="Keyboard shortcuts (Cmd+?)">?</button>
</div>
<main>
  <section class="hero">
    <div class="hero-name">
      <img class="app-icon hero-icon" alt="" hidden>
      <h1 id="heroTitle">Decisions</h1>
    </div>
    <p class="hero-sub" id="heroSub"></p>
  </section>
  <div class="toolbar" id="toolbar">
    <div class="tb-search">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><line x1="16.5" y1="16.5" x2="21" y2="21"></line></svg>
      <input id="search" type="search" placeholder="Search decisions">
    </div>
    <div class="tb-right">
      <div class="seg" id="sort" role="group" aria-label="Sort decisions">
        <span class="seg-lbl">Sort</span>
        <button class="tab" data-sort="recent">Recent</button>
              <button class="tab active" data-sort="phase">By phase</button>
</div>
      <div class="filter-wrap">
        <button class="filter-btn" id="filterBtn" title="Filter" aria-haspopup="dialog" aria-expanded="false">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="4" y1="7" x2="20" y2="7"></line><line x1="7" y1="12" x2="17" y2="12"></line><line x1="10" y1="17" x2="14" y2="17"></line></svg>
          Filter<span class="filter-badge" id="filterBadge"></span>
        </button>
      </div>
      <div class="seg" id="viewSeg" role="group" aria-label="View as">
        <span class="seg-lbl">View</span>
        <button class="tab tab-icon active" data-view="cards" title="Card grid" aria-label="Card grid">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"></rect><rect x="14" y="3" width="7" height="7" rx="1.5"></rect><rect x="3" y="14" width="7" height="7" rx="1.5"></rect><rect x="14" y="14" width="7" height="7" rx="1.5"></rect></svg>
        </button>
        <button class="tab tab-icon" data-view="list" title="Compact list" aria-label="Compact list">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><circle cx="3.5" cy="6" r="1.2" fill="currentColor" stroke="none"></circle><circle cx="3.5" cy="12" r="1.2" fill="currentColor" stroke="none"></circle><circle cx="3.5" cy="18" r="1.2" fill="currentColor" stroke="none"></circle></svg>
        </button>
      </div>
    </div>
  </div>
  <div id="list"></div>
</main>
<div id="filterDrawer" class="drawer" role="dialog" aria-modal="true" aria-label="Filter decisions">
  <aside class="drawer-card">
    <header class="drawer-head">
      <h2 class="drawer-title">Filter</h2>
      <button class="drawer-close" id="filterClose" aria-label="Close">&#10005;</button>
    </header>
    <div class="filter-pop" id="filterPop"></div>
    <div class="drawer-foot" id="filterFoot" hidden>
      <button class="fp-clear" id="clearFilters">Clear filters</button>
    </div>
  </aside>
</div>
<div id="sheet" class="sheet"><div class="sheet-card" id="sheetBody"></div></div>
<div id="kbhelp" class="kbhelp">
  <div class="kbhelp-card">
    <div class="kbhelp-h">Keyboard</div>
    <div class="kbrow"><kbd>/</kbd><span>search</span></div>
    <div class="kbrow"><kbd>Enter</kbd><span>open the top result</span></div>
    <div class="kbrow"><kbd>&larr;</kbd><kbd>&rarr;</kbd><span>prev / next decision (in a sheet)</span></div>
    <div class="kbrow"><kbd>Esc</kbd><span>close</span></div>
    <div class="kbrow"><kbd>Cmd+?</kbd><span>this help</span></div>
  </div>
</div>
<script src="app.js"></script>
</body>
</html>
'''


APP_JS = r'''// Decision Explorer logic. Reads window.DT_DATA (set by data.js) and renders an apple.com-style
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
function orderPhases(present){
  return PHASE_ORDER.filter(p => present.includes(p))
    .concat(present.filter(p => !PHASE_ORDER.includes(p)).sort());
}
function matches(d, f){
  if (!f) return true;
  const hay = [d.title, d.phase, d.category, d.rationale, d.question,
    (d.options||[]).map(o => o.label + ' ' + (o.tradeoffs||[]).map(t => t.criterion + ' ' + (t.note||'')).join(' ')).join(' ')
  ].join(' ').toLowerCase();
  return hay.includes(f.toLowerCase());
}

let activeId = null;          // the decision shown in the open sheet, or null
let sortMode = 'phase';
let filter = '';
let openOnly = false;
let areaFilter = '';
let catFilter = new Set();    // selected categories (multi-select); empty = all
let collapsed = new Set();    // section names folded shut in the list (persists across re-renders)
let viewMode = (function(){ try { return localStorage.getItem('dt-view')==='list' ? 'list' : 'cards'; } catch(e){ return 'cards'; } })();

const isOpen = d => d.status === 'open';
const passes = d => matches(d, filter)
  && (!areaFilter || areaOf(d) === areaFilter)
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
  document.title = PROJECT + ' — Decision Explorer';
  const openN = RAW.filter(isOpen).length;
  const hs = document.getElementById('heroSub');
  if (hs) hs.textContent = RAW.length
    ? RAW.length + ' decision' + (RAW.length===1?'':'s') + (openN ? ' · ' + openN + ' still open' : '')
    : 'No decisions logged yet';
}

// ---- cards ----
function cardHTML(d){
  const p = phaseOf(d), ch = chosenOf(d), pc = phaseColor(p);
  const rev = d.history && d.history.length ? '<span class="card-rev">revised</span>' : '';
  const shown = lastActivity(d);  // card shows the last-revised date (created date lives in the sheet)
  return `<article class="dt-item card${isOpen(d)?' is-open':''}" data-id="${esc(d.id)}" tabindex="0">
    <div class="card-head">
      <span class="phase-pill" style="color:${pc};background:${pc}22">${esc(p)}</span>
      ${shown?`<span class="card-date">${fmtDate(shown,false)}</span>`:''}
    </div>
    <h3 class="card-title">${esc(d.title)}</h3>
    <div class="card-chosen${ch?'':' open'}">${ch?'✓ '+esc(ch.label):'Open — undecided'}</div>
    ${d.rationale?`<p class="card-why">${esc(d.rationale)}</p>`:''}
    <div class="card-foot">${d.category?`<span class="card-cat">${esc(d.category)}</span>`:''}${rev}</div>
  </article>`;
}
function rowHTML(d){
  const p = phaseOf(d), ch = chosenOf(d), pc = phaseColor(p);
  const rev = d.history && d.history.length ? '<span class="row-rev">revised</span>' : '';
  const shown = lastActivity(d);  // row shows the last-revised date (created date lives in the sheet)
  return `<div class="dt-item row${isOpen(d)?' is-open':''}" data-id="${esc(d.id)}" tabindex="0">
    <span class="row-dot" style="background:${pc}"></span>
    <div class="row-main">
      <span class="row-title">${esc(d.title)}</span>
      <span class="row-chosen${ch?'':' open'}">${ch?'✓ '+esc(ch.label):'Open — undecided'}</span>
    </div>
    ${d.category?`<span class="row-cat">${esc(d.category)}</span>`:''}${rev}
    ${shown?`<span class="row-date">${fmtDate(shown,false)}</span>`:''}
    <span class="row-arrow">›</span>
  </div>`;
}
function sectionHTML(name, color, items, pinned){
  const isCol = collapsed.has(name);
  const inner = viewMode === 'list'
    ? `<div class="dlist">${items.map(rowHTML).join('')}</div>`
    : `<div class="grid">${items.map(cardHTML).join('')}</div>`;
  return `<section class="phase-sec${pinned?' pinned':''}${isCol?' collapsed':''}">
    <header class="sec-head" data-sec="${esc(name)}" role="button" tabindex="0" aria-expanded="${isCol?'false':'true'}">
      <span class="sec-caret" aria-hidden="true">▾</span><span class="sec-dot" style="background:${color}"></span>
      <h2 class="sec-name">${esc(name)} (${items.length})</h2></header>
    <div class="sec-body">${inner}</div>
  </section>`;
}
function toggleSection(name){ collapsed.has(name) ? collapsed.delete(name) : collapsed.add(name); buildList(); }

// Build the Filter drawer contents + update the button's active state and count badge.
function renderFilters(){
  const pop = document.getElementById('filterPop');
  const openN = RAW.filter(isOpen).length;
  let h = '';
  if (openN){
    h += `<div class="fp-sec"><div class="fp-h">Show</div>
      <button class="fp-opt${openOnly?' on':''}" data-toggle="open"><span class="fp-check">✓</span>Open decisions only<span class="fp-n">${openN}</span></button></div>`;
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
  const cats = [...new Set(RAW.map(d => d.category).filter(Boolean))].sort();
  if (cats.length){
    h += `<div class="fp-sec"><div class="fp-h">Category</div>`
      + cats.map(c => {
          const n = RAW.filter(d => d.category === c).length;
          return `<button class="fp-opt${catFilter.has(c)?' on':''}" data-cat="${esc(c)}"><span class="fp-check">✓</span>${esc(c)}<span class="fp-n">${n}</span></button>`;
        }).join('')
      + `</div>`;
  }
  const active = (openOnly?1:0) + (areaFilter?1:0) + catFilter.size;
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

  if (openOnly){
    const items = RAW.filter(d => isOpen(d) && passes(d)).sort(byRecency);
    root.innerHTML = items.length ? sectionHTML('Needs deciding', 'var(--neg)', items, true)
      : '<div class="empty-state">No open decisions'+(filter?' match “'+esc(filter)+'”':'')+'.</div>';
    return;
  }

  const pinned = RAW.filter(d => isOpen(d) && passes(d));
  let html = pinned.length ? sectionHTML('Needs deciding', 'var(--neg)', pinned, true) : '';
  let body = '';

  if (sortMode === 'recent'){
    const items = RAW.filter(passes).sort(byRecency);
    if (items.length) body = sectionHTML('Recent', 'var(--accent)', items, false);
  } else if (sortMode === 'area' && AXIS){
    const groups = {};
    RAW.forEach(d => { const a = areaOf(d) || 'Unassigned'; (groups[a] = groups[a] || []).push(d); });
    Object.keys(groups).sort((a,b) => a==='Unassigned'?1 : b==='Unassigned'?-1 : a.localeCompare(b)).forEach(a => {
      const items = groups[a].filter(passes);
      if (items.length) body += sectionHTML(a, 'var(--faint)', items, false);
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
function depRows(ids, dir){
  if (!ids.length) return `<div class="dep-empty">${dir==='up'?'No upstream dependencies':'No downstream decisions'}</div>`;
  return ids.map(id => {
    const dd = RAW.find(x => x.id===id); if (!dd) return '';
    return `<div class="dep-row" data-jump="${esc(id)}"><span class="dep-arrow">${dir==='up'?'↑':'↓'}</span>
      <span class="dep-name">${esc(dd.title)}</span>${dd.category?`<span class="pill">${esc(dd.category)}</span>`:''}</div>`;
  }).join('');
}
function downstreamCascade(rootId){
  const out = [], visited = new Set([rootId]);
  (function walk(id, depth){
    RAW.filter(x => (x.dependsOn||[]).includes(id)).map(x => x.id).sort().forEach(k => {
      if (visited.has(k)) return; visited.add(k); out.push({ id:k, depth }); walk(k, depth+1);
    });
  })(rootId, 0);
  return out;
}
function downRows(rows){
  if (!rows.length) return `<div class="dep-empty">No downstream decisions</div>`;
  return rows.map(({id, depth}) => {
    const dd = RAW.find(x => x.id===id); if (!dd) return '';
    return `<div class="dep-row${depth?' nested':''}" data-jump="${esc(id)}" style="padding-left:${2+depth*16}px">
      <span class="dep-arrow">↓</span><span class="dep-name">${esc(dd.title)}</span>${dd.category?`<span class="pill">${esc(dd.category)}</span>`:''}</div>`;
  }).join('');
}

function sheetHTML(d){
  const ch = chosenOf(d), p = phaseOf(d);
  const upstream = d.dependsOn || [], downCascade = downstreamCascade(d.id);
  const revised = d.history && d.history.length;
  let h = `<button class="sheet-close" aria-label="Close">✕</button>`;
  h += `<h2 class="d-title">${esc(d.title)}</h2>`;
  h += `<div class="d-sub"><span class="pdot" style="background:${phaseColor(p)}"></span>
    <span>${esc(p)}${d.category?' · '+esc(d.category):''}${(AXIS && d.area)?' · '+esc(d.area):''}${d.date?' · '+fmtDate(d.date,true):''}</span>
    ${d.status==='open'?'<span class="tag open">open</span>':''}
    ${revised?'<span class="tag revised" data-open-fold="history">revised</span>':''}</div>`;
  h += `<div class="chosen-box${ch?'':' open'}">
    <div class="chosen-cap">${ch?'✓ Chosen':'Status'}</div>
    <div class="chosen-val">${ch?esc(ch.label):'Still open — no option chosen yet'}</div>
    ${d.rationale?`<div class="why">${esc(d.rationale)}</div>`:''}
    ${d.question?`<div class="why-q${d.rationale?' sep':''}">${esc(d.question)}</div>`:''}</div>`;
  if (downCascade.length || upstream.length){
    h += `<div class="section impact">`;
    if (downCascade.length) h += `<div class="imp-grp"><div class="lbl">Affects${downCascade.length>1?` <span class="lbl-n">${downCascade.length} downstream</span>`:''}</div>${downRows(downCascade)}</div>`;
    if (upstream.length)    h += `<div class="imp-grp"><div class="lbl">Depends on</div>${depRows(upstream,'up')}</div>`;
    h += `</div>`;
  }
  const nopt = (d.options||[]).length;
  h += `<section class="fold" data-open="1"><header class="fold-head"><span class="caret">▾</span><span class="fold-lbl">Options compared${nopt?` (${nopt})`:''}</span></header><div class="fold-body">${tradeoffMatrix(d)}</div></section>`;
  if (revised)
    h += `<section class="fold" data-open="0" data-fold="history"><header class="fold-head"><span class="caret">▸</span><span class="fold-lbl">Revision history (${d.history.length})</span></header><div class="fold-body"><div class="hist">${d.history.map(x => `was <span class="from">“${esc(x.from)}”</span> — ${esc(x.reason)}${x.date?' ('+fmtDate(x.date,true)+')':''}`).join('<br><br>')}</div></div></section>`;
  return h;
}

// ---- sheet open / close ----
const sheet = document.getElementById('sheet');
const sheetBody = document.getElementById('sheetBody');
function openSheet(id){
  const d = RAW.find(x => x.id===id); if (!d) return;
  activeId = id;
  sheetBody.innerHTML = sheetHTML(d);
  sheetBody.scrollTop = 0;
  sheet.classList.add('open');
  document.body.classList.add('no-scroll');
  if (decodeURIComponent((location.hash||'').replace(/^#/,'')) !== id) location.hash = encodeURIComponent(id);
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
  const it = e.target.closest('.dt-item'); if (it) openSheet(it.dataset.id);
});
document.getElementById('list').addEventListener('keydown', e => {
  const head = e.target.closest('.sec-head');
  if (head && (e.key === 'Enter' || e.key === ' ')){ e.preventDefault(); toggleSection(head.dataset.sec); return; }
  if (e.key === 'Enter'){ const it = e.target.closest('.dt-item'); if (it){ e.preventDefault(); openSheet(it.dataset.id); } }
});
sheet.addEventListener('click', e => {
  if (e.target === sheet || e.target.closest('.sheet-close')){ closeSheet(); return; }
  const fh = e.target.closest('.fold-head');
  if (fh){ const s = fh.parentElement; const open = s.dataset.open==='1';
    s.dataset.open = open?'0':'1'; fh.querySelector('.caret').textContent = open?'▸':'▾'; return; }
  const badge = e.target.closest('[data-open-fold]');
  if (badge){ const s = sheet.querySelector('.fold[data-fold="'+badge.dataset.openFold+'"]');
    if (s){ s.dataset.open='1'; const c = s.querySelector('.caret'); if (c) c.textContent='▾'; s.scrollIntoView({block:'nearest'}); } return; }
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
    else if (opt.hasAttribute('data-area')) areaFilter = opt.dataset.area;
    else if (opt.hasAttribute('data-cat')){ const c = opt.dataset.cat; catFilter.has(c) ? catFilter.delete(c) : catFilter.add(c); }
    buildList();  // re-renders the drawer (renderFilters) so checks/badge update; stays open
    return;
  }
  if (e.target.closest('#clearFilters')){ openOnly = false; areaFilter = ''; catFilter.clear(); buildList(); }
});
document.getElementById('sort').addEventListener('click', e => {
  const b = e.target.closest('.tab'); if (!b) return;
  sortMode = b.dataset.sort;
  document.querySelectorAll('#sort .tab').forEach(x => x.classList.toggle('active', x===b));
  buildList();
});
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
  return { project: proj.project || 'Decisions', axis: proj.secondaryAxis || '', icon: proj.icon || '', decisions, expected: names.length };
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
  if (AXIS){  // second-dimension grouping ("By <label>") when the project defines one (d26)
    const b = document.createElement('button');
    b.className = 'tab'; b.dataset.sort = 'area'; b.textContent = 'By ' + AXIS;
    document.getElementById('sort').appendChild(b);
  }
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
'''


REDIRECT_HTML = '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=index.html">
<title>Decision Explorer</title></head>
<body><a href="index.html">Open the decision explorer &rarr;</a></body></html>
'''


def load_decisions(ddir):
    """Read _project.json + every NNNN-*.json decision file under ddir, ordered by the numeric
    prefix. Files may sit at the root (unversioned) OR in a per-version sub-folder (e.g. v1.0/),
    which the viewer groups by the decision's own `version` field, not the folder (d10/d36); the
    folder just mirrors the field for browsing. The manifest stores each file's path RELATIVE to
    ddir so the viewer can fetch it. Project-level metadata lives in decisions/_project.json.
    Files that don't match the NNNN-*.json pattern (e.g. a legacy backup) are ignored."""
    project = "Decisions"
    axis = ""
    pj = os.path.join(ddir, "_project.json")
    if os.path.exists(pj):
        with open(pj, "r", encoding="utf-8") as f:
            meta = json.load(f)
        project = meta.get("project", project)
        axis = meta.get("secondaryAxis", "") or ""
    numbered = []
    for root, _dirs, fns in os.walk(ddir):
        for fn in fns:
            m = re.match(r"^(\d+)-.*\.json$", fn)
            if m:
                rel = os.path.relpath(os.path.join(root, fn), ddir).replace(os.sep, "/")
                numbered.append((int(m.group(1)), rel))
    numbered.sort()
    files = [rel for _, rel in numbered]
    decisions = []
    for rel in files:
        with open(os.path.join(ddir, rel), "r", encoding="utf-8") as f:
            decisions.append(json.load(f))
    return project, axis, decisions, files


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "decisions"
    # Accept either the decisions directory or a legacy .json path (use its folder).
    ddir = (os.path.dirname(arg) or ".") if arg.endswith(".json") else arg
    # Second arg kept for back-compat (used to be the graph.html path); take its DIRECTORY.
    outdir = ddir
    if len(sys.argv) > 2:
        outdir = os.path.dirname(sys.argv[2]) or "."

    project, axis, decisions, files = load_decisions(ddir)
    os.makedirs(outdir, exist_ok=True)

    # 1. manifest.json — ALWAYS regenerated: just the ordered list of decision filenames.
    #    The viewer fetches this, then reads each decision's JSON file directly at runtime
    #    (d28 revised). Decision content is not copied anywhere — edit a JSON and refresh;
    #    only adding/removing a file changes this manifest.
    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(files, f)
    # Remove a stale data.js from the previous (baked-in) approach, if present.
    stale = os.path.join(outdir, "data.js")
    if os.path.exists(stale):
        os.remove(stale)

    # 2. Viewer assets — ONE SHARED viewer (d28 revised again): every project links to a single
    #    canonical copy in the skill, so updating the template once shows up in every project with
    #    no per-project copying. Only the decision DATA (the JSON files + _project.json + icon) is
    #    local to a project. Each run self-heals the links, so new projects and moved/broken links
    #    just work on the next regenerate. CANON_DIR is an absolute path so it's the same no matter
    #    which copy of this script runs.
    CANON_DIR = os.path.expanduser("~/.claude/skills/decision-tree/viewer")
    os.makedirs(CANON_DIR, exist_ok=True)
    assets = [("styles.css", STYLES_CSS), ("app.js", APP_JS), ("index.html", INDEX_HTML)]
    seeded, linked, kept = [], [], []
    for name, content in assets:
        canon = os.path.join(CANON_DIR, name)
        if not os.path.exists(canon):          # seed the canonical viewer once from the bundled template
            with open(canon, "w", encoding="utf-8") as f:
                f.write(content)
            seeded.append(name)
        link = os.path.join(outdir, name)
        if os.path.abspath(link) == os.path.abspath(canon):
            kept.append(name)                  # generating the skill's own canonical folder; nothing to link
            continue
        want = os.path.realpath(canon)
        have = os.path.realpath(link) if os.path.lexists(link) else None
        if have == want and os.path.islink(link):
            kept.append(name)                  # already a correct symlink
        else:
            if os.path.lexists(link):
                os.remove(link)                # replace a real file, wrong target, or broken link
            os.symlink(canon, link)
            linked.append(name)

    # 3. graph.html — a redirect to index.html so old links / the Stop hook keep working.
    with open(os.path.join(outdir, "graph.html"), "w", encoding="utf-8") as f:
        f.write(REDIRECT_HTML)

    phase_order = ["Requirements", "Design", "Implementation", "Testing", "Deployment", "Maintenance"]
    present = {d.get("phase", "Unphased") for d in decisions}
    phases = [p for p in phase_order if p in present] + sorted(p for p in present if p not in phase_order)
    note = ""
    if seeded:
        note += f"; seeded canonical viewer {', '.join(seeded)}"
    if linked:
        note += f"; linked {', '.join(linked)} to the shared viewer"
    if kept:
        note += f"; viewer already linked ({', '.join(kept)})"
    print(f"Wrote {os.path.join(outdir, 'manifest.json')} ({len(decisions)} decision(s); "
          f"phases: {', '.join(phases)}){note} — serve the folder (python3 -m http.server) then open index.html")


if __name__ == "__main__":
    main()
