"""Tokenized US shares on EVM chains, quoted through KyberSwap's free aggregator: the same round trip as
xstocks_quotes (buy $10k and $100k with the chain's dollar token, sell back what the buy would get), for every
issuer that has the share on BNB Chain, Ethereum, Arbitrum, Robinhood Chain and Monad.

Issuers: Backed's xStocks (one address on every EVM chain), Binance's bStocks (BNB Chain only), Ondo Global
Markets and Robinhood's own tokens (Robinhood Chain). Addresses are CoinGecko's platform lists (2026-11-23); on
Robinhood Chain, where many unrelated tokens reuse the tickers and even the "Robinhood Token" name, each is the
one candidate that routed $10k of USDG on 2026-11-23 (2026-11-23-xstocks-chains/robinhood_tokens.json).

On 2026-11-23 (Monday, before the US open) $25k of USDT bought 4.4 NVDAx on BNB Chain, so xStocks there have
next to no liquidity, while $10k on Robinhood Chain routed through Metric, TideFi and Fermi prop AMMs, Bebop and
a PMM besides Uniswap and Aerodrome. On Monad (added 2026-11-25) the xStocks are the same addresses (checked by
symbol() over Monad's RPC); at 11:07 UTC that Wednesday only NVDA, QQQ, SPY and TSLA routed $10k of USDC, through
Kuru's and Hanji's order books (via ERC-4626 wrappers), Uniswap v4: who quotes size, on which chain, in and out of US hours, is the question.

A round trip is answered by Kyber's route only (its sources, its routing); the route keeps each leg's exchange,
pool and amount so the venues can be read later. Calls are paced well under Kyber's free limit, and a share
whose $10k buy finds no route is not asked at $100k in that run.
"""

import json
import time

from common import fetch

