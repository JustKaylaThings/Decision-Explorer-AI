---
name: decision-tree
description: Log decisions and their tradeoffs explicitly, render them as an interactive decision-explorer HTML viewer, and consult past decisions before planning a new feature. Use when the user wants to capture a decision (with options + tradeoffs), revise a past decision, view the decision graph, weigh a new feature against existing decisions, or back-fill a decision log for an existing codebase. Triggered by /decision-tree or phrases like "log this decision", "add a decision", "show the decision tree/graph", "plan a feature", "how does this fit", "what decisions affect X", "audit this codebase", "back-fill decisions".
---

# Decision Explorer

Capture decisions — with their options and per-option tradeoffs — and render an interactive
**decision explorer** (master–detail drawer): a calm, searchable left list of one-line decisions
grouped by SDLC phase, and a right panel that shows the chosen option, why, the full
options × tradeoffs comparison, revision history, and dependency links for ONE decision at a time.

## Files (per project)

Source of truth is **one file per decision** in `decisions/`:

- `decisions/_project.json` — project-level metadata: `{ "project": "<dir name>" }`. Optional
  `"secondaryAxis": "<label>"` (e.g. `"Screen"`) turns on a second grouping dimension: decisions may
  then carry an `area` value, and the viewer gains a "By &lt;label&gt;" grouping mode plus filter chips.
  Leave it unset for projects without such a dimension (the field then stays invisible).
- `decisions/NNNN-slug.json` — one decision per file (see schema below). `NNNN` is the
  zero-padded decision number (matches the `id`, e.g. `d7` → `0007-…`) and orders the files
  chronologically on disk; `slug` is a kebab-case of the title.
- `decisions/graph.html` — generated viewer (never hand-edit; auto-regenerated — see Rendering)
- Generator: `.claude/skills/decision-tree/generate.py`

If `decisions/` has no `_project.json`, create it: `{ "project": "<dir name>" }`. The generator
globs `NNNN-*.json` for decisions, so an empty project is just `_project.json` with no decision files.

## Subcommands

The argument after `/decision-tree` selects the action. With no argument, infer intent.

### `add` — log a new decision
1. Gather, asking only for what's missing (write every field to be **scanned**, not read — see Writing style):
   - **title** — the scannable unit; name the everyday topic in plain words a non-technical person
     understands (e.g. "Daily reminders", not "Engagement mechanics") — see Writing style
   - **phase** — the SDLC stage the decision was made in. One of: `Requirements`, `Design`,
     `Implementation`, `Testing`, `Deployment`, `Maintenance`. This is the PRIMARY grouping in the
     viewer (the "framework"). If genuinely unclear, omit (it falls under "Unphased").
   - **category** — the topic/area it files under (e.g. "Architecture", "Frontend", "Process").
     Reuse an existing category string when it fits; shown as a secondary tag within a phase.
   - **date** — when the decision was made, ISO 8601 with time to the second: `YYYY-MM-DDThh:mm:ss`
     (drop the time only if the user is back-logging an older decision and the time is unknown).
     Stamp it automatically at capture — get the real local time by running `date "+%Y-%m-%dT%H:%M:%S"`
     rather than guessing, since session context usually carries only the date. Don't ask the user
     unless they're logging a decision made earlier. Drives the viewer's "Recent" sort.
   - **type**: `technical` or `general` (drives the suggested tradeoff axes — see Templates)
   - **question** the decision answers
   - **options** (2+), each with a label and its **tradeoffs**: `{criterion, sentiment, note}`
     where sentiment is `+` (pro), `-` (con), or `~` (mixed/neutral)
   - which option is **chosen** (set `chosen: true`; omit/false if still open → set decision `status: "open"`)
   - **rationale** for the choice
   - optional **dependsOn**: ids of earlier decisions this one follows from
   - optional **area** — the value on the project's second dimension, only if `_project.json` sets
     `secondaryAxis` (e.g. the screen a decision belongs to). Reuse existing values verbatim.
2. Write a new file `decisions/NNNN-slug.json` containing the decision object, with a fresh
   `id` (`d<N>`, where `N` is the next number) and matching `NNNN` (zero-padded `N`); option ids
   `o<N><a..>`. `slug` is the kebab-case title. The file holds the single decision object (the
   schema below), not an array.
