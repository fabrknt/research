import sys; sys.path.insert(0,'.')
from rpc import *
F='0x0F820B9afC270d658a9fD7D16B1Bdc45b70f074C'
end=int(call('arb','eth_blockNumber',[]),16)
scan('arb',F,['0x0b33722ea9d97f05fb7128e0987e4060c182350308a3d0a19f8ec53512fe1493'],300000000,end,'cache/var_pools.jsonl',span=2000000,minspan=5000,maxspan=10000000)
