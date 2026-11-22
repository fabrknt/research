"""Solana SOL/USDC quotes per prop AMM at three sizes each way, from Jupiter's free quote API (no key;
api.jup.ag, then lite-api.jup.ag if that fails: on 2026-11-21 both answered and shared one limit of 100): one row per quote, the route's labels, the output amount and the slot it was priced at.

Each venue is asked alone (dexes=<label>, onlyDirectRoutes) and "any" is Jupiter's best route. A quote that
has no route is kept as its error code: on 2026-11-21 HumidiFi and TesseraV gave no route through this API
at any size, so they are asked only once a run (10 SOL to USDC), to show when that changes.

Only Jupiter's NO_ROUTES_FOUND counts as "no route"; any other failure is kept as its code, and a run where
more than a quarter of the quotes failed that way is incomplete (all of them: the call fails), so the
health check sees it.
"""

import json
import threading
import time
from collections import deque
import urllib.error
import urllib.parse
import urllib.request

HOSTS = ["https://api.jup.ag", "https://lite-api.jup.ag"]
SOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
VENUES = ["any", "BisonFi", "GoonFi V2", "SolFi V2", "ZeroFi", "Kipseli", "Scorch"]
PROBE = ["HumidiFi", "TesseraV"]  # no route on 2026-11-21
SIZES = [(SOL, USDC, a * 10**9) for a in (10, 1_000, 10_000)] + \
        [(USDC, SOL, a * 10**6) for a in (1_000, 100_000, 1_000_000)]
PAUSE = 0.25  # 44 quotes a run, about 15 s; the free limit was 100 per window on 2026-11-21
# Every HTTP attempt to Jupiter, from any source's thread, takes a slot first: at most 80 in any 60 s, under
# the free limit of 100 with room for the 429 retries. xstocks_quotes shares this through quote().
LIMIT, WINDOW = 80, 60.0
_lock, _sent = threading.Lock(), deque()


def _slot() -> None:
    with _lock:  # waiting while holding the lock queues the other threads behind this one
        while True:
            now = time.monotonic()
            while _sent and _sent[0] <= now - WINDOW:
                _sent.popleft()
            if len(_sent) < LIMIT:
                _sent.append(now)
                return
            time.sleep(_sent[0] + WINDOW - now)


def quote(params: dict) -> dict:
    """The quote, or {"errorCode": ...}; tries each host once, and waits once on a 429."""
    last = {"errorCode": "unreachable"}
    for host in HOSTS:
        for attempt in range(2):
            req = urllib.request.Request(f"{host}/swap/v1/quote?{urllib.parse.urlencode(params)}",
                                         headers={"user-agent": "fabrknt-research"})
            _slot()
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                try:
                    last = {"errorCode": json.load(e).get("errorCode") or f"http_{e.code}"}
                except Exception:
                    last = {"errorCode": f"http_{e.code}"}
                if last["errorCode"] == "NO_ROUTES_FOUND":
                    return last
                if e.code == 429 and attempt == 0:
                    time.sleep(10)
                    continue
            except Exception as e:
                last = {"errorCode": type(e).__name__}
            break
    return last


def run(state: dict) -> list[dict]:
    rows, failed = [], 0
    jobs = [(v, size) for v in VENUES for size in SIZES] + [(v, SIZES[0]) for v in PROBE]
    for venue, (src, dst, amount) in jobs:
        q = {"inputMint": src, "outputMint": dst, "amount": amount, "slippageBps": 50}
        if venue != "any":
            q |= {"dexes": venue, "onlyDirectRoutes": "true"}
        row = {"t": time.time(), "venue": venue, "in": "SOL" if src == SOL else "USDC", "amount": amount}
        r = quote(q)
        if "outAmount" in r:
            row |= {"out": r["outAmount"], "impact": r.get("priceImpactPct"), "slot": r.get("contextSlot"),
                    "route": [(p["swapInfo"]["label"], p["percent"]) for p in r.get("routePlan", [])]}
        elif r.get("errorCode") == "NO_ROUTES_FOUND":
            row["err"] = "no_route"
        else:
            row["err"] = r.get("errorCode")
            failed += 1
        rows.append(row)
        time.sleep(PAUSE)
    if failed == len(jobs):
        raise RuntimeError("every quote failed")
    state["status"] = {"incomplete": failed > len(jobs) / 4, "failed_quotes": failed}
    return rows
