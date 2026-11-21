"""Read what the recorder kept: download the hours from the monthly releases (recorder-YYYYMM), decrypt them
with the private key (kept off GitHub) and print one source's rows as JSON lines.

    python3 -I recorder/read.py SOURCE [--from 2026-11-21] [--to 2026-11-22] [--key PEM] > rows.jsonl

Hours are cached under recorder/data/<run id>/ (git-ignored), so a second read downloads only new hours.
"""

import argparse
import gzip
import io
import json
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

REPO = "fabrknt/research"
HERE = Path(__file__).resolve().parent
CACHE = HERE / "data"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def hours(since: float, until: float):
    """(run id, count.json) of every hour that overlaps [since, until), downloading and decrypting as needed."""
    tags = [t for t in gh("release", "list", "-R", REPO, "-L", "200", "--json", "tagName", "-q", ".[].tagName").split()
            if t.startswith("recorder-") and t[9:].isdigit()]
    for tag in sorted(tags):
        month = datetime.strptime(tag[9:], "%Y%m").replace(tzinfo=timezone.utc).timestamp()
        if month > until or month + 32 * 86400 < since:
            continue
        for asset in gh("release", "view", tag, "-R", REPO, "--json", "assets", "-q", ".assets[].name").split():
            run = asset.removesuffix(".tar")
            d = CACHE / run
            if not d.exists():  # unpack next to it, then rename: a half-unpacked hour is never taken for done
                tmp = CACHE / f".{run}.tmp"
                shutil.rmtree(tmp, ignore_errors=True)
                tmp.mkdir(parents=True)
                with tarfile.open(fileobj=io.BytesIO(gh_bytes(tag, asset))) as t:
                    t.extractall(tmp, filter="data")
                tmp.rename(d)
            count = json.loads((d / "count.json").read_text())
            if count["end"] >= since and count["start"] < until:
                yield run, count


def gh_bytes(tag: str, asset: str) -> bytes:
    return subprocess.run(["gh", "release", "download", tag, "-R", REPO, "-p", asset, "-O", "-"],
                          check=True, capture_output=True).stdout


def decrypt(run: str, key: Path) -> Path:
    d = CACHE / run
    if not (d / "out").exists():  # decrypt into out.tmp, then rename
        k = subprocess.run(["openssl", "pkeyutl", "-decrypt", "-inkey", str(key), "-pkeyopt", "rsa_padding_mode:oaep",
                            "-in", str(d / "key.bin.enc")], check=True, capture_output=True).stdout
        (d / "key.bin").write_bytes(k)
        try:
            tgz = subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-in", str(d / "data.tgz.enc"),
                                  "-pass", f"file:{d / 'key.bin'}"], check=True, capture_output=True).stdout
        finally:
            (d / "key.bin").unlink()
        tmp = d / "out.tmp"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        with tarfile.open(fileobj=io.BytesIO(tgz)) as t:
            t.extractall(tmp, filter="data")
        tmp.rename(d / "out")
    return d / "out"


def day(s: str) -> float:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("--from", dest="since", type=day, default=0.0)
    p.add_argument("--to", dest="until", type=day, default=4e9)
    p.add_argument("--key", type=Path, default=Path.home() / ".config/fabrknt/research-data-key.pem")
    a = p.parse_args()
    n = 0
    for run, _ in sorted(hours(a.since, a.until), key=lambda x: x[1]["start"]):
        f = decrypt(run, a.key) / f"{a.source}.jsonl.gz"
        if not f.exists():
            continue
        for line in gzip.open(f, "rt"):
            if a.since <= json.loads(line)["t"] < a.until:
                sys.stdout.write(line)
                n += 1
    print(n, "rows", file=sys.stderr)


if __name__ == "__main__":
    main()
