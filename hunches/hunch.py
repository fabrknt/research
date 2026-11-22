#!/usr/bin/env python3
"""Sealed hunches: write a hunch privately, publish only its hash, open it when it is due.

usage:
  hunch.py new                       write a blank hunch in the private folder and print its path
  hunch.py seal ID                   hash the private file and add it to sealed.csv
  hunch.py open ID hit|miss|void [NOTE]
                                     check the private file against its hash, publish it, record the verdict
  hunch.py due [--date YYYY-MM-DD]   list sealed hunches that are due and not opened (exit 0)
  hunch.py stats                     counts, hit rate, Brier score of the stated confidence
  hunch.py verify                    check the chain of sealed.csv and every opened hunch against it

The private folder is $HUNCH_DIR, default ~/.config/fabrknt/hunches (never in this repo).
A sealed file must not change: one changed byte and `open` refuses it. Each row of sealed.csv carries the
hash of the file above it (`prev`), so a row removed or edited later breaks every row after it. A hunch
that can no longer be judged is opened as `void`, never left sealed; `stats` also scores voids as misses.
"""
import csv
import datetime as dt
import hashlib
import os
import re
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEALED = HERE / "sealed.csv"
RESULTS = HERE / "results.csv"
OPENED = HERE / "opened"
STAMPS = HERE / "stamps"
PRIVATE = Path(os.environ.get("HUNCH_DIR", Path.home() / ".config" / "fabrknt" / "hunches"))

SEALED_COLS = ["id", "sealed_at", "due", "sha256", "prev"]
RESULT_COLS = ["id", "opened_at", "verdict", "confidence", "note"]
VERDICTS = ("hit", "miss", "void")
ID_RE = re.compile(r"^H-\d{4}$")

TEMPLATE = """id: {id}
written: {today}
due: YYYY-MM-DD
confidence: NN
nonce: {nonce}

## What I sense


## Why now


## Hit if


## Miss if

"""


def now_utc():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv(path, cols):
    if not path.exists():
        return []
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and list(rows[0].keys()) != cols:
        sys.exit(f"{path.name}: unexpected columns {list(rows[0].keys())}")
    return rows


def append_csv(path, cols, row):
    new = not path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow(row)


def fields(text):
    out = {}
    for line in text.splitlines():
        if line.startswith("## "):
            break
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def check_id(hid):
    if not ID_RE.match(hid):
        sys.exit(f"bad id {hid!r}: want H-0001")
    return hid


def private_path(hid):
    return PRIVATE / f"{hid}.md"


def cmd_new():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE, 0o700)
    used = {r["id"] for r in read_csv(SEALED, SEALED_COLS)} | {p.stem for p in PRIVATE.glob("H-*.md")}
    n = 1
    while f"H-{n:04d}" in used:
        n += 1
    hid = f"H-{n:04d}"
    p = private_path(hid)
    # The nonce keeps a short hunch from being guessed by hashing candidate texts. "x" never overwrites.
    with open(p, "x") as f:
        f.write(TEMPLATE.format(id=hid, today=dt.date.today().isoformat(), nonce=secrets.token_hex(16)))
    os.chmod(p, 0o600)
    print(p)


def cmd_seal(hid):
    check_id(hid)
    if any(r["id"] == hid for r in read_csv(SEALED, SEALED_COLS)):
        sys.exit(f"{hid} is already sealed")
    p = private_path(hid)
    if not p.exists():
        sys.exit(f"no private file {p}")
    data = p.read_bytes()
    f = fields(data.decode())
    if f.get("id") != hid:
        sys.exit(f"{p.name}: id line says {f.get('id')!r}")
    try:
        due = dt.date.fromisoformat(f.get("due", ""))
    except ValueError:
        sys.exit(f"{p.name}: due must be YYYY-MM-DD")
    if due <= dt.date.today():
        sys.exit(f"{p.name}: due {due} is not in the future")
    try:
        conf = int(f.get("confidence", ""))
    except ValueError:
        sys.exit(f"{p.name}: confidence must be a whole percent")
    if not 1 <= conf <= 99:
        sys.exit(f"{p.name}: confidence must be 1-99")
    if len(f.get("nonce", "")) < 32:
        sys.exit(f"{p.name}: nonce missing (write the file with `new`)")
    body = data.decode().split("## Hit if", 1)
    if len(body) != 2 or not body[1].split("## Miss if", 1)[0].strip():
        sys.exit(f"{p.name}: 'Hit if' is empty; a hunch with no test can't be opened as hit or miss")
    os.chmod(p, 0o400)
    digest = hashlib.sha256(data).hexdigest()
    prev = hashlib.sha256(SEALED.read_bytes() if SEALED.exists() else b"").hexdigest()
    append_csv(SEALED, SEALED_COLS,
               {"id": hid, "sealed_at": now_utc(), "due": due.isoformat(), "sha256": digest, "prev": prev})
    print(f"{hid} sealed, due {due}, sha256 {digest}")
    print("commit and push hunches/sealed.csv today; the workflow stamps it on Bitcoin")


