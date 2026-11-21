"""Daily check that the recorder kept what it should have over the last 24 hours, from each hour's count.json
(unencrypted; it holds no data, so this runs on GitHub without the key). A source falls short when its
working calls are under 80% of what its interval allows since it started, at most 24 hours (a daily source:
none at all; a source started under an hour ago: not judged), or when the newest
hour is more than 2 hours old. It also flags storage: all monthly releases over 20 GB (time to move older
months off GitHub) or this month's release near GitHub's 1,000-file limit. Shortfalls go into one open
issue, "recorder: gaps", as a comment.

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
MAX_TOTAL_GB = 20      # past this, move older months off GitHub (to S3 or similar)
MAX_MONTH_ASSETS = 900  # a release holds at most 1,000 files


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


def storage() -> list[str]:
    """Size of all recorder-YYYYMM releases and the file count of this month's, against the limits above."""
    tags = [t for t in gh("api", f"repos/{REPO}/releases", "--paginate", "-q", ".[].tag_name").split()
            if t.startswith("recorder-") and t[9:].isdigit()]
    total, this_month = 0, 0
    for tag in tags:
        assets = json.loads(gh("release", "view", tag, "-R", REPO, "--json", "assets"))["assets"]
        total += sum(a["size"] for a in assets)
        if tag == time.strftime("recorder-%Y%m", time.gmtime()):
            this_month = len(assets)
    out = []
    if total > MAX_TOTAL_GB * 1e9:
        out.append(f"storage: {total / 1e9:.1f} GB in {len(tags)} monthly releases, over {MAX_TOTAL_GB} GB: move older months off GitHub")
    if this_month > MAX_MONTH_ASSETS:
        out.append(f"storage: {this_month} files in this month's release, near the 1,000 limit")
    print(f"storage: {total / 1e9:.2f} GB in {len(tags)} monthly releases, {this_month} files this month")
    return out


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
        # a source that started within the window (a new one, or the recorder's first day) is held to the time
        # since its first hour, not the whole 24 h. count.json lists every source configured for that job, with
        # zeros if it never worked, so a stopped source is still judged; one in no hour at all is new, added
        # after the newest finished hour
        began = min((c["start"] for c in hours if s["name"] in c["sources"]), default=now)
        last = max((c["end"] for c in hours), default=now)  # the hour running now isn't in yet
        span = last - max(since, began)
        want = max(1, int(0.8 * span / s["every"])) if span >= 3600 else 0
        if complete < want:
            problems.append(f"{s['name']}: {complete} complete calls in 24 h (want {want}), {failed} failed {types}")
        status = next((c["status"] for c in reversed(mine) if c.get("status")), {})
        if status.get("behind_s", 0) > 3600:
            problems.append(f"{s['name']}: {status['behind_s'] / 3600:.1f} h behind")
        if status.get("failed_items"):
            problems.append(f"{s['name']}: {status['failed_items']} items failed after all tries")
    try:
        problems += storage()
    except Exception as e:  # don't let it hide the gaps found above
        problems.append(f"storage check failed: {type(e).__name__}")
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
