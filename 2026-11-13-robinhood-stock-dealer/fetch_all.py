"""v4 の Swap を期間でまとめて取り、data/pools.json(対象 9 銘柄を片側に持つプール)の分だけ CSV に残す。

公開 RPC は 1 回 1 万件までなので、1.2 万ブロック(約 20 分)ずつ取る。
使い方: python3 fetch_all.py <日数>
"""
import csv, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from rpc import call, logs

PM = "0x8366a39CC670B4001A1121B8F6A443A643e40951"
SWAP = "0x40e9cecb9f5f1f1c5b9c97dec2917b7ee92e57ba5563708daca94dd84ad7112f"
STEP = 12_000


def s128(w):
    v = int(w, 16)
    return v - 2**256 if v >= 2**255 else v


if __name__ == "__main__":
    days = float(sys.argv[1])
    ids = {p["id"] for p in json.load(open("data/pools.json"))}
    head = int(sys.argv[2]) if len(sys.argv) > 2 else int(call("eth_blockNumber", []), 16)
    start = head - int(days * 86400 / 0.1047)
    chunks = [(a, min(a + STEP - 1, head)) for a in range(start, head + 1, STEP)]
    print("blocks", start, head, "chunks", len(chunks), file=sys.stderr)

    def get(ch):
        out = []
        for l in logs(PM, [SWAP], ch[0], ch[1], step=STEP):
            if l["topics"][1] not in ids:
                continue
            d = l["data"][2:]
            w = [d[i:i + 64] for i in range(0, len(d), 64)]
            out.append((int(l["blockNumber"], 16), l["topics"][1], "0x" + l["topics"][2][26:],
                        s128(w[0]), s128(w[1]), int(w[5], 16), l["transactionHash"]))
        return out

    # 区間ごとに data/chunks/ に書き、止まっても続きから取れるようにする。
    os.makedirs("data/chunks", exist_ok=True)

    def run(ch):
        path = f"data/chunks/{ch[0]}.csv"
        if os.path.exists(path):
            return 0
        rows = get(ch)
        with open(path + ".tmp", "w", newline="") as f:
            csv.writer(f).writerows(rows)
        os.replace(path + ".tmp", path)
        return len(rows)

    t0 = time.time()
    with ThreadPoolExecutor(2) as ex:
        for i, k in enumerate(ex.map(run, chunks)):
            if i % 50 == 0:
                print(i, len(chunks), round(time.time() - t0), file=sys.stderr, flush=True)
    with open("data/all_swaps.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["block", "pool", "sender", "a0", "a1", "fee", "tx"])
        for ch in chunks:
            wr.writerows(csv.reader(open(f"data/chunks/{ch[0]}.csv")))
    print("done", file=sys.stderr)
