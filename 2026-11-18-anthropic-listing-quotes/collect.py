"""Every minute, save Binance's and Bitget's Anthropic pre-IPO perp quotes, as quoted.

The reference prices for HL Price Guard's Anthropic IPO case (fabrknt/hl-price-guard,
cases/anthropic-ipo-2026). Its Cloudflare recorder reads Hyperliquid and OKX; Binance and Bitget
answer 403 to Cloudflare, so they are read here. Each venue's price is stored as quoted, with no
share-count basis applied, so a rebase cannot be written into the record. OKX is read too, to line
the two records up.

    python3 collect.py 60 60     # 60 rounds, every 60 s -> data/quotes-YYYYMMDD.jsonl
"""
import json
import os
import sys
import time
import urllib.request

# Binance's announced move to about 13.1B shares comes under a new symbol, ANTUSDT; read both names.
SOURCES = {
    "binance": ["https://fapi.binance.com/fapi/v1/premiumIndex?symbol=" + s for s in ("ANTHROPICUSDT", "ANTUSDT")],
    "bitget": ["https://api.bitget.com/api/v2/mix/market/ticker?productType=USDT-FUTURES&symbol=" + s
               for s in ("ANTHROPICUSDT", "ANTUSDT")],
    "okx": ["https://www.okx.com/api/v5/market/ticker?instId=ANTHROPIC-USDT-SWAP"],
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def get(url):
    req = urllib.request.Request(url, headers={"user-agent": "fabrknt-research"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def main(rounds: int, every: int) -> None:
    os.makedirs(OUT, exist_ok=True)
    for i in range(rounds):
        start = time.time()
        row = {"t": int(start)}
        for venue, urls in SOURCES.items():
            for url in urls:
                try:
                    row[url] = get(url)
                except Exception as e:  # an unlisted symbol or a block is part of the record
                    row[url] = {"error": f"{getattr(e, 'code', '')} {e}"[:200]}
        with open(os.path.join(OUT, time.strftime("quotes-%Y%m%d.jsonl", time.gmtime(start))), "a") as f:
            f.write(json.dumps(row) + "\n")
        if i < rounds - 1:
            time.sleep(max(0, every - (time.time() - start)))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
