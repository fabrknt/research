"""Books at high frequency, but only around events: a big move or a new listing on Hyperliquid.

Every run (10 s) reads allMids for the main dex's perps and every HIP-3 dex. A name becomes "hot" for HOT_S
(72 h) when its mid is MOVE (1.5%) or more from the highest or lowest mid of the last minute and its 24h
volume is at least MIN_VLM, or when it appears for the first time (a new listing). A HIP-3 name is registered
halted (isDelisted) before it trades; every PENDING_EVERY runs the dexes holding such names are re-read, so
the run that sees one open marks it "new" within about a minute instead of at the next 10-minute refresh, and a
name that appears halted and was never seen trading gets a "registered" trigger row. For each hot name (at
most MAX_HOT moves and MAX_NEW listings, newest kept in each, so a burst of moves never pushes a listing's
first 72 h out) a run saves the Hyperliquid l2Book, and every third run the Lighter book if
Lighter lists the same symbol. Book failures are counted in the public status, and a run where half or
more of the wanted books failed, or with hot names but no Lighter market list, is incomplete, so the health
check sees it.

A registered name's deployer settings (perpDexs: open-interest cap, funding multiplier, interest rate, clamp)
are read with the pending check; a change while it is still halted is the deployer preparing the opening and
gives a "prep" trigger row. If NTFY_TOPIC is set, "registered", "prep" and "new" rows are also pushed to
https://ntfy.sh/<topic> (a secret; the only place names leave the encrypted rows). Pushes go through an
in-memory queue sent by a background thread, so a slow ntfy never stalls the 10 s sampling; a push is retried
for up to PUSH_TRY_S, then dropped and counted (status push_failed, push_queued). The row is the durable record:
a push still queued when the process ends is lost, and the next process does not resend it.
A name's settings are compared only against a baseline from a settings read made after this process first
saw the name halted, so settings that were already there at registration are not announced as a change. The
baseline is kept in state across processes on purpose: settings that changed between two processes, while the
name stayed halted, are a real change and are announced at the first read of the new process.

Rows: {"kind": "trigger", "name", "why": "move" | "new" | "registered" | "prep", "move", "oracle"?, "prep"?}
and {"kind": "book", "name", "hl", "lighter"}.
The state is published unencrypted, so it holds names only as hashes (they come from the venues' APIs):
state["known"] the names seen so far, state["hot"] hash -> expiry for moves, state["new"] the same for
listings, state["registered"] halted names seen,
state["prep"] hash -> hash of its deployer settings.
"""

import hashlib
import queue
import threading
import time
from collections import deque

from common import fetch, hl, hl_dexes, notify

LIGHTER = "https://mainnet.zklighter.elliot.ai/api/v1"
MOVE = 0.015
WINDOW_S = 60
MIN_VLM = 2_000_000
HOT_S = 72 * 3600
MAX_HOT = 8   # names hot from a move
MAX_NEW = 6   # names hot from a listing, kept apart: 11-24 a listing's books were cut at 30 min by moves
REFRESH_S = 600  # names, volumes and Lighter's markets
PENDING_EVERY = 6  # runs: re-read the dexes holding never-traded halted names (about a minute; 20-weight calls)

LIGHTER_EVERY = 3  # runs: about 18 Lighter calls a minute at most, beside one_quote's 40 every 5 minutes
START_DELAY = 20   # s: the first run waits, so this cold start doesn't stack on the other sources'

_cache = {"at": 0.0, "vlm": {}, "dexes": [], "halted": {}, "oracle": {}, "prep": {}, "lighter": {}, "lighter_ok": True,
          "runs": 0, "prep_t": 0.0, "seen_halted": {}, "push_failed": 0}
PUSH_TRY_S = 600
_outbox: queue.Queue = queue.Queue()


def _sender() -> None:
    while True:
        title, body, t0 = _outbox.get()
        while not notify(title, body):
            if time.time() - t0 > PUSH_TRY_S:
                _cache["push_failed"] += 1
                break
            time.sleep(20)
        _outbox.task_done()


def push(title: str, body: str) -> None:
    if not _cache.get("sender"):
        _cache["sender"] = threading.Thread(target=_sender, daemon=True)
        _cache["sender"].start()
    _outbox.put((title, body, time.time()))


PREP_FIELDS = {"assetToStreamingOiCap": "oi_cap", "assetToFundingMultiplier": "funding_mult",
               "assetToFundingInterestRate": "funding_rate", "assetToFundingClamp": "funding_clamp"}
_mids: deque = deque()  # (t, {name: mid}) over the last WINDOW_S + a little


def key(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:16]


