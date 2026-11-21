"""Robinhood stock token -> Hyperliquid xyz (HIP-3) coin. 60 names match by symbol (RH asset list from
~/src/rh-measure/data/rhj_assets.json, 2026-11-13, x xyz meta on 2026-11-21); SPY and QQQ map to the
xyz index perps SP500 and XYZ100 with a fitted ratio k, as in ../2026-11-13-robinhood-stock-dealer/analyze.py."""
SAME = ['AAOI', 'AAPL', 'AMAT', 'AMD', 'AMZN', 'ASML', 'AVGO', 'BABA', 'BB', 'BE', 'BMNR', 'CBRS', 'COIN', 'COST',
        'CRCL', 'CRWD', 'CRWV', 'DELL', 'EWT', 'EWY', 'GEV', 'GLW', 'GME', 'GOOGL', 'HIMS', 'IBM', 'INTC', 'IREN',
        'LITE', 'LLY', 'LRCX', 'META', 'MRNA', 'MRVL', 'MSFT', 'MSTR', 'MU', 'NBIS', 'NET', 'NFLX', 'NOW', 'NVDA',
        'ORCL', 'PANW', 'PLTR', 'QCOM', 'RDDT', 'RIVN', 'RKLB', 'SKHY', 'SMH', 'SNDK', 'SPCX', 'TSLA', 'TSM', 'TTWO',
        'UMC', 'USAR', 'WDC', 'ZM']
HL_COIN = {s: s for s in SAME}
HL_COIN.update({"SPY": "SP500", "QQQ": "XYZ100"})
