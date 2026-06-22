# Consulting the decision log before a new feature

Use this when planning a new feature or change in a project that already has a decision log
(`decisions/NNNN-*.json`). Goal: weigh the feature against past decisions and brief the user on
where it fits and what it touches — **before** any new decision is made. This flow is **advisory and
writes nothing**; a decision is captured only later, through `add`, if the user decides to build it.

## Contents
- When to run
- Workflow (read → weigh → place → brief)
- Briefing format
- Handing off to capture

## When to run
- The user names it: "plan a feature", "how would X fit", "what decisions affect X".
- Proactively: any feature or change request that touches an area with existing decisions — consult
  the log first, then answer.

## Workflow

Copy this checklist and work through it:

```
Consult progress:
- [ ] 1. Find the related decisions
- [ ] 2. Weigh them
- [ ] 3. Place the feature
- [ ] 4. Brief the user (write nothing)
```

**1. Find the related decisions**
- If `_project.json` sets a `secondaryAxis` (e.g. Screen) and the feature targets one value, start by
  pulling the decisions with that `area`, then widen to anything they depend on.
- Small log (under ~150 decisions): read every `decisions/NNNN-*.json` and judge relevance yourself —
  your judgment catches connections a keyword search misses (e.g. a decision that conflicts but shares
  no words).
- Large log: seed by matching the feature's terms against each decision's title, question, option
  labels, and category; then expand along `dependsOn` (and the decisions that depend on those) to pull
  the whole affected cluster, not isolated hits.

**2. Weigh them**
For each related decision, note: the chosen option and why, the tradeoff **criteria** that bear on this
feature (reuse those exact criterion strings if it gets captured later), and how the feature relates —
reinforces it, depends on it, conflicts with it, or would supersede it.

**3. Place the feature**
Work out where it belongs: the SDLC **phase**, a **category** (reuse an existing one when it fits), the
decisions it **dependsOn**, and any it conflicts with or supersedes. Relationships are expressed
**informally** — `dependsOn` plus a plain note — never a new relation type.

**4. Brief the user — write nothing**
Produce the briefing below. Do not create or edit any decision file at this step.

## Briefing format
Keep it **lean** — this is a scan, not a memo. Four sections, every entry **one line**, no
paragraphs. Cap each list at the 2–3 bullets that actually matter; drop a section entirely if it's
empty (don't write "none" filler). Lead each related/constraint bullet with the id or criterion so
the eye lands on it. Total briefing should fit on a screen without scrolling.

```markdown
**Related**
- <id> <title> — chosen: <option> · matters here: <≤6 words>

**Constraints**
- <criterion> — <≤8 words on what it implies>

**Where it fits**
<Phase> · <Category> · deps <ids> · conflicts <id> (or omit the conflict clause)

**Call**
<1 sentence: build it or not + the single thing to watch.>
```

Skip the **Constraints** section when nothing material bears on the feature; never pad a section to
look complete. Prose around the block (extra caveats, alternatives) belongs *after* it, not inside.

## Handing off to capture
If the user then decides to build it, capture it with `add` (confirm-at-the-moment): draft the new
decision, wire `dependsOn`, and record any supersede/conflict relationship as a plain note in the
`rationale` (e.g. "replaces the approach in <id>"). Then regenerate the viewer. Until the user
decides, nothing is written.
