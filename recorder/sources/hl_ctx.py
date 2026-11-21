"""Hyperliquid metaAndAssetCtxs for the main dex and every HIP-3 dex: one row per dex."""

import time

from common import hl, hl_dexes


def run(state: dict) -> list[dict]:
    rows = []
    for dex in hl_dexes():
        meta, ctxs = hl({"type": "metaAndAssetCtxs", **({"dex": dex} if dex else {})})
        rows.append({"t": time.time(), "dex": dex, "names": [u["name"] for u in meta["universe"]], "ctxs": ctxs})
    return rows
