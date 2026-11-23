import sys,datetime; sys.path.insert(0,'.')
from rpc import *
B='0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7'
end=find_block('arb',int(datetime.datetime(2024,5,1,tzinfo=datetime.timezone.utc).timestamp()),190000000,220000000)
print('may1 block',end,flush=True)
scan('arb','0xaf88d065e77c8cC2239327C5EDb3A432268e5831',[TRANSFER,None,pad(B)],156000000,end,'cache/b2_s1.jsonl',span=200000,minspan=2000,maxspan=3000000)