3. **Reuse tradeoff criterion wording verbatim** across decisions when it's the same axis
   (e.g. always "ops cost", not "operational cost" once and "ops burden" later) — identical
   strings become one shared node, which is the whole point of the graph.
4. Regenerate the viewer (see Rendering).

### `revise <id>` — change a past decision
- Open that decision's file (`decisions/NNNN-*.json`, where `NNNN` matches the `id`). Move the old
  chosen option's choice into the decision's `history` array
  (`{ "from": "<old option label>", "reason": "<why changed>", "date": "<YYYY-MM-DDThh:mm:ss>" }`),
  stamping the revision time from `date "+%Y-%m-%dT%H:%M:%S"`; then set the new `chosen`.
- Update `rationale`. Keep both options as nodes so the graph shows what was reconsidered.
- If the title changed materially you may rename the file's `slug` (keep the `NNNN` prefix). Regenerate.

### `audit <path>` — back-fill decisions for an existing codebase
For an app that was built **without** a decision log, reconstruct the load-bearing decisions by
mining the code and git history, then interviewing the user to fill the *why* — the
confirm-at-the-moment model run in reverse (discover, then confirm). **Writes nothing until the
user approves the drafts.** Scoped to load-bearing choices only (language, framework, data store,
auth, deployment, key libs), never every detectable pick. Run the discover → filter → draft →
interview → confirm workflow in **[auditing.md](auditing.md)**. `<path>` defaults to the project
root; if it has no `decisions/`, create the folder and `_project.json` first. If a log already
exists, only gap-fill — never duplicate a logged decision.

### `plan` — consult the log before a new feature
Before deciding a new feature or change, weigh it against the existing decisions, then brief the
user — **do not write anything**. Run the read → weigh → place → brief workflow in
**[consulting.md](consulting.md)**.

**Proactive:** even when the user doesn't say `plan`, if a feature or change request touches an area
that already has decisions, consult the log first and surface what's relevant. The briefing is
advisory; capture a new decision via `add` only if the user then actually decides to build it.

### `view` — (re)generate and open
- Regenerate, then tell the user the path to `decisions/graph.html` so they can open it in a browser.

### `list` — summarize
- Read the decision files (`decisions/NNNN-*.json`) and print a compact list: id · title · chosen option · status.

## Writing style — plain and scannable

Every string is read in a dense list or a calm panel by someone who may **not be technical**. Write so
a non-technical reader can scan the list and know what each decision is about, then open one and
understand what was chosen and why — *without knowing the tools involved*. Be concrete, drop filler,
and never leave jargon unexplained.

- **title** — the only thing visible in the list. Name the **everyday topic in plain words**, not the
  technical answer. Lead with the noun, ~2–6 words, no trailing period, distinguishable next to 30
  others. The precise tool (TypeScript, SQLite, expo-router) belongs in the option/rationale, not the title.
  - ❌ "Engagement mechanics" / "Reminders only (local notification)" → ✅ "Daily reminders"
  - ❌ "StyleSheet + custom components" → ✅ "How the app is styled"
  - ❌ "SQLite/Expo storage defaults" → ✅ "Where data is stored on the device"
  - ❌ "Primary-key strategy" → ✅ "How entries are identified"
- **option label** — the choice in plain terms; keep the precise tool in parentheses when it helps
  (e.g. "On the device only (SQLite)"). Short and parallel so the set compares at a glance.
- **rationale** — 1–2 sentences a non-technical person can follow: what was chosen and the deciding
  reason. The first time a technical term appears, add a half-line of plain explanation (e.g.
  "TypeScript — a stricter form of JavaScript that catches mistakes early"). Cut "we decided to…".
- **tradeoff criterion** — 1–3 plain words for the axis ("setup effort", "long-term cost",
  "lock-in → hard to switch later"); reuse wording verbatim across decisions (see step 3).
  **note** — a short plain clause, not a paragraph.
- **question** — one plain sentence ending in `?`; the decision it answers, not background.

When the user hands you a vague OR jargon-heavy title, propose a plain rewrite in the draft rather than
logging it as-is.

