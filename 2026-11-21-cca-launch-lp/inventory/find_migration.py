"""graduated のオークションごとに、funds の受け手(=LBP strategy)のログから migrate の tx を探し、
receipt の PoolManager Initialize / ModifyLiquidity から v4 の poolId・hook・初期価格・LP の位置を読む。
usage: python3 find_migration.py CHAIN [MIN_RAISE_USD] -> data/migr_CHAIN.json"""
import json,sys,rpc,logs,datetime,bisect
from eth_abi import decode
ch=sys.argv[1]; MINUSD=float(sys.argv[2]) if len(sys.argv)>2 else 1000
INIT="0xdd466e674ea557f56295e2d0218a125ea4b4f0f6f3307b95f85e6110838d6438"; MODL="0xf208f4912782fd25c7f114ca3723a2d5dd6f3bcc3ac8db5af63baa85f711d5ec"
PM=logs.PM[ch].lower()
WIN={"ethereum":7200*30,"unichain":86400*30,"arbitrum":345600*30,"base":43200*3}[ch]   # base は 1000 ブロック刻みなので 3 日に絞る
eth=json.load(open("data/eth_usd_daily.json"))["prices"]; ET=[p[0]/1000 for p in eth]
def ethusd(t): i=max(0,min(len(ET)-1,bisect.bisect_left(ET,t))); return eth[i][1]
STABLE={"USDC","USDT","USD₮0","USDT0","DAI","USDS"}
def usd(a,t):
    x=(a["currencyRaised"] or 0)/10**(a["curDec"] or 18)
    if a["curSym"] in ("ETH","WETH"): return x*ethusd(t)
    if a["curSym"] in STABLE: return x
    return None
def btime(n):
    return int(rpc.call(ch,"eth_getBlockByNumber",[hex(n),False],tries=4)["timestamp"],16)
A=[a for a in json.load(open("data/auctions.json")) if a["chain"]==ch and a.get("isGraduated")==1]
head=rpc.bn(ch); out=[]
import collections
shared=collections.Counter(x["fundsRecipient"].lower() for x in json.load(open("data/auctions.json")) if x["chain"]==ch)
for a in A:
    a["endTime"]=btime(min(a["endBlock"],head)); a["startTime"]=btime(min(a["startBlock"],head)); a["raisedUSD"]=usd(a,a["endTime"])
    if "(偽)" in (a["curSym"] or "") or (a["raisedUSD"] is not None and a["raisedUSD"]<MINUSD): continue
    if a["endBlock"]>head: a["status"]="live"; out.append(a); continue
    a["migr"]=None
    chunk=WIN if ch in logs.API else {"base":10000,"arbitrum":1000000,"unichain":500000}[ch]
    b=a["endBlock"]; lim=min(a["endBlock"]+WIN,head)
    while b<=lim and a["migr"] is None:      # RPC のチェーンは区間を少しずつ進め、見つかったら止める
        e=min(b+chunk-1,lim)
        lg=logs.get_logs(ch,[],b,e,address=a["fundsRecipient"])
        txs=[]; [txs.append(l["tx"]) for l in lg if l["tx"] not in txs]
        for h in txs:
            try: r=rpc.call(ch,"eth_getTransactionReceipt",[h],tries=4)
            except Exception as e:
                # arb1 が古い receipt を解けないことがある -> 同じブロックの PoolManager ログから組み立てる
                n=next(l["n"] for l in lg if l["tx"]==h)
                pl=rpc.call(ch,"eth_getLogs",[dict(address=logs.PM[ch],fromBlock=hex(n),toBlock=hex(n))],tries=4)
                r=dict(blockNumber=hex(n),from_="?",logs=[x for x in pl if x["transactionHash"]==h])
                print("receipt fallback",h,len(r["logs"]),file=sys.stderr)
            ini=[l for l in r["logs"] if l["address"].lower()==PM and l["topics"][0]==INIT]
            if not ini: continue
            l=ini[0]; c0="0x"+l["topics"][2][26:]; c1="0x"+l["topics"][3][26:]
            # 共有の strategy(v3 の singleton)では他のオークションの migrate も混じる -> token が一致する時だけ採る
            if shared[a["fundsRecipient"].lower()]>1 and a["token"].lower() not in (c0,c1): continue
            fee,ts,hook,sp,tick=decode(["uint24","int24","address","uint160","int24"],bytes.fromhex(l["data"][2:]))
            pid=l["topics"][1]
            mods=[]
            for m in r["logs"]:
                if m["address"].lower()==PM and m["topics"][0]==MODL and m["topics"][1]==pid:
                    tl,tu,ld,salt=decode(["int24","int24","int256","bytes32"],bytes.fromhex(m["data"][2:])); mods.append([tl,tu,ld])
            a["migr"]=dict(tx=h,block=int(r["blockNumber"],16),from_=r.get("from","?"),poolId=pid,currency0=c0,currency1=c1,fee=fee,tickSpacing=ts,hooks=hook,sqrtPriceX96=sp,tick=tick,positions=mods)
            break

        b=e+1
    a["status"]="migrated" if a["migr"] else "no_migration_found"
    print(a["tokSym"],a["curSym"],round(a["raisedUSD"] or -1),a["status"],a["migr"] and a["migr"]["poolId"],file=sys.stderr,flush=True)
    out.append(a)
json.dump(out,open(f"data/migr_{ch}.json","w"),indent=1)
