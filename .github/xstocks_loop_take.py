"""Checks what a turn of the xStocks loop handed over and copies it into loop/ (xstocks-loop.yml, commit job).

usage: python3 -I .github/xstocks_loop_take.py IN_DIR LOOP_DIR

IN_DIR holds the turn's new and changed files at their repo paths. Taken only when every one is a regular
text file under LOOP_DIR named experiments/<name>.md, findings.md or <name>.py (never README.md, prompt.md
or table.py), each at most 200 kB, at most 20 and 1 MB in all. Anything else fails the job and nothing is
copied. Nothing handed over is run.
"""

import os
import re
import shutil
import sys

OK = re.compile(r"experiments/[A-Za-z0-9][A-Za-z0-9_.-]{0,60}\.md|findings\.md|[a-z][a-z0-9_]{0,40}\.py")
FIXED = {"README.md", "prompt.md", "table.py"}


def main(src: str, loop: str) -> None:
    root = os.path.join(src, loop)
    if not os.path.isdir(src):
        print("the turn handed over nothing")
        return
    files, total = [], 0
    for d, dirs, names in os.walk(src, followlinks=False):
        for n in dirs + names:
            p = os.path.join(d, n)
            if os.path.islink(p):
                sys.exit(f"link: {p}")
        for n in names:
            p = os.path.join(d, n)
            if not p.startswith(root + os.sep):
                sys.exit(f"outside {loop}: {p}")
            rel = os.path.relpath(p, root)
            size = os.lstat(p).st_size
            if not os.path.isfile(p) or size > 200_000 or not OK.fullmatch(rel) or rel in FIXED:
                sys.exit(f"not allowed: {rel} ({size} bytes)")
            with open(p, encoding="utf-8") as f:
                f.read()  # text only
            files.append(rel)
            total += size
    if len(files) > 20 or total > 1_000_000:
        sys.exit(f"too much: {len(files)} files, {total} bytes")
    for rel in files:
        dst = os.path.join(loop, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(root, rel), dst)
        print("take", rel)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
