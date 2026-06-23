---
name: decide
description: Shorthand alias for the decision-tree skill (Decision Explorer AI). Log decisions and their tradeoffs, render the interactive decision-explorer viewer, and consult past decisions before planning a feature. Use when the user types /decide or wants to capture, revise, view, list, audit, or plan against decisions. Triggered by /decide or /decision-tree or phrases like "log this decision", "add a decision", "show the decision tree/graph", "plan a feature".
---

# /decide — alias of decision-tree

This skill is a **shorthand alias** for the `decision-tree` skill, kept so the command
is easy to type (no need to spell "decision"). It holds **no logic of its own** — the
single source of truth is the full skill at `~/.claude/skills/decision-tree/SKILL.md`.

**Do this:** Read `~/.claude/skills/decision-tree/SKILL.md` and follow it exactly.
Treat `/decide <subcommand>` as identical to `/decision-tree <subcommand>` — same
subcommands (`add`, `revise`, `plan`, `view`, `list`, `audit`), same flows, same files,
same generator. The two names are interchangeable.
