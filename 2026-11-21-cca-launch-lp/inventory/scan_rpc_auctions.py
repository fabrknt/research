"""Base と Arbitrum は Blockscout が Cloudflare/403 で引けないので、公開 RPC の eth_getLogs を区間に分けて AuctionCreated を集める。
usage: python3 scan_rpc_auctions.py CHAIN -> data/auctions_rpc_CHAIN.json"""
import json,sys,rpc,concurrent.futures as cf
ch=sys.argv[1]
T="0x7ede475fad18ccf0039f2b956c4d43a8b4ed0853de4daaa8ae25299f331ae3b9"
F={"v2.1.0":"0x000000001F26a0044BaA66024e7b6599c61963F8","v2.0.0":"0x00cCa200BF124dBfA848937c553864f4B4CE0632",
   "v1.1.0":"0xCCccCcCAE7503Cac057829BF2811De42E16e0bD5","v1.0.0":"0x0000ccaDF55C911a2FbC0BB9d2942Aa77c6FAa1D"}
idx={"base":0,"arbitrum":1}[ch]; step={"base":1000,"arbitrum":100000}[ch]
start=int(sys.argv[2]); head=int(rpc.call(ch,"eth_blockNumber",[],i=idx),16)-50
rng=[(b,min(b+step-1,head)) for b in range(start,head+1,step)]
inv={v.lower():k for k,v in F.items()}
def one(r):
    return rpc.call(ch,"eth_getLogs",[dict(address=list(F.values()),topics=[T],fromBlock=hex(r[0]),toBlock=hex(r[1]))],i=idx,tries=8)
out=[]
with cf.ThreadPoolExecutor(int(sys.argv[3]) if len(sys.argv)>3 else 4) as ex:
    for k,res in enumerate(ex.map(one,rng)):
        for it in res:
            out.append(dict(chain=ch,ver=inv[it["address"].lower()],factory=it["address"],block=int(it["blockNumber"],16),tx=it["transactionHash"],
                auction="0x"+it["topics"][1][26:],token="0x"+it["topics"][2][26:],data=it["data"],ts=None))
        if k%100==0: print(k,len(rng),len(out),file=sys.stderr,flush=True)
json.dump(dict(start=start,head=head,items=out),open(f"data/auctions_rpc_{ch}.json","w"),indent=1)
print(ch,len(out),start,head)
