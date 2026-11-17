"""USDC transfers from Lighter's contract (ZkLighter) to given addresses on Ethereum.

usage: transfers.py FROM_BLOCK ADDRESS...
"""

import sys

from rpc import TOPIC_TRANSFER, USDC, ZKLIGHTER, logs, utc


def topic(address: str) -> str:
    return "0x" + address.lower().removeprefix("0x").rjust(64, "0")


def main(from_block: int, addresses: list[str]) -> None:
    for addr in addresses:
        found = logs(USDC, [TOPIC_TRANSFER, topic(ZKLIGHTER), topic(addr)], from_block, "latest")
        print(f"to {addr}: {len(found)} transfers")
        for log in found:
            print(f"  block {int(log['blockNumber'], 16)} {utc(int(log['blockTimestamp'], 16))} "
                  f"{int(log['data'], 16) / 1e6:,.2f} USDC tx {log['transactionHash']}")


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2:])
