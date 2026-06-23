#!/usr/bin/env python3
"""Re-embed the canonical viewer into generate.py so a clean-environment build ships the latest.

Why this exists: generate.py carries the viewer (index.html / styles.css / app.js) as embedded
string literals — that embedded copy is the SEED used when no canonical viewer exists, e.g. on a
clean CI box like Netlify. Locally the canonical files (the symlink targets in
~/.claude/skills/decision-tree/viewer/) are the source of truth and the embedded seed is ignored,
so it silently drifts. When it drifts, the next clean build publishes a STALE viewer with no error.

Run this whenever you've edited the viewer and before you push a deploy:

    python3 skill/sync-viewer.py            # re-embed, report what changed
    python3 skill/sync-viewer.py --check    # exit 1 if out of sync (for a pre-push/CI guard), write nothing

It rewrites the generate.py sitting next to this script, then keeps the installed skill copy at
~/.claude/skills/decision-tree/generate.py in sync if present.
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GENERATE_PY = os.path.join(HERE, "generate.py")
CANON_DIR = os.path.expanduser("~/.claude/skills/decision-tree/viewer")
INSTALLED_GENERATE_PY = os.path.expanduser("~/.claude/skills/decision-tree/generate.py")

# (literal name in generate.py, canonical filename)
TARGETS = [("STYLES_CSS", "styles.css"), ("INDEX_HTML", "index.html"), ("APP_JS", "app.js")]


def reembed(src):
    """Return (new_src, changes). Each literal is matched as  NAME = r'''...'''  and its body
    replaced with the canonical file's content. changes is a list of (name, old_len, new_len)."""
    changes = []
    for var, fname in TARGETS:
        path = os.path.join(CANON_DIR, fname)
        if not os.path.exists(path):
            sys.exit(f"error: canonical viewer file missing: {path}")
        content = open(path, encoding="utf-8").read()
        if "'''" in content:
            sys.exit(f"error: {fname} contains ''' — cannot embed in a raw triple-quoted string")
        pat = re.compile(r"(" + var + r"\s*=\s*r''')(.*?)(''')", re.DOTALL)
        m = pat.search(src)
        if not m:
            sys.exit(f"error: could not locate the {var} literal in generate.py")
        if m.group(2) != content:
            changes.append((var, len(m.group(2)), len(content)))
        src = src[:m.start(2)] + content + src[m.end(2):]
    return src, changes


def main():
    check_only = "--check" in sys.argv[1:]

    if not os.path.exists(GENERATE_PY):
        sys.exit(f"error: not found: {GENERATE_PY}")
    original = open(GENERATE_PY, encoding="utf-8").read()
    updated, changes = reembed(original)

    if not changes:
        print("Embedded viewer already matches the canonical viewer — nothing to do.")
        return

    if check_only:
        for var, old, new in changes:
            print(f"OUT OF SYNC: {var} embedded={old} canonical={new}")
        print("\nRun `python3 skill/sync-viewer.py` to re-embed, then commit generate.py.")
        sys.exit(1)

    ast.parse(updated)  # never write a file that won't import
    open(GENERATE_PY, "w", encoding="utf-8").write(updated)
    for var, old, new in changes:
        print(f"re-embedded {var}: {old} -> {new} chars")
    print(f"wrote {GENERATE_PY}")

    # Keep the installed skill copy identical so local regenerates and shared copies don't diverge.
    if os.path.exists(INSTALLED_GENERATE_PY) and os.path.abspath(INSTALLED_GENERATE_PY) != os.path.abspath(GENERATE_PY):
        open(INSTALLED_GENERATE_PY, "w", encoding="utf-8").write(updated)
        print(f"synced {INSTALLED_GENERATE_PY}")

    print("\nNext: commit generate.py and push so the deploy rebuilds with the latest viewer.")


if __name__ == "__main__":
    main()
