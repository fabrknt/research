"""How far does a US stock move between Friday's close and Monday's open, and how close does Hyperliquid's
24/7 price (trade.xyz's HIP-3 dex) get to the open at each point of the weekend?

    python3 -I weekend.py            # every weekend still in reach -> results/weekends.csv

Reads 15-minute candles from Hyperliquid's public info API (the latest 5,000, about 52 days) and keeps
only derived numbers, in bp: no prices are written. A weekend already in the file is not read again, so
a weekly run adds the new one and keeps the old rows after the candles are gone.

"Open" is xyz's price 15 minutes after the US open (the close of the 09:30–09:45 New York candle), when
the perp has the real market to follow; "close" is xyz's price at 16:00 New York on the last trading day.
"""
import csv
import datetime as dt
import json
import os
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
API = "https://api.hyperliquid.xyz/info"
COINS = [
    "SP500", "XYZ100", "AAPL", "AMD", "AMZN", "COIN", "COST", "CRCL", "GOOGL", "HOOD", "INTC", "LLY",
    "META", "MSFT", "MSTR", "MU", "NFLX", "NVDA", "ORCL", "PLTR", "SNDK", "TSLA",
]
# NYSE full-day closures that touch a weekend (a Friday or a Monday), 2026-09..2027-12, and the
# Fridays that close at 13:00 (the day after Thanksgiving).
EARLY_CLOSE = {dt.date(2026, 11, 27), dt.date(2027, 11, 26)}
HOLIDAYS = {
    dt.date(2026, 9, 7), dt.date(2026, 12, 25), dt.date(2027, 1, 1), dt.date(2027, 1, 18),
    dt.date(2027, 2, 15), dt.date(2027, 3, 26), dt.date(2027, 5, 31), dt.date(2027, 9, 6),
    dt.date(2027, 12, 24),
}
# Points of the weekend at which we ask how close xyz already is to the open.
CHECKS = ["sun_20utc", "mon_07utc", "open_minus_1h"]
FIELDS = ["close_day", "open_day", "coin", "gap_bp"] + [f"err_{c}_bp" for c in CHECKS]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "weekends.csv")


def trading_day(d):
    return d.weekday() < 5 and d not in HOLIDAYS


def weekends(today):
    """(last trading day before, first trading day after) for each weekend whose open is done by now."""
    out = []
    d = today - dt.timedelta(days=60)
    while d <= today:
        if d.weekday() == 5:  # Saturday
            close = d - dt.timedelta(days=1)
            while not trading_day(close):
                close -= dt.timedelta(days=1)
            opn = d + dt.timedelta(days=2)
            while not trading_day(opn):
                opn += dt.timedelta(days=1)
            out.append((close, opn))
        d += dt.timedelta(days=1)
    return out


def ny(day, hh, mm):
    return dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=NY).astimezone(UTC)


def candles(coin, start, end):
    body = json.dumps({"type": "candleSnapshot", "req": {
        "coin": f"xyz:{coin}", "interval": "15m",
        "startTime": int(start.timestamp() * 1000), "endTime": int(end.timestamp() * 1000)}}).encode()
    for attempt in range(5):
        try:
            req = urllib.request.Request(API, body, {"content-type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return {int(c["T"]) + 1: float(c["c"]) for c in json.load(r)}  # candle end (ms) -> close
        except Exception as e:  # 429s come in bursts
            print(f"{coin}: {e}, retrying", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return {}


def price_at(series, t):
    """xyz's price at time t: the close of the 15-minute candle that ends at t."""
    return series.get(int(t.timestamp() * 1000))


def main():
    now = dt.datetime.now(UTC)
    done = set()
    rows = []
    if os.path.exists(OUT):
        with open(OUT) as f:
            rows = list(csv.DictReader(f))
        done = {(r["close_day"], r["coin"]) for r in rows}
    earliest = now - dt.timedelta(minutes=15 * 4990)
    todo = [(c, o) for c, o in weekends(now.date())
            if ny(o, 9, 45) <= now and ny(c, 16, 0) - dt.timedelta(minutes=15) >= earliest]
    added = 0
    for coin in COINS:
        need = [(c, o) for c, o in todo if (c.isoformat(), coin) not in done]
        if not need:
            continue
        series = candles(coin, ny(need[0][0], 12, 0), now)
        time.sleep(0.5)
        for close_day, open_day in need:
            close = price_at(series, ny(close_day, 13 if close_day in EARLY_CLOSE else 16, 0))
            opn = price_at(series, ny(open_day, 9, 45))
            sunday = open_day - dt.timedelta(days=(open_day.weekday() + 1) % 7 or 7)
            at = {
                "sun_20utc": dt.datetime(sunday.year, sunday.month, sunday.day, 20, tzinfo=UTC),
                "mon_07utc": dt.datetime(open_day.year, open_day.month, open_day.day, 7, tzinfo=UTC),
                "open_minus_1h": ny(open_day, 8, 30),
            }
            if not close or not opn:
                continue  # not listed yet, or a missing candle
            row = {"close_day": close_day.isoformat(), "open_day": open_day.isoformat(), "coin": coin,
                   "gap_bp": f"{(opn / close - 1) * 1e4:.1f}"}
            for name, t in at.items():
                p = price_at(series, t)
                row[f"err_{name}_bp"] = f"{(opn / p - 1) * 1e4:.1f}" if p else ""
            rows.append(row)
            added += 1
    rows.sort(key=lambda r: (r["close_day"], r["coin"]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"added {added} rows, {len(rows)} in {os.path.relpath(OUT)}")


if __name__ == "__main__":
    main()
