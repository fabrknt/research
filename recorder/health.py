"""Daily check that the recorder kept what it should have over the last 24 hours, from each hour's count.json
(unencrypted; it holds no data, so this runs on GitHub without the key). A source falls short when its
working calls are under 80% of what its interval allows (a daily source: none at all), or when the newest
hour is more than 2 hours old. Shortfalls go into one open issue, "recorder: gaps", as a comment.

    python3 -I recorder/health.py [--dry]
"""

import io
import json
import subprocess
import sys
import tarfile
import time
import tomllib
from pathlib import Path

REPO = "fabrknt/research"
HERE = Path(__file__).resolve().parent
TITLE = "recorder: gaps"
WINDOW = 86400


def gh(*args: str, binary: bool = False):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=not binary).stdout


def counts(since: float):
    out = []
    for tag in (time.strftime("recorder-%Y%m", time.gmtime(since)), time.strftime("recorder-%Y%m", time.gmtime())):
        try:
            assets = json.loads(gh("release", "view", tag, "-R", REPO, "--json", "assets"))["assets"]
        except subprocess.CalledProcessError:
            continue
        for a in assets:
            if a["name"].endswith(".tar") and a["createdAt"] >= time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(since)):
                tar = gh("release", "download", tag, "-R", REPO, "-p", a["name"], "-O", "-", binary=True)
                with tarfile.open(fileobj=io.BytesIO(tar)) as t:
                    out.append(json.load(t.extractfile("count.json")))
        if tag == time.strftime("recorder-%Y%m", time.gmtime()):
            break
    return {json.dumps(c, sort_keys=True): c for c in out}.values()  # same month twice -> once


def main(dry: bool) -> None:
    now = time.time()
    since = now - WINDOW
    hours = [c for c in counts(since - 3 * 3600) if c["end"] >= since]
    problems = []
    if not hours or max(c["end"] for c in hours) < now - 2 * 3600:
        last = max((c["end"] for c in hours), default=None)
        problems.append(f"no hour has finished since {time.strftime('%Y-%m-%d %H:%M', time.gmtime(last)) if last else 'before the window'} UTC")
    hours = sorted(hours, key=lambda c: c["end"])
    for s in tomllib.loads((HERE / "sources.toml").read_text())["source"]:
        mine = [c["sources"][s["name"]] for c in hours if s["name"] in c["sources"]]
        complete = sum(c.get("complete", 0) for c in mine)
        failed = sum(c.get("failed", 0) for c in mine)
        types: dict = {}
        for c in mine:
            for k, v in c.get("error_types", {}).items():
                types[k] = types.get(k, 0) + v
        want = max(1, int(0.8 * WINDOW / s["every"]))
        if complete < want:
            problems.append(f"{s['name']}: {complete} complete calls in 24 h (want {want}), {failed} failed {types}")
        status = next((c["status"] for c in reversed(mine) if c.get("status")), {})
        if status.get("behind_s", 0) > 3600:
            problems.append(f"{s['name']}: {status['behind_s'] / 3600:.1f} h behind")
        if status.get("failed_items"):
            problems.append(f"{s['name']}: {status['failed_items']} items failed after all tries")
    report = "\n".join(f"- {p}" for p in problems)
    print(report or f"all sources kept up ({len(hours)} hours)")
    if not problems or dry:
        return
    found = gh("issue", "list", "-R", REPO, "--state", "open", "--search", f'"{TITLE}" in:title', "--json", "number", "-q", ".[0].number").strip()
    body = f"{time.strftime('%Y-%m-%d', time.gmtime(now))}, last 24 hours:\n\n{report}"
    if found:
        gh("issue", "comment", found, "-R", REPO, "--body", body)
    else:
        gh("issue", "create", "-R", REPO, "--title", TITLE, "--body", body)


if __name__ == "__main__":
    main("--dry" in sys.argv)
