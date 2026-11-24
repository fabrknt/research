"""HTTP helpers shared by the sources: JSON GET/POST and plain text, with retries."""

import json
import os
import time
import urllib.request

HL = "https://api.hyperliquid.xyz/info"
UA = "fabrknt-research"


def fetch(url: str, body=None, tries: int = 4, raw: bool = False, headers: dict | None = None):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                         headers={"content-type": "application/json", "user-agent": UA}
                                         | (headers or {}))
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            return data.decode("utf-8", "replace") if raw else json.loads(data)
        except Exception as e:  # 429s and timeouts: wait (as long as a 429 asks, at least) and retry
            if i == tries - 1 or getattr(e, "code", None) in (400, 404):  # an answer, not a hiccup
                raise
            wait = 2 + 3 * i
            if getattr(e, "code", None) == 429:
                try:  # the Retry-After header (Solana's public RPC), capped so one call can't stall the hour
                    wait = max(wait, min(60.0, float(e.headers.get("Retry-After") or 0)))
                except Exception:
                    pass
                try:  # or a JSON retry_after_seconds (Hyperliquid)
                    wait = max(wait, float(json.load(e).get("retry_after_seconds", 0)) + 1)
                except Exception:
                    pass
            time.sleep(wait)


def hl(body):
    return fetch(HL, body)


def hl_dexes() -> list[str]:
    """"" for the main dex, then every HIP-3 dex by name."""
    return [""] + [d["name"] for d in hl({"type": "perpDexs"}) if d]


def notify(title: str, body: str) -> bool:
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return True
    for i in range(3):
        try:
            req = urllib.request.Request(f"https://ntfy.sh/{topic}", data=body.encode(),
                                         headers={"Title": title, "Priority": "high", "user-agent": "fabrknt-research"})
            urllib.request.urlopen(req, timeout=15).read()
            return True
        except Exception:
            time.sleep(2 + 3 * i)
    return False  # the row is still the record
