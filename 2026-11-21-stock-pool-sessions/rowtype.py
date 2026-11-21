"""Compact row for data/rows.pkl (slots instead of dicts: ~2M swaps)."""


class Row:
    __slots__ = ("t", "pool", "sym", "qsym", "usdq", "usd", "side", "fee", "hooks", "fables", "sender", "tx",
                 "sess", "bell", "lp", "pool_lp", "d_bp", "toward", "blk")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def __getitem__(self, k):
        return getattr(self, k)
