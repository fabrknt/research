"""HIP-3(trade.xyz)の株 perps の足を Hyperliquid の公開 API から取る。"""
import json, time, urllib.error, urllib.request

HL = "https://api.hyperliquid.xyz/info"


def post(body, retries=8):
    req = urllib.request.Request(HL, json.dumps(body).encode(), {"Content-Type": "application/json"})
    for i in range(retries):
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:
            # 429 は待って取り直す。
            if e.code != 429 or i == retries - 1:
                raise
            time.sleep(min(30, 2 ** i))


def candles(coin, interval, start_ms, end_ms):
    out = {}
    while start_ms < end_ms:
        cs = post({"type": "candleSnapshot", "req": {"coin": coin, "interval": interval,
                                                     "startTime": start_ms, "endTime": end_ms}})
        if not cs:
            break
        for c in cs:
            out[c["t"]] = c
        nxt = cs[-1]["t"] + 1
        if nxt <= start_ms:
            break
        start_ms = nxt
        time.sleep(0.3)
    return [out[k] for k in sorted(out)]


if __name__ == "__main__":
    meta = post({"type": "meta", "dex": "xyz"})
    print([u["name"] for u in meta["universe"]][:80])
