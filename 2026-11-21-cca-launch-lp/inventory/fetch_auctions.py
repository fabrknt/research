"""4 チェーン × 4 版の CCA factory から AuctionCreated を Blockscout v2 API(鍵なし)で全件取る。
usage: python3 fetch_auctions.py  -> data/auctions_raw.json"""
import json,urllib.request,time,sys
HOSTS={"ethereum":"eth.blockscout.com","base":"base.blockscout.com","arbitrum":"arbitrum.blockscout.com","unichain":"unichain.blockscout.com"}
FACT={"v2.1.0":"0x000000001F26a0044BaA66024e7b6599c61963F8","v2.0.0":"0x00cCa200BF124dBfA848937c553864f4B4CE0632",
      "v1.1.0":"0xCCccCcCAE7503Cac057829BF2811De42E16e0bD5","v1.0.0":"0x0000ccaDF55C911a2FbC0BB9d2942Aa77c6FAa1D"}
T="0x7ede475fad18ccf0039f2b956c4d43a8b4ed0853de4daaa8ae25299f331ae3b9"
def get(u):
    for k in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={"User-Agent":"research-script"}),timeout=60))
        except Exception as e: print("retry",u,e,file=sys.stderr); time.sleep(3)
out=[]
for ch,h in HOSTS.items():
    for v,f in FACT.items():
        u=f"https://{h}/api/v2/addresses/{f}/logs"; q=""; n=0
        while True:
            d=get(u+q)
            if not d: break
            for it in d.get("items",[]):
                if it["topics"][0]!=T: continue
                out.append(dict(chain=ch,ver=v,factory=f,block=it["block_number"],tx=it["transaction_hash"],
                    auction="0x"+it["topics"][1][26:],token="0x"+it["topics"][2][26:],data=it["data"],ts=it.get("block_timestamp")))
                n+=1
            p=d.get("next_page_params")
            if not p: break
            q="?"+"&".join(f"{k}={v2}" for k,v2 in p.items())
        print(ch,v,n,file=sys.stderr)
json.dump(out,open("data/auctions_raw.json","w"),indent=1)
print(len(out))