KYBER = "https://aggregator-api.kyberswap.com/{chain}/api/v1/routes"
HEADERS = {"x-client-id": "fabrknt-research"}
# chain: (dollar token, decimals)
DOLLAR = {
    "bsc": ("0x55d398326f99059fF775485246999027B3197955", 18),        # USDT (BSC-USD)
    "ethereum": ("0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48", 6),    # USDC
    "arbitrum": ("0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6),    # USDC
    "robinhood": ("0x5fc5360d0400a0fd4f2af552add042d716f1d168", 6),   # USDG (Global Dollar)
    "monad": ("0x754704bc059f8c67012fed69bc8a327a5aafb603", 6),       # USDC
}
SIZES = (10_000, 100_000)
PAUSE = 0.5

# (chain, issuer, share): token address
TOKENS: dict[tuple[str, str, str], str] = {
    ("arbitrum", "xstocks", "AAPL"): "0x9d275685dc284c8eb1c79f6aba7a63dc75ec890a",
    ("arbitrum", "xstocks", "AMZN"): "0x3557ba345b01efa20a1bddc61f573bfd87195081",
    ("arbitrum", "xstocks", "COIN"): "0x364f210f430ec2448fc68a49203040f6124096f0",
    ("arbitrum", "xstocks", "CRCL"): "0xfebded1b0986a8ee107f5ab1a1c5a813491deceb",
    ("arbitrum", "xstocks", "GOOGL"): "0xe92f673ca36c5e2efd2de7628f815f84807e803f",
    ("arbitrum", "xstocks", "HOOD"): "0xe1385fdd5ffb10081cd52c56584f25efa9084015",
    ("arbitrum", "xstocks", "META"): "0x96702be57cd9777f835117a809c7124fe4ec989a",
    ("arbitrum", "xstocks", "MSFT"): "0x5621737f42dae558b81269fcb9e9e70c19aa6b35",
    ("arbitrum", "xstocks", "MSTR"): "0xae2f842ef90c0d5213259ab82639d5bbf649b08e",
    ("arbitrum", "xstocks", "NVDA"): "0xc845b2894dbddd03858fd2d643b4ef725fe0849d",
    ("arbitrum", "xstocks", "QQQ"): "0xa753a7395cae905cd615da0b82a53e0560f250af",
    ("arbitrum", "xstocks", "SPY"): "0x90a2a4c76b5d8c0bc892a69ea28aa775a8f2dd48",
    ("arbitrum", "xstocks", "TSLA"): "0x8ad3c73f833d3f9a523ab01476625f269aeb7cf0",
    ("bsc", "bstocks", "AAPL"): "0x431a3bee82e2ca41e49895cbece5bb0f76a89b7a",
    ("bsc", "bstocks", "AMZN"): "0x1a4b499833a79a09ad7cf1d42d7dacf71e92eb00",
    ("bsc", "bstocks", "COIN"): "0x585bde7c54abb5ccd7791f923d6c2187635f3952",
    ("bsc", "bstocks", "CRCL"): "0x80f3d493ebce97e343c53d29a137942416b4ffc0",
    ("bsc", "bstocks", "GOOGL"): "0x3f53de71c126bdabae20f9cd64848d317f6c3238",
    ("bsc", "bstocks", "HOOD"): "0xa394dcea3fd3847fd793afbfd163e2e3858b7c65",
    ("bsc", "bstocks", "META"): "0x7425889fe94f9d693e8daefe88bcced6acfef4c0",
    ("bsc", "bstocks", "MSFT"): "0x80106cb3ead06659a5ad19df39d9b4733863b9b0",
    ("bsc", "bstocks", "MSTR"): "0xe87afb3076aeb0f9b14e368de8145ae6a2826a14",
    ("bsc", "bstocks", "NVDA"): "0x02fca66c1d1afb4e2a7884261eb00f63598a7436",
    ("bsc", "bstocks", "QQQ"): "0x205812cdbed920aff76c6580abd681a46d11efc7",
    ("bsc", "bstocks", "SPY"): "0x7138b48df7d98d7e3cc221bfe7192d0a178182d8",
    ("bsc", "bstocks", "TSLA"): "0x5b1910eaad6450e50f816082aa078c41f10c292f",
    ("bsc", "ondo", "AAPL"): "0x390a684ef9cade28a7ad0dfa61ab1eb3842618c4",
    ("bsc", "ondo", "AMZN"): "0x4553cfe1c09f37f38b12dc509f676964e392f8fc",
    ("bsc", "ondo", "COIN"): "0xf8589b526fdd65f7f301c605a6e04f0f1b4b3620",
    ("bsc", "ondo", "CRCL"): "0x992879cd8ce0c312d98648875b5a8d6d042cbf34",
    ("bsc", "ondo", "GOOGL"): "0x091fc7778e6932d4009b087b191d1ee3bac5729a",
    ("bsc", "ondo", "HOOD"): "0x19601179a60f55ff6636f5d1a8b6671053bd60a8",
    ("bsc", "ondo", "META"): "0xd7df5863a3e742f0c767768cdfcb63f09e0422f6",
    ("bsc", "ondo", "MSFT"): "0x6bfe75d1ad432050ea973c3a3dcd88f02e2444c3",
    ("bsc", "ondo", "MSTR"): "0x7313ea16493b2f55054df0131a3a14b043ec8992",
    ("bsc", "ondo", "NVDA"): "0xa9ee28c80f960b889dfbd1902055218cba016f75",
    ("bsc", "ondo", "QQQ"): "0x0cde6936d305d5b34667fc46425e852efd73559a",
    ("bsc", "ondo", "SPY"): "0x6a708ead771238919d85930b5a0f10454e1c331a",
    ("bsc", "ondo", "TSLA"): "0x2494b603319d4d9f9715c9f4496d9e0364b59d93",
    ("bsc", "xstocks", "AAPL"): "0x9d275685dc284c8eb1c79f6aba7a63dc75ec890a",
    ("bsc", "xstocks", "AMZN"): "0x3557ba345b01efa20a1bddc61f573bfd87195081",
    ("bsc", "xstocks", "COIN"): "0x364f210f430ec2448fc68a49203040f6124096f0",
    ("bsc", "xstocks", "CRCL"): "0xfebded1b0986a8ee107f5ab1a1c5a813491deceb",
    ("bsc", "xstocks", "GOOGL"): "0xe92f673ca36c5e2efd2de7628f815f84807e803f",
    ("bsc", "xstocks", "HOOD"): "0xe1385fdd5ffb10081cd52c56584f25efa9084015",
    ("bsc", "xstocks", "META"): "0x96702be57cd9777f835117a809c7124fe4ec989a",
    ("bsc", "xstocks", "MSFT"): "0x5621737f42dae558b81269fcb9e9e70c19aa6b35",
    ("bsc", "xstocks", "MSTR"): "0xae2f842ef90c0d5213259ab82639d5bbf649b08e",
    ("bsc", "xstocks", "NVDA"): "0xc845b2894dbddd03858fd2d643b4ef725fe0849d",
    ("bsc", "xstocks", "QQQ"): "0xa753a7395cae905cd615da0b82a53e0560f250af",
    ("bsc", "xstocks", "SPY"): "0x90a2a4c76b5d8c0bc892a69ea28aa775a8f2dd48",
    ("bsc", "xstocks", "TSLA"): "0x8ad3c73f833d3f9a523ab01476625f269aeb7cf0",
    ("ethereum", "ondo", "AAPL"): "0x14c3abf95cb9c93a8b82c1cdcb76d72cb87b2d4c",
    ("ethereum", "ondo", "AMZN"): "0xbb8774fb97436d23d74c1b882e8e9a69322cfd31",
    ("ethereum", "ondo", "COIN"): "0xf042cfa86cf1d598a75bdb55c3507a1f39f9493b",
    ("ethereum", "ondo", "CRCL"): "0x3632dea96a953c11dac2f00b4a05a32cd1063fae",
    ("ethereum", "ondo", "GOOGL"): "0xba47214edd2bb43099611b208f75e4b42fdcfedc",
    ("ethereum", "ondo", "HOOD"): "0x998f02a9e343ef6e3e6f28700d5a20f839fd74e6",
    ("ethereum", "ondo", "META"): "0x59644165402b611b350645555b50afb581c71eb2",
    ("ethereum", "ondo", "MSFT"): "0xb812837b81a3a6b81d7cd74cfb19a7f2784555e5",
    ("ethereum", "ondo", "MSTR"): "0xcabd955322dfbf94c084929ac5e9eca3feb5556f",
    ("ethereum", "ondo", "NVDA"): "0x2d1f7226bd1f780af6b9a49dcc0ae00e8df4bdee",
    ("ethereum", "ondo", "QQQ"): "0x0e397938c1aa0680954093495b70a9f5e2249aba",
    ("ethereum", "ondo", "SPY"): "0xfedc5f4a6c38211c1338aa411018dfaf26612c08",
    ("ethereum", "ondo", "TSLA"): "0xf6b1117ec07684d3958cad8beb1b302bfd21103f",
    ("ethereum", "xstocks", "AAPL"): "0x9d275685dc284c8eb1c79f6aba7a63dc75ec890a",
    ("ethereum", "xstocks", "AMZN"): "0x3557ba345b01efa20a1bddc61f573bfd87195081",
    ("ethereum", "xstocks", "COIN"): "0x364f210f430ec2448fc68a49203040f6124096f0",
    ("ethereum", "xstocks", "CRCL"): "0xfebded1b0986a8ee107f5ab1a1c5a813491deceb",
    ("ethereum", "xstocks", "GOOGL"): "0xe92f673ca36c5e2efd2de7628f815f84807e803f",
    ("ethereum", "xstocks", "HOOD"): "0xe1385fdd5ffb10081cd52c56584f25efa9084015",
    ("ethereum", "xstocks", "META"): "0x96702be57cd9777f835117a809c7124fe4ec989a",
    ("ethereum", "xstocks", "MSFT"): "0x5621737f42dae558b81269fcb9e9e70c19aa6b35",
    ("ethereum", "xstocks", "MSTR"): "0xae2f842ef90c0d5213259ab82639d5bbf649b08e",
    ("ethereum", "xstocks", "NVDA"): "0xc845b2894dbddd03858fd2d643b4ef725fe0849d",
    ("ethereum", "xstocks", "QQQ"): "0xa753a7395cae905cd615da0b82a53e0560f250af",
    ("ethereum", "xstocks", "SPY"): "0x90a2a4c76b5d8c0bc892a69ea28aa775a8f2dd48",
    ("ethereum", "xstocks", "TSLA"): "0x8ad3c73f833d3f9a523ab01476625f269aeb7cf0",
    ("monad", "xstocks", "AAPL"): "0x9d275685dc284c8eb1c79f6aba7a63dc75ec890a",
    ("monad", "xstocks", "AMZN"): "0x3557ba345b01efa20a1bddc61f573bfd87195081",
    ("monad", "xstocks", "COIN"): "0x364f210f430ec2448fc68a49203040f6124096f0",
    ("monad", "xstocks", "CRCL"): "0xfebded1b0986a8ee107f5ab1a1c5a813491deceb",
    ("monad", "xstocks", "GOOGL"): "0xe92f673ca36c5e2efd2de7628f815f84807e803f",
    ("monad", "xstocks", "HOOD"): "0xe1385fdd5ffb10081cd52c56584f25efa9084015",
    ("monad", "xstocks", "META"): "0x96702be57cd9777f835117a809c7124fe4ec989a",
    ("monad", "xstocks", "MSFT"): "0x5621737f42dae558b81269fcb9e9e70c19aa6b35",
    ("monad", "xstocks", "MSTR"): "0xae2f842ef90c0d5213259ab82639d5bbf649b08e",
    ("monad", "xstocks", "NVDA"): "0xc845b2894dbddd03858fd2d643b4ef725fe0849d",
    ("monad", "xstocks", "QQQ"): "0xa753a7395cae905cd615da0b82a53e0560f250af",
    ("monad", "xstocks", "SPY"): "0x90a2a4c76b5d8c0bc892a69ea28aa775a8f2dd48",
    ("monad", "xstocks", "TSLA"): "0x8ad3c73f833d3f9a523ab01476625f269aeb7cf0",
    ("robinhood", "ondo", "AAPL"): "0x9bf86418caf2b7a939603d6c24219a77bf7f9b33",
    ("robinhood", "ondo", "CRCL"): "0x369c4748e98c153e9b7adebc3e71e9e2a5f60dc0",
    ("robinhood", "ondo", "GOOGL"): "0xe10cc5f0cd0c90322ebeb33e7757b2c9090146dc",
    ("robinhood", "ondo", "HOOD"): "0x43cac729218c62210d71d66b7f0ec93990d8d8cc",
    ("robinhood", "ondo", "META"): "0x7b5026cfcb4de0cf3d9a39fe2a541514b71437a2",
    ("robinhood", "ondo", "MSTR"): "0x09dedc334fc47ab543e5d70c7fd9d2b1aea175bd",
    ("robinhood", "ondo", "NVDA"): "0xf1b95ae4e7700b962714702ea53784dc8492a856",
    ("robinhood", "ondo", "QQQ"): "0x300fe8a40701ce81460503fb886f9ed81a3b5e14",
    ("robinhood", "ondo", "SPY"): "0x533c5571ae586985e1fddfaa24304284d970c62a",
    ("robinhood", "ondo", "TSLA"): "0xb197f36c25ba9b66960688882a4dc595c6b04309",
    ("robinhood", "robinhood", "AAPL"): "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9",
    ("robinhood", "robinhood", "CRCL"): "0xdf0992e440dd0be65bd8439b609d6d4366bf1cb5",
    ("robinhood", "robinhood", "GOOGL"): "0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3",
    ("robinhood", "robinhood", "MSFT"): "0xe93237c50d904957cf27e7b1133b510c669c2e74",
    ("robinhood", "robinhood", "MSTR"): "0xec262a75e413fafd0df80480274532c79d42da09",
    ("robinhood", "robinhood", "NVDA"): "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
    ("robinhood", "robinhood", "QQQ"): "0xd5f3879160bc7c32ebb4dc785f8a4f505888de68",
    ("robinhood", "robinhood", "SPY"): "0x117cc2133c37b721f49de2a7a74833232b3b4c0c",
    ("robinhood", "robinhood", "TSLA"): "0x322f0929c4625ed5bad873c95208d54e1c003b2d",
}


class NoRoute(Exception):
    pass


def _route(chain: str, tin: str, tout: str, amount: int) -> dict:
    """Kyber's routeSummary; NoRoute only for its explicit "route not found" (HTTP 400, code 4008)."""
    url = KYBER.format(chain=chain) + f"?tokenIn={tin}&tokenOut={tout}&amountIn={amount}"
    try:
        d = fetch(url, headers=HEADERS)
    except Exception as e:
        if getattr(e, "code", None) == 400:
            try:
                body = json.loads(e.read())
            except Exception:
                body = {}
            if body.get("code") == 4008:
                raise NoRoute() from None
        raise
    finally:
        time.sleep(PAUSE)
    if d.get("code") not in (0, None) or not (d.get("data") or {}).get("routeSummary"):
        return {}  # a malformed answer: _ask counts it as a failure (bad_answer)
    return d["data"]["routeSummary"]


def _ask(row: dict, chain: str, tin: str, tout: str, amount: int) -> tuple[dict, int]:
    """Fills row from one quote; returns (row, 1 if the call failed other than as no route)."""
    try:
        r = _route(chain, tin, tout, amount)
    except NoRoute:
        row["err"] = "no_route"
        return row, 0
    except Exception as e:
        row["err"] = type(e).__name__
        return row, 1
    try:
        out = int(r["amountOut"])
        paths = r["route"]
        if not (isinstance(paths, list) and paths and all(isinstance(p, list) and p and
                all(isinstance(s, dict) and s.get("exchange") for s in p) for p in paths)):
            raise ValueError("route")
        route = [(s.get("exchange"), s.get("pool"), s.get("swapAmount")) for p in paths for s in p]
    except Exception:
        out = 0
    if out <= 0:  # a malformed answer (nothing out, bad route list), not Kyber's explicit no-route
        row["err"] = "bad_answer"
        return row, 1
    row |= {"out": out, "in_usd": r.get("amountInUsd"), "out_usd": r.get("amountOutUsd"), "route": route}
    return row, 0


def run(state: dict) -> list[dict]:
    rows, failed, asked = [], 0, 0
    for (chain, issuer, share), token in TOKENS.items():
        dollar, dec = DOLLAR[chain]
        for usd in SIZES:
            base = {"kind": "quote", "chain": chain, "issuer": issuer, "share": share, "usd": usd}
            buy, f = _ask({"t": time.time(), "side": "buy", "amount": usd * 10**dec} | base,
                          chain, dollar, token, usd * 10**dec)
            rows.append(buy)
            failed, asked = failed + f, asked + 1
            if "out" not in buy:
                break  # no route for $10k: don't ask $100k this run
            sell, f = _ask({"t": time.time(), "side": "sell", "amount": buy["out"]} | base,
                           chain, token, dollar, buy["out"])
            rows.append(sell)
            failed, asked = failed + f, asked + 1
    if asked and failed == asked:
        raise RuntimeError("every call failed")
    state["status"] = {"incomplete": failed > asked / 4, "failed_quotes": failed}
    return rows
