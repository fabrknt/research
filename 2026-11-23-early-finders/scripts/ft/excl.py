import json,re
KW=['pool','pair','router','swap','aggregat','bridge','gateway','diamond','settler','settlement','multicall','forwarder','relayer','spoke','messenger','tokenminter','circle','proxytomeson','layerzero','wormhole','stargate','socket','across','mayan','rhino','owlto','layerswap','meson','squid','rango','xy finance','symbiosis','synapse','li.fi','lifi','interport','orbiter','relay','1inch','mev bot','null','burn','fee collector','fees','opensea','cow protocol','zerion','debank','rubic','rainbow','odos','kyber','paraswap','gnosissafe','multisig','airdrop claim','donateandclaim','hyperliquid','dln','deswa','allbridge','cctp','adapter','zap','helper','hypervisor','memecoin trader','superform','galxe','permit','dodo','fusion','woofi','arbswap','clipper','beefy','token bridge','assetforwarder','bridging','crosschain','cross chain','tokenmessenger','universalrouter','camelot','sushi','uniswap','pancake','algebra','traderjoe','trader joe','lizard','ramses','curve','balancer']
def label(L,a):
    v=L.get(a,{}); tags=[t[0] or '' for t in v.get('tags',[])]+[t[2] or '' for t in v.get('tags',[])]
    return ((v.get('sourcify') or '')+' | '+';'.join(dict.fromkeys(tags)))
def excluded(L,a):
    s=label(L,a).lower()
    if a.lower() in ('0x0000000000000000000000000000000000000000',): return True
    if 'aevo' in s or 'orderly' in s: return False
    return any(k in s for k in KW)