## Capture model: confirm at the moment

The primary way decisions enter the log is **draft-and-confirm at the point of decision** — NOT
a retroactive sweep (that would require trusting AI recall). Whenever a decision is reached in
conversation (especially via an options choice the user picks), proactively **draft it (title,
category, options, tradeoffs, chosen, rationale) and have the user confirm or edit before
writing**. Then `add`/`revise` and regenerate. Structured option-pickers ARE decisions — capture
them there.

**Backstop:** a `Stop` hook (`.claude/hooks/reconcile-decisions.py`, in `.claude/settings.json`,
throttled ~once/15 min per session) fires at turn end and asks you to check for any decision that
was made/changed but not yet logged-and-confirmed. If found, **propose it to the user for
approval — never write silently.** If all captured, say so briefly. (After creating settings.json
the user must open `/hooks` or restart for the hook to take effect.)

## Templates (decision `type`)

When adding, suggest tradeoff axes the user can accept or replace:
- **technical**: build effort, complexity, scalability, maintainability, cost, lock-in, performance
- **general**: cost, time, risk, reversibility, alignment-with-goal, effort

These are only prompts — the user defines the actual criteria. Keep wording consistent (step 3 above).

## Rendering

**Auto-regenerated (decision d8) — you rarely run this by hand.** The viewer rebuilds two ways:
  - `add` / `revise` / `view` regenerate as their last step (the skill, side A).
  - The `Stop` hook regenerates `graph.html` whenever a decision file changed (side B), so even a
    manual edit is picked up at turn end.

To regenerate explicitly, run from the project root:

```
python3 .claude/skills/decision-tree/generate.py decisions decisions/graph.html
```

(The first argument is now the **decisions folder**, not a single JSON file. A legacy
`decisions/decisions.json` path still works — it's treated as "use that file's folder".)

Requires only Python 3 (no pip installs, no external libraries or fonts — works fully offline).
The output is a **decision explorer** (master–detail drawer), one screen, no tabs:
  - **Left list**: a calm, searchable column of one-line decisions filed under collapsible
    **SDLC-phase** sections in lifecycle order (Requirements → Design → Implementation → Testing →
    Deployment → Maintenance), each phase color-coded; **category** is a secondary tag. Each item
    shows its **date** when set; a **By phase / Recent** toggle switches between the phase-grouped
    framework view (default) and a flat newest-first list (undated decisions sink to the bottom).
    When `_project.json` sets `secondaryAxis`, a third "By &lt;label&gt;" grouping mode and a row of
    filter chips appear, so you can browse or narrow by that dimension (e.g. by screen).
  - **Right detail panel** (shows ONE selected decision at a time, to avoid wall-of-text overwhelm):
    the **chosen option and why first**, then the full **options × tradeoffs** comparison, the
    decided date, revision history (with a "revised" badge), and inline **Depends on / Affects** rows
    (click to jump to that decision). The whole-graph Map view was deliberately dropped (decisions
    d2 + d5): connections show as the detail panel's dependency rows, not a separate graph.

Report the output path; the user opens it in a browser.

## JSON schema (reference)

`decisions/_project.json`:

```json
{ "project": "string", "secondaryAxis": "string (optional, e.g. \"Screen\")" }
```

Each `decisions/NNNN-slug.json` is a single decision object (no wrapper array):

```json
    {
      "id": "d1",
      "title": "string",
      "phase": "Requirements | Design | Implementation | Testing | Deployment | Maintenance",
      "category": "string",
      "area": "string (optional; value on _project.json's secondaryAxis, e.g. a screen)",
      "date": "YYYY-MM-DDThh:mm:ss",
      "type": "technical | general",
      "question": "string",
      "status": "decided | open",
      "rationale": "string",
      "dependsOn": ["d0"],
      "history": [{ "from": "string", "reason": "string", "date": "YYYY-MM-DDThh:mm:ss" }],
      "options": [
        {
          "id": "o1a",
          "label": "string",
          "chosen": true,
          "note": "string",
          "tradeoffs": [
            { "criterion": "string", "sentiment": "+ | - | ~", "note": "string" }
          ]
        }
      ]
    }
```
