"""Books at high frequency, but only around events: a big move or a new listing on Hyperliquid.

Every run (10 s) reads allMids for the main dex's perps and every HIP-3 dex. A name becomes "hot" for HOT_S
(72 h) when its mid is MOVE (1.5%) or more from the highest or lowest mid of the last minute and its 24h
volume is at least MIN_VLM, or when it appears for the first time (a new listing). A HIP-3 name is registered
halted (isDelisted) before it trades; every PENDING_EVERY runs the dexes holding such names are re-read, so
the run that sees one open marks it "new" within about a minute instead of at the next 10-minute refresh, and a
name that appears halted and was never seen trading gets a "registered" trigger row. For each hot name (at
most MAX_HOT, newest kept) a run saves the Hyperliquid l2Book, and every third run the Lighter book if
Lighter lists the same symbol. Book failures are counted in the public status, and a run where half or
more of the wanted books failed, or with hot names but no Lighter market list, is incomplete, so the health
check sees it.

Rows: {"kind": "trigger", "name", "why": "move" | "new" | "registered", "move"} and {"kind": "book", "name", "hl", "lighter"}.
The state is published unencrypted, so it holds names only as hashes (they come from the venues' APIs):
state["known"] the names seen so far, state["hot"] hash -> expiry.
"""

import hashlib
import time
from collections import deque

from common import fetch, hl, hl_dexes

LIGHTER = "https://mainnet.zklighter.elliot.ai/api/v1"
MOVE = 0.015
WINDOW_S = 60
MIN_VLM = 2_000_000
HOT_S = 72 * 3600
MAX_HOT = 8
REFRESH_S = 600  # names, volumes and Lighter's markets
PENDING_EVERY = 6  # runs: re-read the dexes holding never-traded halted names (about a minute; 20-weight calls)

LIGHTER_EVERY = 3  # runs: about 18 Lighter calls a minute at most, beside one_quote's 40 every 5 minutes
START_DELAY = 20   # s: the first run waits, so this cold start doesn't stack on the other sources'

_cache = {"at": 0.0, "vlm": {}, "dexes": [], "halted": {}, "lighter": {}, "lighter_ok": True, "runs": 0}
_mids: deque = deque()  # (t, {name: mid}) over the last WINDOW_S + a little