def read_dex(dex: str, vlm: dict, halted: dict) -> None:
    meta, ctxs = hl({"type": "metaAndAssetCtxs", **({"dex": dex} if dex else {})})
    for u, c in zip(meta["universe"], ctxs):
        if u.get("isDelisted"):
            halted[u["name"]] = dex
            _cache["oracle"][u["name"]] = c.get("oraclePx")
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


def read_prep() -> None:
    """Each HIP-3 name's deployer settings, from one perpDexs call (kept as they were if it fails)."""
    t0 = time.time()
    try:
        prep = {}
        for d in hl({"type": "perpDexs"}):
            for field, short in PREP_FIELDS.items():
                for item in (d or {}).get(field) or []:
                    if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str):
                        prep.setdefault(item[0], {})[short] = item[1]
        _cache["prep"], _cache["prep_read"], _cache["prep_t"] = prep, True, t0
    except Exception:
        pass


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
        if any(d for d in _cache["halted"].values()):
            read_prep()
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
    new = {k: e for k, e in state.get("new", {}).items() if e > now}
    if "new" not in state:  # state from before the split: a hot name once seen halted was hot from its listing
        was_halted = set(state.get("registered", []))
        new = {k: e for k, e in hot.items() if k in was_halted}
        hot = {k: e for k, e in hot.items() if k not in was_halted}
    first = not known
    first_reg = "registered" not in state  # names already halted when this check started are not news
    registered = set(state.get("registered", []))
    preps = dict(state.get("prep", {}))
    for name in _cache["halted"]:  # registered but not trading: a name that never traded is a coming listing
        k = key(name)
        if k in known:
            continue
        p = _cache["prep"].get(name, {})
        seen = _cache["seen_halted"].setdefault(name, now)
        fresh = _cache.get("prep_read") and _cache["prep_t"] > seen  # settings read after the name was seen
        ph = key(name + repr(sorted(p.items())))
        if k not in registered:
            registered.add(k)
            if not (first or first_reg):
                rows.append({"t": now, "kind": "trigger", "name": name, "why": "registered", "move": None,
                             "oracle": _cache["oracle"].get(name), "prep": p})
        elif fresh and k in preps and preps[k] != ph:
            rows.append({"t": now, "kind": "trigger", "name": name, "why": "prep", "move": None,
                         "oracle": _cache["oracle"].get(name), "prep": p})
        if fresh:
            preps[k] = ph
    pending = {key(n) for n in _cache["halted"]}  # the last successful read of each dex
    preps = {k: v for k, v in preps.items() if k in pending and k not in known}
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
        if why == "new":
            rows.append({"t": now, "kind": "trigger", "name": name, "why": why, "move": move})
            new[k] = now + HOT_S
            hot.pop(k, None)
        elif why and k not in new:  # a listing's own moves stay inside its listing window
            if k not in hot:  # a name already hot only has its 72 h extended; the trigger row marks the start
                rows.append({"t": now, "kind": "trigger", "name": name, "why": why, "move": move})
            hot[k] = now + HOT_S
    if len(hot) > MAX_HOT:  # keep the most recently triggered
        hot = dict(sorted(hot.items(), key=lambda x: -x[1])[:MAX_HOT])
    if len(new) > MAX_NEW:
        new = dict(sorted(new.items(), key=lambda x: -x[1])[:MAX_NEW])

    names = {key(n): n for n in mids}
    with_lighter = _cache["runs"] % LIGHTER_EVERY == 0
    wanted = failed = 0
    for k in [*new, *hot]:
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

    for r in rows:
        if r["kind"] != "trigger" or r["why"] == "move":
            continue
        p = ", ".join(f"{a} {b}" for a, b in sorted((r.get("prep") or {}).items()))
        title, body = {
            "registered": ("HL registered " + r["name"], f"halted, oracle {r.get('oracle')}\n{p}"),
            "prep": ("HL opening prep " + r["name"], f"still halted, oracle {r.get('oracle')}\n{p}"),
            "new": ("HL trading open " + r["name"], f"mid {mids.get(r['name'])}"),
        }[r["why"]]
        push(title, body)

    state["known"], state["hot"], state["new"], state["registered"] = sorted(known), hot, new, sorted(registered)
    state["prep"] = preps
    state["status"] = {"hot": len(hot), "listing_hot": len(new), "books_wanted": wanted, "books_failed": failed,
                       "lighter_markets_ok": _cache["lighter_ok"], "push_failed": _cache["push_failed"],
                       "push_queued": _outbox.unfinished_tasks,  # waiting or being retried
                       "incomplete": (wanted > 0 and failed * 2 >= wanted) or (bool(hot or new) and not _cache["lighter_ok"])}
    return rows
