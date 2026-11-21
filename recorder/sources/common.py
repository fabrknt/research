"""HTTP helpers shared by the sources: JSON GET/POST and plain text, with retries."""

import json
import time
import urllib.request

HL = "https://api.hyperliquid.xyz/info"
UA = "fabrknt-research"


def fetch(url: str, body=None, tries: int = 4, raw: bool = False):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                         headers={"content-type": "application/json", "user-agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            return data.decode("utf-8", "replace") if raw else json.loads(data)
        except Exception as e:  # 429s and timeouts: wait (as long as a 429 asks, at least) and retry
            if i == tries - 1 or getattr(e, "code", None) in (400, 404):  # an answer, not a hiccup
                raise
            wait = 2 + 3 * i
            if getattr(e, "code", None) == 429:
                try:
                    wait = max(wait, float(json.load(e).get("retry_after_seconds", 0)) + 1)
                except Exception:
                    pass
            time.sleep(wait)


def hl(body):
    return fetch(HL, body)


def hl_dexes() -> list[str]:
    """"" for the main dex, then every HIP-3 dex by name."""
    return [""] + [d["name"] for d in hl({"type": "perpDexs"}) if d]
