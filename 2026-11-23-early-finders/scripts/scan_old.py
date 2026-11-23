import sys; sys.path.insert(0,'.')
from rpc import *
O='0xc67e9efdb8a66a4b91b1f3731c75f500130373a4'
scan('arb','0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8',[TRANSFER,None,pad(O)],40000000,200000000,'cache/old_usdce.jsonl',span=500000,minspan=2000,maxspan=5000000)
