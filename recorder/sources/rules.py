"""Each venue's rules as they stand today: one row per item, its sha256, and whether it changed since it was
last fetched (state["sha"]). Items: Hyperliquid perpDexs, meta (with margin tables) per dex and spotMeta;
Lighter orderBookDetails; every page listed in the Hyperliquid, Lighter and Variational docs' llms.txt.

Items that fail are tried again (status incomplete, within 10 minutes), only those (all of a docs site's
pages when its index failed), up to TRIES times a day; after that the day is closed with status
failed_items > 0, which the health check reports. The state is published unencrypted, so it names items
only by a hash of their name (dex names and docs URLs come from the venues' APIs).
"""

import hashlib
import json
import re
import time

from common import fetch, hl, hl_dexes

LIGHTER = "https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails"
DOCS = {"hl": "https://hyperliquid.gitbook.io/hyperliquid-docs/llms.txt",
        "lighter": "https://docs.lighter.xyz/llms.txt",
        "variational": "https://docs.variational.io/llms.txt"}
PAUSE = 0.3  # between docs pages
TRIES = 3


def key(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def items():
    """(name, the docs index it was listed in or None, fetch)"""
    yield "hl/perpDexs", None, lambda: hl({"type": "perpDexs"})
    for dex in hl_dexes():
        yield f"hl/meta/{dex or 'main'}", None, (lambda d=dex: hl({"type": "meta", **({"dex": d} if d else {})}))
    yield "hl/spotMeta", None, lambda: hl({"type": "spotMeta"})
    yield "lighter/orderBookDetails", None, lambda: fetch(LIGHTER)
    for venue, index in DOCS.items():
        name = f"docs/{venue}/llms.txt"
        try:
            text = fetch(index, raw=True)
        except Exception as e:
            yield name, None, (lambda e=e: (_ for _ in ()).throw(e))
            continue
        yield name, None, lambda t=text: t
        for url in dict.fromkeys(re.findall(r"\]\((https://[^)\s]+)\)", text)):
            yield f"docs/{venue}/{url.split('://', 1)[1]}", name, (lambda u=url: (time.sleep(PAUSE), fetch(u, raw=True))[1])


def run(state: dict) -> list[dict]:
    today = time.strftime("%Y-%m-%d", time.gmtime())
    retry = state.get("day") == today and state.get("failed")
    if not retry:
        state["day"], state["tries"] = today, 0
    want = {k for k in state.get("failed", []) if len(k) == 16} if retry else None
    # only hashed names in the state (a name kept in plain by an earlier version is dropped)
    seen = state["sha"] = {k: v for k, v in state.get("sha", {}).items() if len(k) == 16}
    rows, failed, yielded = [], [], set()
    for name, index, get in items():
        k = key(name)
        yielded.add(k)
        if want is not None and k not in want and not (index and key(index) in want):
            continue
        try:
            body = get()
        except Exception:
            failed.append(k)
            continue
        text = body if isinstance(body, str) else json.dumps(body, sort_keys=True)
        sha = hashlib.sha256(text.encode()).hexdigest()
        rows.append({"t": time.time(), "item": name, "sha": sha, "changed": seen.get(k) != sha, "body": body})
        seen[k] = sha
    if want is not None:  # pending items not reached this time (their index failed again) stay pending
        failed += sorted(want - yielded)
    state["tries"] += 1
    give_up = state["tries"] >= TRIES
    state["failed"] = [] if give_up else failed
    state["status"] = {"incomplete": bool(failed) and not give_up, "failed_items": len(failed)}
    return rows