def cmd_open(hid, verdict, note):
    check_id(hid)
    if verdict not in VERDICTS:
        sys.exit(f"verdict must be one of {VERDICTS}")
    sealed = {r["id"]: r for r in read_csv(SEALED, SEALED_COLS)}
    if hid not in sealed:
        sys.exit(f"{hid} was never sealed")
    if any(r["id"] == hid for r in read_csv(RESULTS, RESULT_COLS)):
        sys.exit(f"{hid} is already opened")
    p = private_path(hid)
    data = p.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sealed[hid]["sha256"]:
        sys.exit(f"{p.name} does not match its seal ({digest} != {sealed[hid]['sha256']}); it was changed")
    OPENED.mkdir(exist_ok=True)
    (OPENED / f"{hid}.md").write_bytes(data)  # the bytes just checked, not a second read
    conf = fields(data.decode())["confidence"]
    append_csv(RESULTS, RESULT_COLS,
               {"id": hid, "opened_at": now_utc(), "verdict": verdict, "confidence": conf, "note": note})
    print(f"{hid} opened as {verdict}; commit hunches/opened/{hid}.md and hunches/results.csv")


def due_rows(on):
    opened = {r["id"] for r in read_csv(RESULTS, RESULT_COLS)}
    return [r for r in read_csv(SEALED, SEALED_COLS)
            if r["id"] not in opened and dt.date.fromisoformat(r["due"]) <= on]


def cmd_due(args):
    on = dt.date.today()
    if args[:1] == ["--date"] and len(args) == 2:
        on = dt.date.fromisoformat(args[1])
    for r in due_rows(on):
        print(f"{r['id']}\t{r['due']}")


def cmd_stats():
    verify(quiet=True)
    sealed = read_csv(SEALED, SEALED_COLS)
    res = read_csv(RESULTS, RESULT_COLS)
    judged = [r for r in res if r["verdict"] in ("hit", "miss")]
    hits = sum(r["verdict"] == "hit" for r in judged)
    void = sum(r["verdict"] == "void" for r in res)
    print(f"sealed {len(sealed)}  opened {len(res)}  still sealed {len(sealed) - len(res)}")
    print(f"hit {hits}  miss {len(judged) - hits}  void {void}")
    if judged:
        brier = sum((int(r["confidence"]) / 100 - (r["verdict"] == "hit")) ** 2 for r in judged) / len(judged)
        mean_conf = sum(int(r["confidence"]) for r in judged) / len(judged)
        print(f"hit rate {hits / len(judged):.0%}  mean stated confidence {mean_conf:.0f}%  "
              f"Brier {brier:.3f} (0.25 = always saying 50%)")
    if void:
        opened = [r for r in res]
        brier_v = sum((int(r["confidence"]) / 100 - (r["verdict"] == "hit")) ** 2 for r in opened) / len(opened)
        print(f"with each void counted as a miss: hit rate {hits / len(opened):.0%}  Brier {brier_v:.3f}")


def verify(quiet=False):
    """Fail loudly unless sealed.csv is an unbroken chain and every result matches an opened, sealed file."""
    bad = []
    raw = SEALED.read_bytes() if SEALED.exists() else b""
    lines = raw.splitlines(keepends=True)
    sealed = read_csv(SEALED, SEALED_COLS)
    if len(sealed) != max(len(lines) - 1, 0):
        bad.append("sealed.csv: a row spans lines or a line is blank")
    seen = set()
    for i, r in enumerate(sealed, start=1):
        if r["prev"] != hashlib.sha256(b"".join(lines[:i])).hexdigest():
            bad.append(f"{r['id']}: prev does not match the file above it (a row was edited or removed)")
        if r["id"] in seen or not ID_RE.match(r["id"]):
            bad.append(f"{r['id']}: duplicate or malformed id")
        seen.add(r["id"])
    by_id = {r["id"]: r for r in sealed}
    results = read_csv(RESULTS, RESULT_COLS)
    if len({r["id"] for r in results}) != len(results):
        bad.append("results.csv: an id is opened twice")
    for r in results:
        s = by_id.get(r["id"])
        f = OPENED / f"{r['id']}.md"
        if s is None:
            bad.append(f"{r['id']}: in results.csv but never sealed")
            continue
        if r["verdict"] not in VERDICTS:
            bad.append(f"{r['id']}: verdict {r['verdict']!r}")
        if not f.exists():
            bad.append(f"{r['id']}: no opened/{f.name}")
            continue
        data = f.read_bytes()
        if hashlib.sha256(data).hexdigest() != s["sha256"]:
            bad.append(f"{r['id']}: opened file does not match its seal")
        if fields(data.decode()).get("confidence") != r["confidence"]:
            bad.append(f"{r['id']}: confidence in results.csv differs from the opened file")
    opened_ids = {r["id"] for r in results}
    for f in OPENED.glob("H-*.md") if OPENED.exists() else []:
        if f.stem not in opened_ids:
            bad.append(f"{f.name}: published but not in results.csv")
    if bad:
        sys.exit("verify failed:\n  " + "\n  ".join(bad))
    if not quiet:
        print(f"ok: {len(sealed)} sealed, chain unbroken; {len(results)} opened, each matches its seal")


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, rest = argv[0], argv[1:]
    if cmd == "new" and not rest:
        cmd_new()
    elif cmd == "seal" and len(rest) == 1:
        cmd_seal(rest[0])
    elif cmd == "open" and len(rest) in (2, 3):
        cmd_open(rest[0], rest[1], rest[2] if len(rest) == 3 else "")
    elif cmd == "due":
        cmd_due(rest)
    elif cmd == "stats" and not rest:
        cmd_stats()
    elif cmd == "verify" and not rest:
        verify()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
