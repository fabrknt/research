"""Decode a Lighter blob into per-account deltas.

Written from the blob schema in elliottech/lighter-prover desertexit/README.md, not from its code
(the prover is BUSL-1.1).
"""

import sys

BLOB_BYTES = 4096 * 32
VERSION_SIZE = 2
RESERVED_SIZE = 32
MARKETS = 255
MARK_PRICES_SIZE = MARKETS * 4
FUNDING_SIZE = MARKETS * 9
QUOTE_MULT_SIZE = MARKETS * 2


def pub_data(blob: bytes) -> bytes:
    """Drop byte 0 of every 32-byte field element: 4096 x 31 bytes."""
    if len(blob) != BLOB_BYTES:
        raise ValueError(f"blob is {len(blob)} bytes, want {BLOB_BYTES}")
    return bytes(b for i, b in enumerate(blob) if i % 32 != 0)


class Nibbles:
    """A stream of 4-bit limbs, low nibble of each byte first. A target is [n][n limbs, MSB first]."""

    def __init__(self, data: bytes):
        self.limbs = [x for b in data for x in (b & 0xF, b >> 4)]
        self.pos = 0

    def remaining(self) -> int:
        return len(self.limbs) - self.pos

    def target(self) -> int:
        n = self.limbs[self.pos]
        self.pos += 1
        v = 0
        for _ in range(n):
            v = (v << 4) | self.limbs[self.pos]
            self.pos += 1
        return v


def l1_address(chunks: list[int]) -> str:
    # The address is byte-reversed, then split into 7 / 7 / 6 byte little-endian chunks.
    rev = b"".join(c.to_bytes(8, "little")[:k] for c, k in zip(chunks, (7, 7, 6)))
    return "0x" + rev[::-1].hex()


def decode(blob: bytes) -> dict:
    pd = pub_data(blob)
    version = int.from_bytes(pd[0:2], "big")
    off = VERSION_SIZE + RESERVED_SIZE
    marks = [int.from_bytes(pd[off + 4 * i: off + 4 * i + 4], "big") for i in range(MARKETS)]
    off += MARK_PRICES_SIZE + FUNDING_SIZE + QUOTE_MULT_SIZE
    s = Nibbles(pd[off:])

    markets = []
    if version >= 1:
        for _ in range(s.target()):
            limb = s.target()
            public_index = s.target()
            m = {"market_index": limb & 0xFFF, "public_market_index": public_index}
            if version >= 2:
                m["status"] = (limb >> 12) & 0x3
                m["price"] = limb >> 14
                m["settlement_cap"] = s.target()
                m["quote_extension_multiplier"] = s.target()
            else:
                m["status"] = (limb >> 12) & 1
            markets.append(m)

    accounts = []
    index = 0
    first = True
    while s.remaining() > 1:
        diff = s.target()
        if diff == 0 and not first:
            break
        first = False
        index += diff
        a = {"account_index": index, "positions": {}, "binary_options": {}, "assets": {}, "shares": {}}

        flags = s.target()
        a["account_type"] = flags >> 2
        if flags & 1:
            a["l1_address"] = l1_address([s.target(), s.target(), s.target()])
        if flags & 2:
            signs = s.target()
            total, operator = s.target(), s.target()
            a["pool_info"] = {
                "total_shares": -total if signs & 2 else total,
                "operator_shares": -operator if signs & 1 else operator,
            }

        for _ in range(s.target()):
            mi = s.target()
            funding = s.target() | ((mi >> 8) << 60)
            v = s.target()
            pos = v >> 2
            a["positions"][mi & 0xFF] = {
                "position_delta": -pos if v & 2 else pos,
                "funding_prefix_sum_delta": -funding if v & 1 else funding,
            }

        if version >= 2:
            for _ in range(s.target()):
                mi = s.target()
                v = s.target()
                a["binary_options"][mi] = -(v >> 1) if v & 1 else v >> 1

        for _ in range(s.target()):
            lo = s.target()
            hi = s.target()
            asset = lo & 0x3F
            bal = (hi << 48) | (lo >> 7)
            a["assets"][asset] = -bal if (lo >> 6) & 1 else bal

        for _ in range(s.target()):
            v = s.target()
            amount = s.target()
            a["shares"][v >> 1] = -amount if v & 1 else amount

        accounts.append(a)

    return {"version": version, "mark_prices": marks, "markets": markets, "accounts": accounts,
            "unread_limbs": s.remaining()}


if __name__ == "__main__":
    d = decode(open(sys.argv[1], "rb").read())
    accts = d["accounts"]
    print("version", d["version"], "market deltas", len(d["markets"]), "accounts", len(accts),
          "with positions", sum(1 for a in accts if a["positions"]),
          "new addresses", sum(1 for a in accts if "l1_address" in a))
    idx = [a["account_index"] for a in accts]
    print("index range", idx[0] if idx else None, idx[-1] if idx else None, "sorted", idx == sorted(idx))
