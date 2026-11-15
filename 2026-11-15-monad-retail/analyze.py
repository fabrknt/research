"""Count one day of nad.fun's V2 bonding curve from scan_curve.py's output.

    python3 -I analyze.py day.json

Event signatures are in topics.txt. Buy and Sell carry (token, sender) as indexed topics, in that
order (nad.fun token addresses end in 7777), and (amountIn, amountOut) as data; Create's first topic
is the creator; MON is amountIn on a Buy and amountOut on a Sell.
"""
import json, sys

T = {
    "buy": "0x89f5adc174562e07c9c9b1cae7109bbecb21cf9d1b2847e550042b8653c54a0e",
    "sell": "0xa082022e93cfcd9f1da5f9236718053910f7e840da080c789c7845698dc032ff",
    "create": "0xac11ceed5187dce8e72afc92116e2aebbbd4fb263cb4021374a5df1b90c89936",
    "graduate": "0xc0682ac2d5a530c92664a8717db0ab335b5c5cbdfdc740185679e170244633e0",
}
d = json.load(open(sys.argv[1]))
logs = d["logs"]
hours = (d["head"] - d["start"]) * d["block_time"] / 3600
of = lambda k: [l for l in logs if l["topics"][0] == T[k]]
word = lambda l, i: int(l["data"][2 + 64 * i: 2 + 64 * (i + 1)], 16)
addr = lambda t: "0x" + t[-40:]
creates, grads = of("create"), of("graduate")
buys, sells = of("buy"), of("sell")
traders = {addr(l["topics"][2]) for l in buys + sells}
mon = sum(word(l, 0) for l in buys) + sum(word(l, 1) for l in sells)
print(f"window: blocks {d['start']}..{d['head']} = {hours:.1f} h, failed ranges: {len(d.get('failed') or [])}")
print(f"created: {len(creates)} tokens by {len({addr(l['topics'][1]) for l in creates})} creators; graduated: {len(grads)}")
print(f"trades: {len(buys)} buys, {len(sells)} sells, by {len(traders)} addresses")
print(f"MON through the curve: {mon / 1e18:,.0f}")