def key(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def read_dex(dex: str, vlm: dict, halted: dict) -> None:
    meta, ctxs = hl({"type": "metaAndAssetCtxs", **({"dex": dex} if dex else {})})
    for u, c in zip(meta["universe"], ctxs):
        if u.get("isDelisted"):
            halted[u["name"]] = dex
        else:
            vlm[u["name"]] = float(c.get("dayNtlVlm") or 0)


def refresh() -> None:
    vlm, halted, dexes = {}, {}, hl_dexes()
    for dex in dexes:
        read_dex(dex, vlm, halted)
    _cache.update(at=time.time(), vlm=vlm, halted=halted, dexes=dexes)
    lighter_markets()


def check_pending(known: set) -> None:
    """Re-read only the HIP-3 dexes holding halted names that never traded, so an opening is seen within
    PENDING_EVERY runs. Names delisted after trading are left to the 10-minute refresh."""
    for dex in sorted({d for n, d in _cache["halted"].items() if d and key(n) not in known}):
        vlm, halted = {}, {}
        try:
            read_dex(dex, vlm, halted)
        except Exception:
            continue  # the next check or refresh tries again
        for name in [n for n, d in _cache["halted"].items() if d == dex and n not in halted]:
            del _cache["halted"][name]
        for name in halted:
            _cache["halted"].setdefault(name, dex)
            _cache["vlm"].pop(name, None)  # halted now: no move triggers or books until it trades again
        _cache["vlm"].update(vlm)


def lighter_markets() -> None:
    _cache["lighter_try"] = time.time()
    try:
        _cache["lighter"] = {o["symbol"]: o["market_id"] for o in fetch(LIGHTER + "/orderBooks")["order_books"]
                             if o["status"] == "active" and o["market_type"] == "perp"}
        _cache["lighter_ok"] = True
    except Exception:
        _cache["lighter_ok"] = False


def run(state: dict) -> list[dict]:
    if _cache["at"] == 0:
        time.sleep(START_DELAY)
    now = time.time()
    if now - _cache["at"] > REFRESH_S:
        refresh()
        now = time.time()
    elif not _cache["lighter_ok"] and now - _cache.get("lighter_try", 0) > 60:  # try again each minute
        lighter_markets()
        now = time.time()
    _cache["runs"] += 1
    if _cache["runs"] % PENDING_EVERY == 0:
        check_pending(set(state.get("known", [])))
    mids = {}
    for dex in _cache["dexes"]:
        for name, px in hl({"type": "allMids", **({"dex": dex} if dex else {})}).items():
            if name in _cache["vlm"]:
                mids[name] = float(px)
    _mids.append((now, mids))
    while _mids and _mids[0][0] < now - WINDOW_S:
        _mids.popleft()
    rows = []
    lo, hi = {}, {}  # lowest and highest mid of the last minute, this run included
    for _, m in _mids:
        for n, px in m.items():
            if px > 0:
                lo[n], hi[n] = min(lo.get(n, px), px), max(hi.get(n, px), px)

    known = set(state.get("known", []))
    hot = {k: e for k, e in state.get("hot", {}).items() if e > now}
    first = not known
    first_reg = "registered" not in state  # names already halted when this check started are not news
    registered = set(state.get("registered", []))
    for name in _cache["halted"]:  # registered but not trading: a name that never traded is a coming listing
        k = key(name)
        if k not in known and k not in registered:
            registered.add(k)
            if not (first or first_reg):
                rows.append({"t": now, "kind": "trigger", "name": name, "why": "registered", "move": None})
    for name, px in mids.items():
        k = key(name)
        why, move = None, None
        if k not in known:
            known.add(k)
            why = None if first else "new"
        elif px > 0 and name in lo and _cache["vlm"].get(name, 0) >= MIN_VLM:
            up, down = px / lo[name] - 1, px / hi[name] - 1
            move = up if up >= -down else down
            if abs(move) >= MOVE:
                why = "move"
        if why:  # a name already hot only has its 72 h extended; the trigger row marks the start
            if k not in hot:
                rows.append({"t": now, "kind": "trigger", "name": name, "why": why, "move": move})
            hot[k] = now + HOT_S
    if len(hot) > MAX_HOT:  # keep the most recently triggered
        hot = dict(sorted(hot.items(), key=lambda x: -x[1])[:MAX_HOT])

    names = {key(n): n for n in mids}
    with_lighter = _cache["runs"] % LIGHTER_EVERY == 0
    wanted = failed = 0
    for k in hot:
        name = names.get(k)
        if not name:
            continue
        row = {"t": now, "kind": "book", "name": name}
        wanted += 1
        try:
            d = hl({"type": "l2Book", "coin": name})
            row["hl"] = {"bids": [(x["px"], x["sz"]) for x in d["levels"][0]],
                         "asks": [(x["px"], x["sz"]) for x in d["levels"][1]], "t": d["time"] / 1000}
        except Exception as e:
            row["hl_err"] = type(e).__name__
            failed += 1
        base = name.split(":", 1)[-1]
        if with_lighter and base in _cache["lighter"]:
            wanted += 1
            try:
                d = fetch(f"{LIGHTER}/orderBookOrders?market_id={_cache['lighter'][base]}&limit=100")
                row["lighter"] = {"bids": [(o["price"], o["remaining_base_amount"]) for o in d["bids"]],
                                  "asks": [(o["price"], o["remaining_base_amount"]) for o in d["asks"]],
                                  "t": time.time()}
            except Exception as e:
                row["lighter_err"] = type(e).__name__
                failed += 1
        rows.append(row)

    state["known"], state["hot"], state["registered"] = sorted(known), hot, sorted(registered)
    state["status"] = {"hot": len(hot), "books_wanted": wanted, "books_failed": failed,
                       "lighter_markets_ok": _cache["lighter_ok"],
                       "incomplete": (wanted > 0 and failed * 2 >= wanted) or (bool(hot) and not _cache["lighter_ok"])}
    return rows
