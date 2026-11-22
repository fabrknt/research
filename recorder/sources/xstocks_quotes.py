"""Solana xStocks (tokenized US shares) quoted on Jupiter against the Hyperliquid xyz perp book for the same
share, at the same moment, every 5 minutes, weekends included.

Per name, first the xyz l2Book (when xyz lists it), then Jupiter's best route to buy $1k, $10k and $100k of
the token with USDC and to sell back the amount each buy would get, then Hadron alone ($1k each way). The
route keeps each leg's label, pool account and share, so which venues fill (Hadron, Scorch, GoonFi V2 and the
curve pools on 2026-11-22) can be read later.

On 2026-11-22 (a Sunday) Hadron quoted 12 of these names flat up to $2k-8k and nothing above; past $10k
the routes were curve pools and a $100k round trip cost 150-800 bp, while the xyz books held $10k within
about 2 bp. SPYx and QQQx have no xyz perp of their own and are kept for the quotes only.

Each run also keeps every mint's Token-2022 scaledUiAmount config and pause state (one getMultipleAccounts
from Solana's public RPC). Quotes are in raw token units, and one raw token is `multiplier` shares (dividends
are folded in; NFLXx went to 10 on a split): AAPLx was 1.0038 and MSFTx 1.0073 on 2026-11-22, so comparing
a raw price with the xyz price per share without it shows a 38-73 bp gap that isn't there.

Quotes go through solana_quotes.quote (same hosts, same handling of 429 and NO_ROUTES_FOUND), paced so
this and solana_quotes stay under Jupiter's free limit together.
"""

import time

from common import fetch, hl
from solana_quotes import quote

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
# symbol: (mint, xyz perp or None); every xStock has 8 decimals
NAMES = {
    "NVDAx": ("Xsc9qvGR1efVDFGLrVsmkzv3qi45LTBjeUKSPmx9qEh", "xyz:NVDA"),
    "TSLAx": ("XsDoVfqeBukxuZHWhdvWHBhgEHjGNst4MLodqsJHzoB", "xyz:TSLA"),
    "CRCLx": ("XsueG8BtpquVJX9LVLLEGuViXUungE6WmK5YZ3p3bd1", "xyz:CRCL"),
    "AAPLx": ("XsbEhLAtcf6HdfpFZ5xEMdqW8nfAvcsP5bdudRLJzJp", "xyz:AAPL"),
    "MSTRx": ("XsP7xzNPvEHS1m6qfanPUGjNmdnmsLKEoNAnHjdxxyZ", "xyz:MSTR"),
    "GOOGLx": ("XsCPL9dNWBMvFtTmwcCA5v3xWPSMEBCszbQdiLLq6aN", "xyz:GOOGL"),
    "MSFTx": ("XspzcW1PRtgf6Wj92HCiZdjzKCyFekVD8P5Ueh3dRMX", "xyz:MSFT"),
    "METAx": ("Xsa62P5mvPszXL1krVUnU5ar38bBSVcWAB6fmPCo5Zu", "xyz:META"),
    "COINx": ("Xs7ZdzSHLU9ftNJsii5fCeJhoRWSC32SQGzGQtePxNu", "xyz:COIN"),
    "GMEx": ("Xsf9mBktVB9BSU5kf4nHxPq5hCBJ2j2ui3ecFGxPRGc", "xyz:GME"),
    "SPYx": ("XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W", None),
    "QQQx": ("Xs8S1uUs1zvS2p7iwtsG3b6fkhpvmwz4GYU3gWAmWHZ", None),
}
SIZES = (1_000, 10_000, 100_000)  # USD of USDC in
ALONE = "Hadron"
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
PAUSE = 1.0  # 96 quotes a run, about 2 minutes; solana_quotes.quote also holds both sources to 80 a minute


def _ask(row: dict, params: dict) -> tuple[dict, int]:
    """Fills row from one quote; returns (row, 1 if it failed other than as no route)."""
    r = quote(params | {"slippageBps": 50})
    time.sleep(PAUSE)
    if "outAmount" in r:
        row |= {"out": int(r["outAmount"]), "slot": r.get("contextSlot"), "impact": r.get("priceImpactPct"),
                "route": [(p["swapInfo"]["label"], p["swapInfo"].get("ammKey"), p["percent"])
                          for p in r.get("routePlan", [])]}
        return row, 0
    if r.get("errorCode") == "NO_ROUTES_FOUND":
        row["err"] = "no_route"
        return row, 0
    row["err"] = r.get("errorCode")
    return row, 1


def run(state: dict) -> list[dict]:
    rows, failed, asked, books, books_failed = [], 0, 0, 0, 0
    mints_failed = 0
    try:
        got = fetch(SOLANA_RPC, {"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
                                 "params": [[m for m, _ in NAMES.values()], {"encoding": "jsonParsed"}]})
        for sym, acct in zip(NAMES, got["result"]["value"]):
            ext = {e["extension"]: e.get("state") for e in acct["data"]["parsed"]["info"].get("extensions", [])}
            rows.append({"t": time.time(), "kind": "mint", "sym": sym, "slot": got["result"]["context"]["slot"],
                         "scaled": ext.get("scaledUiAmountConfig"), "pause": ext.get("pausableConfig")})
    except Exception as e:
        rows.append({"t": time.time(), "kind": "mint", "err": type(e).__name__})
        mints_failed = 1
    for sym, (mint, perp) in NAMES.items():
        if perp:
            books += 1
            try:
                b = hl({"type": "l2Book", "coin": perp})
                rows.append({"t": time.time(), "kind": "hl_book", "sym": sym, "coin": perp,
                             "time": b.get("time"), "levels": b.get("levels")})
            except Exception as e:
                rows.append({"t": time.time(), "kind": "hl_book", "sym": sym, "coin": perp, "err": type(e).__name__})
                books_failed += 1
        jobs = [("any", usd) for usd in SIZES] + [(ALONE, SIZES[0])]
        for venue, usd in jobs:
            only = {"dexes": venue, "onlyDirectRoutes": "true"} if venue != "any" else {}
            buy, f = _ask({"t": time.time(), "kind": "quote", "sym": sym, "venue": venue, "side": "buy",
                           "usd": usd, "amount": usd * 10**6},
                          {"inputMint": USDC, "outputMint": mint, "amount": usd * 10**6} | only)
            rows.append(buy)
            failed, asked = failed + f, asked + 1
            if "out" not in buy:
                continue
            sell, f = _ask({"t": time.time(), "kind": "quote", "sym": sym, "venue": venue, "side": "sell",
                            "usd": usd, "amount": buy["out"]},
                           {"inputMint": mint, "outputMint": USDC, "amount": buy["out"]} | only)
            rows.append(sell)
            failed, asked = failed + f, asked + 1
    if failed == asked and books_failed == books:
        raise RuntimeError("every call failed")
    # the quotes and the books are judged apart: either one missing a quarter makes the run incomplete
    state["status"] = {"incomplete": failed > asked / 4 or books_failed > books / 4 or bool(mints_failed),
                       "failed_quotes": failed, "failed_books": books_failed, "failed_mints": mints_failed}
    return rows
