# Do early Hyperliquid finders also find later winners early?

Research test, 2026-11-23. Public on-chain data and public APIs only. Nothing was committed, posted or sent.

## Verdict (plain)

**There is a lift, and it is solid. As a stand-alone trading signal it is weak.**

How the cohort was picked: wallets whose first deposit of $100 or more into the HL bridge came before HL's points program (2023-11-01). The selection used HL data only. These wallets reached the later winners early much more often than wallets that first came to HL in H1 2025:

- **Lighter**, before its public launch (2025-10-02): **11.2%** for the early cohort vs **4.1%** for the late one. Lift **2.75×**, 95% CI 1.84–4.12.
- **Variational Omni**, before its points program began (2025-12-17): **8.1%** vs **1.8%**. Lift **4.5×**, CI 2.5–8.3.
- Looking only at the deepest-beta window makes the gap larger. For Lighter before 2025-06-01, it is 5.3% vs 0.8%, lift **6.4×**, CI 2.6–15.7.
- There is a clean gradient. The points-season-1 cohort (Nov 2023 to Apr 2024) falls in between: Lighter 6.8%, Variational 3.7%.
- The lift holds after:
  - dropping wallets flagged by the farmer heuristics: 2.6× for Lighter, 4.3× for Variational;
  - matching on deposit size;
  - restricting to EOAs.
- Arbitrum wallets that were active in Oct 2023 but never touched HL almost never found either protocol: 0.3%.

**Confidence.**
- The association itself: **high**. The intervals are well above 1, and the gradient and the robustness checks all agree.
- Usefulness as "follow the early finders": **low to moderate**, for four reasons.
  1. I tested 2 winners and **0 losers**. I could not measure how often this cohort also crowds into protocols that later fail. That is the false-positive rate, and it decides whether the signal is usable.
  2. The share is low in absolute terms. About 89% of early HL wallets did *not* find Lighter early.
  3. The cohort is ~0.4% of Lighter's pre-launch accounts. The signal is concentrated at the *very* start: an estimated ~7% of Lighter's first ~450 accounts, and 5 of Variational's first 176 pools. Later it fades into the crowd.
  4. Both later protocols are perp DEXs, like HL. This shows "early perp-DEX adopters adopt the next perp DEX early". It does not show general alpha-finding.

So the idea does **not** stop. It also does not graduate to a live signal until a loser test exists (Section 8).

## 1. Verified contracts and their sources

| Protocol | Contract | Chain | Token | How verified |
|---|---|---|---|---|
| Hyperliquid, legacy bridge ("Bridge1") | `0xc67e9efdb8a66a4b91b1f3731c75f500130373a4` | Arbitrum | USDC.e `0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8` | The DefiLlama HL adapter at commit `5b50d8bf` (2023-04-18) lists it as the only HL TVL holder. The adapter at commit `fada8297` (2023-12-14) lists it next to Bridge2. On-chain, USDC.e transfers into it run from 2023-02-26 (block 64,815,178) to 2024-01-27: 55,413 transfers from 25,221 senders. Arbiscan returned 403, so I could not view its verified-source page. |
| Hyperliquid Bridge2 | `0x2Df1c51E09aECF9cacB7bc98cB1742757f163dF7` | Arbitrum | native USDC `0xaf88d065e77c8cC2239327C5EDb3A432268e5831` | Official HL docs (gitbook, "Bridge2" page: native USDC, minimum 5 USDC, now marked legacy in favor of CCTP). Source is `hyperliquid-dex/contracts` Bridge2.sol, with audit commits from Jul to Nov 2023. rotki's constants and the DefiLlama adapter agree. On-chain, the first inbound USDC is at block 156,001,186 (2023-12-02). |
| Lighter ZkLighter (proxy) | `0x3B4D794a66304F130a4Db8F2551B0070dfCf5ca7` | Ethereum L1 | USDC | Blockscout ETH: verified, tagged "Lighter: ZkLighter", implementation `0x94E1f6d3e0c6fC3966747879299A089baF76A80F`. Lighter API docs describe the `deposit` method on mainnet, and the L2Beat config agrees. Deposit events: `Deposit(uint48 toAccountIndex,address toAddress,uint128 amount)` until about Dec 2025, then `Deposit(uint48,address,uint16,uint8,uint128)`. The first deposits are around 2025-01-17. |
| Variational Settlement Pool Factory | `0x0F820B9afC270d658a9fD7D16B1Bdc45b70f074C` | Arbitrum | USDC | Official Variational docs, "Mainnet Contracts" page. The same page lists the Core OLP Vault `0x74bbbb0e7f0bad6938509dd4b556a39a4db1f2cd`, the Treasury `0x5e91…d645` and the Oracle `0x84BE…6172`. Event: `PoolCreated(address creator, address[] parties, …)`. All 211,915 pools were created by the Core OLP Vault, so they are all Omni pools, one per user, each an EIP-1167 clone. The first pool is from 2025-01-30. |

**How Variational deposits work.** The docs and on-chain checks agree. The user signs an EIP-2612 permit, the relayer creates a pool for that user, and USDC then moves from the user, through an intermediary, into the pool. The `parties[]` array in `PoolCreated` holds the user's own address, an EOA in every case I checked. So the timestamp of a user's first `PoolCreated` is when they onboarded to Omni.

**How Lighter is measured.** Free Ethereum RPCs either refuse historical `eth_getLogs` (publicnode requires a token) or cap the range at 10 to 800 blocks. So I did not scan L1 Transfer logs. I used two other sources instead:
- Lighter's public API, `GET /api/v1/accountsByL1Address`, which returns the wallet's main account index.
- A calibration of account index against date, built from ZkLighter Deposit events read through Blockscout's keyless API at about 90 dates. The index is assigned in order of creation.

This also counts Lighter deposits that arrived through its multi-chain fast bridge, because the solver deposits on L1 to the user's address.

## 2. Key dates

| Protocol | Date | Event | Source |
|---|---|---|---|
| HL | 2023-02-26 | First deposit to the legacy bridge (closed alpha) | on-chain |
| HL | **2023-11-01** | Points program begins; closed-alpha points ran through 2023-10-31 | HL docs, "Points" page |
| HL | 2023-12-02 | Bridge2 live (first native-USDC deposit) | on-chain |
| HL | 2024-05-01 | End of points season 1 (6 months of 1M points per week) | HL docs |
| HL | 2024-11-29 | HYPE genesis and airdrop | The Block, Cointelegraph |
| Lighter | ~2025-01-17 | First L1 deposits (private beta; Season 1 points ran during the beta) | on-chain |
| Lighter | 2025-09-30 | Season 1 ends | press (Blockworks, Odaily) |
| Lighter | **2025-10-02** | Public mainnet; Season 2 begins | Blockworks and others |
| Lighter | 2025-12-30 | LIT token | The Block |
| Variational Omni | 2025-01-30 | First Omni pool (invite-only private beta) | on-chain |
| Variational | **2025-12-17** | Points program begins (retroactive to 2025-12-11) | press (CryptoBriefing and others) |
| Variational | 2026-11-11 | Private beta ends; public mainnet, no invite code needed | RootData, Odaily |
| Variational | Q4 2026 (pending) | VAR token generation event, not yet happened | CryptoBriefing |

## 3. Groups and filters (sizes)

All groups were chosen without looking at Lighter or Variational.

**A: early HL** (first bridge deposit before 2023-11-01, the points start).
- 25,221 unique senders ever used the legacy bridge.
- 13,863 had a first deposit before 2023-11-01.
- **6,385** remain after the dust filter, which requires a deposit of $100 or more before 2023-11-01. The filter removed 7,478 wallets (54%), which is a lot of dust and probing.
- Lighter can only be checked one wallet at a time through its API, so I tested a random **2,000** wallets. Variational was tested on all 6,385 (see the robustness section).
- All 2,000 tested wallets are EOAs: 1,824 plain and 176 now delegated under EIP-7702. None are contract wallets.

**B, second cut: HL points season 1** (first deposit 2023-11-01 to 2024-04-30, across both bridges).
- 125,274 wallets.
- 86,690 remain after the ≥$100 filter, which removed 38,584.
- I tested a random **600**.

**Late HL, control 1** (first-ever HL activity in H1 2025).
- I took Bridge2 deposits on six sampled days, the 15th of each month from Jan to Jun 2025: 26,180 transfers.
- 16,464 senders had not deposited before May 2024.
- 10,371 remain after the ≥$100 filter, which removed 6,093.
- I checked 2,600 random ones against the HL API ledger (`userNonFundingLedgerUpdates`, which covers all deposit routes and internal transfers back to Feb 2023).
- 1,986 of them (76%) had *earlier* HL activity, so they are not late.
- That leaves **614** truly-new 2025 wallets.

**Control 2** (active on Arbitrum in Oct 2023 but never on HL).
- Senders of ≥$100 USDC or USDC.e in two 3-hour windows (2023-10-10 and 2023-10-20, 12:00–15:00 UTC): 3,625 wallets.
- 3,178 were not HL depositors through April 2024.
- I sampled 2,400; 1,737 of those were plain EOAs.
- I checked 800 on the HL API; 690 had **zero HL ledger events ever**.
- That gives **690** wallets.

## 4. Outcome table

The Lighter and Variational columns use the same tested wallets.

| Group | n | Lighter before public launch (2025-10-02) | Lighter before 2025-06-01 | Lighter ever | Variational before points (2025-12-17) | Variational before 2025-09-01 | Variational ever | Early on both |
|---|---|---|---|---|---|---|---|---|
| A: early HL (pre-points) | 2,000 | **224 (11.2%)** [9.9–12.7] | 105 (5.3%) | 321 (16.1%) | **162 (8.1%)** [7.0–9.4] | 31 (1.6%) | 310 (15.5%) | 87 (4.4%) |
| B: HL points S1 | 600 | 41 (6.8%) [5.1–9.1] | 20 (3.3%) | 68 (11.3%) | 22 (3.7%) [2.4–5.5] | 5 (0.8%) | 58 (9.7%) | 15 |
| Late HL (2025 H1) | 614 | 25 (4.1%) [2.8–5.9] | 5 (0.8%) | 41 (6.7%) | 11 (1.8%) [1.0–3.2] | 4 (0.7%) | 26 (4.2%) | 6 |
| Control: Arbitrum, never HL | 690 | 2 (0.3%) [0.1–1.1] | 1 | 4 (0.6%) | 2 (0.3%) [0.1–1.1] | 0 | 3 (0.4%) | 1 |

Brackets are Wilson 95% intervals.

**Lift vs Late HL** (risk ratio, Katz log 95% CI):

| | Lighter early | Variational early | Lighter (strict, before Jun 2025) | Variational (strict, before Sep 2025) | Lighter ever |
|---|---|---|---|---|---|
| A vs Late | **2.75** (1.84–4.12) | **4.52** (2.47–8.27) | **6.4** (2.6–15.7) | 2.4 (0.8–6.7), not significant | 2.40 (1.76–3.28) |
| B vs Late | 1.68 (1.03–2.72) | 2.05 (1.00–4.18) | | | 1.70 (1.17–2.46) |
| A vs Control 2 | ~39× | ~28× | | | |

**Median lead time among wallets that were early.** Lighter dates come from the index-to-date calibration, which has about 4-day resolution. CIs are bootstrapped.

| Group | Lighter: days before public launch | Variational: days before points start | Variational: days before public launch |
|---|---|---|---|
| A | 115 [96–134] (n=224) | 62 (n=162) | 391 [387–398] |
| B | 117 [94–144] (n=41) | 54 (n=22) | 383 [373–394] |
| Late | 96 [14–108] (n=25) | 81 (n=11) | 410 [380–476] |

How to read this: *among the wallets that did find the new protocol early*, the cohorts arrived at roughly similar times. The difference is mostly in the **hit rate**, not in how early they came. The exception is the deep beta. 47% of the early cohort's Lighter finders arrived before 2025-06-01, against 20% for Late.

**Cohort convergence on the new protocols** (useful for a watcher).
- **Lighter.** Of the 2,000 tested A wallets, the 10th one arrived on 2025-03-08, when Lighter had about 453 accounts. Scaled to the full cohort, that is about 7% of Lighter's first ~450 accounts.
  - The 50th arrived on 2025-04-13, at about 5.4k accounts.
  - The 100th arrived on 2025-05-25, at about 17k accounts.
  - By the public launch, the early cohort was about 0.4% of roughly 169k accounts.
- **Variational** (full A cohort):
  - 5 A wallets were among the first 176 Omni pools, by 2025-02-23.
  - 10 among the first 855.
  - 50 among the first ~4,250, by 2025-06-05.
  - Overall, the cohort is 0.5% of 210k pools.

## 5. Robustness

- **Full cohort, Variational** (no sampling, local data): A is 497/6,385 = **7.8%** [7.2–8.5]. B (all 86,690) is 2.7%. The unverified late candidates (10,371) are 3.6%, but that set includes the 76% who were not actually new.
- **Size matching** (first qualifying deposit):
  - ≥$1k: A (n=524) is Lighter 10.3%, Variational 6.5%. Late (n=224) is 6.7%, 2.7%. The lift is weaker here: about 1.5× for Lighter (CIs overlap) and 2.4× for Variational.
  - $100–1k: A (1,476) is 11.5%, 8.7%. Late (390) is 2.6%, 1.3%, a lift of 4–7×.
  - So the lift is real, but much of it comes from small early wallets vs small late wallets. Large late wallets come closer to the early cohort.
- **EOA only:** the late EOAs that were checked (406 of 614) give Lighter 3.9%, a lift of 2.84 (1.73–4.67), and Variational a lift of 4.70 (2.22–9.94). A and B are all EOAs.
- **Variational "pool created" vs "funded":** I sampled 150 pre-points pools from A and 150 from Late.
  - Within about 4 days of creation, the pool received ≥$100 for 96/150 in A (median $760) and 86/150 in Late (median $220).
  - About two-thirds of pools were funded in both groups. Some are funded later, outside my window. The ratio between groups does not change.

## 6. Farmers

Four flags were used:
- Tiny repeated deposits: 3 or more HL deposits under $50.
- Burst clusters: 4 or more wallets with the same first-deposit amount (rounded to $1) in the same UTC hour.
- Shared small-EOA funder: the USDC source in the ~12 days before the first deposit is an EOA with a low nonce that also funded other cohort wallets.
- Arbitrum nonce ≥ 3,000.

**Results:**
- On the full A cohort: 213 tiny-repeaters and 109 in burst clusters. Of the 2,000 tested, 104 are flagged.
- On the funding and nonce sample: 400 A wallets, 274 of which were also tested on Lighter.
  - Shared small-EOA funder: 7/400, in two clusters of 2 and 5 wallets.
  - Everything else that showed up as a shared source was a router, a bridge or a CEX contract, or a USDC mint.
  - Nonce ≥ 3,000: 7 of the 274. The median nonce is 192.
  - Any flag: 29/274 (11%).
- **Flagged wallets are far more likely to show up early.** Lighter early is 25–38% for flagged wallets vs about 11% for unflagged ones.
- **The lift survives dropping them.** A minus tiny/burst (n=1,896) gives Lighter 10.4% and Variational 7.6%. That is lift 2.56 (1.71–3.85) and 4.27 (2.33–7.83) vs Late. I did not apply farmer filters to the late group, which makes this conservative.
- "Distinct contracts touched" was **not measured**. Arbiscan and Arbitrum Blockscout block keyless clients through Cloudflare, and there is no free tx-list source.
- Sybils funded with ETH, or through CEX withdrawals, are invisible to the funder heuristic.

## 7. Assumptions and gaps

1. **The Lighter timing is inferred, not observed per deposit.** "Early" means the wallet's main Lighter account index is ≤ 169,322, the index envelope at 2025-10-02. The index is assigned in order of creation, and the calibration has about 4-day resolution. Its tail runs a little low: deposits seen near a date may not include the newest accounts. Lighter's own count was ~188k beta accounts, close to this.
   - This measures account creation (first deposit). It does not apply a ≥$100 test to the Lighter deposit itself.
2. **Lighter address matching.** An HL address is matched to the same Lighter L1 address. Every tested HL wallet is an EOA, so the same address on Arbitrum and Ethereum is the same key holder. People who used a *different* wallet on Lighter are missed, the same way in every group.
3. **The HL cohort uses Transfer `from` addresses.** Bridge2 and the legacy bridge credit the sender, including permit deposits. Deposits made through a contract wallet would be credited to that contract.
4. **"First deposit" for A and B** is the first on-chain deposit to either bridge. A few wallets got their first USDC by an internal HL transfer before any on-chain deposit; the HL API showed this for one case.
   - **The late cohort's firstness** was checked against the full HL ledger, which is stricter.
5. **The late cohort is a sample of 6 calendar days in H1 2025**, not all of H1. Its n=614 is the binding sample size.
   - Late HL users and Lighter's beta overlap in time. Both groups had the same calendar window to join Lighter.
6. **The control is two 3-hour windows of USDC senders**, filtered to plain EOAs (codehash `0x`; delegated 7702 wallets were dropped). It is a rough "active Arbitrum user" proxy that includes payment and CEX-flow wallets. It shows HL-earliness matters, not just being on Arbitrum. It is *not* matched on DeFi sophistication.
7. **Dust rule.** I dropped *wallets* with no single deposit of $100 or more before the cutoff, and used the first ≥$100 deposit. I did not sum many small deposits.
8. **The old bridge was not checked on Arbiscan's verified-source page** (Arbiscan returned 403). Its identity rests on DefiLlama's adapter history and the on-chain flow pattern (USDC.e, Feb 2023 to Jan 2024).
9. **Variational dates and the Lighter Season 1 dates come from the press**, cross-checked against on-chain first activity. The VAR token has not launched, so "paid" cannot be judged for Variational.
10. **Step 6 (survival of other protocols the cohort tried) was skipped.** It needs per-wallet transaction history across all contracts, and every free source was blocked. This is the most important gap (see the verdict).
11. **Rate limits shaped the samples.** Lighter's API allows about 1 request/s per IP, the HL info API about 1/s, and the Arbitrum public RPC caps OR-topic queries at 100k blocks. That is why I sampled 2,000 / 600 / 614 / 690 instead of the full cohorts.

## 8. What a live watcher would need

**Cohort definition, reproducible with free data:**
- The address sent ≥$100 USDC.e to the HL legacy bridge `0xc67e9efd…73a4` on Arbitrum before 2023-11-01: 6,385 wallets (list in `cohorts.json`, key `A_early_HL_full`).
- Optionally remove the tiny-repeat and burst-cluster wallets.
- Optionally add the B cohort (86,690) as a weaker second tier, at about half the lift.

**Convergence signal:**
- **What to watch:** a newly deployed contract on Arbitrum or Ethereum, under about 60 days old, that receives first-ever stablecoin deposits of ≥$100 from **≥5 distinct cohort wallets within its first ~500 depositors**, or ≥10 within its first ~1,000. A per-user contract factory counts too: use `PoolCreated`-style events and count unique `parties`.
- **Why these thresholds:** Lighter reached 5 cohort wallets (from the 2,000 tested; about 3× that for the full cohort) by its ~240th account. Variational reached 5 by its ~176th pool. Both were 6 to 20 months ahead of their public launches and tokens.
- **Rank** candidates by cohort share among the first N depositors, not by raw count. The cohort's share falls from about 3–7% at the very start to 0.4–0.5% at maturity.
- **Discount** hits driven by farmer-flagged wallets. They join everything.

**Before trusting it,** run the missing test. Collect every contract that hit the threshold above during 2023–2025, with cohort-share ranking, and see what fraction became Lighter- or Variational-like winners vs dead points farms. That gives the precision the signal needs. That needs a tx-indexer (paid, or a self-run node).

## 9. Files (all in this folder)

- `cohorts.json` holds the cohort wallet lists and definitions (private working data):
  - `A_early_HL_full` (6,385)
  - `A_early_HL_lighter_tested` (2,000)
  - `B_points_S1_sample`
  - `Late_HL_2025H1` (614)
  - `Control_never_HL` (690)
  - the A wallets that were early on Lighter and on Variational
- `cache/` holds the raw logs: legacy bridge, Bridge2 Dec 2023 to Apr 2024, the late windows, the control windows, Variational `PoolCreated`, the Lighter lookups and calibration, the HL ledger checks, and the farmer data. All of it is resumable.
- Scripts: `rpc.py` (adaptive `eth_getLogs`), `scan_*.py`, `build_*.py`, `lighter_*.py`, `hl_check.py`, `farmers.py`, `var_verify.py`, `analyze.py`, `report.py`, `farm_lift.py`, `timeline.py`.
- Raw printed outputs: `report_output.txt`, `farm_output.txt`, `timeline_output.txt`.

---

# Failure test (free data)

Run 2026-11-23. Public Arbitrum RPC (`arb1.arbitrum.io`), Sourcify, the Blockscout metadata service (OLI labels), the DefiLlama adapters on GitHub, and the DefiLlama API, all keyless. No paid indexers were used. Nothing was posted or committed.

## Verdict

**The signal does not clear the failure test.**
- Among *truly new* protocols, those where ≥5 early-HL wallets (from a random sample of 1,500) arrived within the first 60 days succeeded **20%** of the time (5/25, 95% CI 9–39%).
- The other new protocols the same wallets touched succeeded **6%** of the time (3/50, CI 2–16%).
- That gap is not significant (Fisher p = 0.11).
- The precision of 20% is also not distinguishable from the base rate:
  - 14% for all DefiLlama-listed Arbitrum protocols from the same period (30/215, p = 0.38);
  - 11% for all new protocols the cohort touched.
- Counting new contracts of established protocols too (Compound V3, Radiant, Stryke, Thetanuts and others), precision is 19% vs 13% (p = 0.54).
- **About 4 in 5 threshold hits failed** under the success rule, which was written before any outcome was looked at.
- A higher cohort share among the first 500 depositors did **not** predict success. The median share was 0.5% for successes and 1.0% for failures.
- **The one thing that held up:** the two strongest convergences, Reya (156 early cohort wallets) and Aevo (105), were both perp venues and both succeeded. The next tier (Pike 42, Blackwing 33, Cega 20, nftperp 20) all failed. Pike was exploited in April 2024.

Read together with Part 1: early-HL wallets reliably show up early at **new perp venues**, and among the very largest convergences that has paid. As a general "follow them into new protocols" signal, it is mostly a points-farming footprint. Its precision is near the base rate.

Confidence:
- **Moderate** that the signal has no strong general precision edge. n = 25 crossers; the CIs are wide but bounded.
- **Low** on the narrower perp-venue reading: two hits out of seven perp-like crossers, so the sample is tiny.

## Pre-registered rule (written before any outcome was looked at)

File: `ft/PREREGISTERED_RULE.txt`, timestamp 2026-11-23T03:02:35Z, written while the outflow scan was still running.

- **Primary success:** DefiLlama peak TVL ≥ $50M, AND latest TVL (Nov 2026) ≥ $1M.
- **Secondary success:** the protocol launched a token (DefiLlama `gecko_id` or a token symbol).
- Protocols with no DefiLlama listing count as failures.
- The threshold is ≥5 distinct early-HL cohort wallets arriving within 60 days of the contract's first activity.

## Method

**1. Outflows.**
- Wallets: 1,500 random early-HL wallets, after removing the tiny-repeat and burst farmer flags (6,064 remained), plus the 614 late-HL wallets.
- Query: ERC-20 `Transfer` logs with topic1 set to an OR list of those wallets. arb1 allows at most 1,000 address-plus-topic selectors per query (so batches of 995 wallets, with all 4 tokens in the address field) and at most a 100k-block span when OR lists are used.
- Tokens (each verified on-chain with `name()`/`symbol()`): native USDC `0xaf88…5831`, USDC.e `0xFF97…5CC8`, USDT0 `0xFd08…bb9`, WETH `0x82aF…Bab1`.
- Window: 2023-11-01 to 2025-03-01 (blocks 145,877,584 to 310,946,919). I cut this short of the requested 2025-06-30 for two reasons. First, candidate births are limited to Nov 2023–Dec 2024 so outcomes have had ≥11 months to mature, and 60 days past Dec 2024 is about Mar 2025. Second, throughput was about 1 query/s.
- Result: 102,309 transfers to 8,235 recipients.
- The other free RPCs could not do this. publicnode needs a token for archive data, drpc allows 100 blocks, 1rpc 50 blocks, and llamarpc failed.
- The late group's own outflow batch was dropped part-way to save throughput. Its baseline comes from step 3 instead.

**2. Candidates.**
- 896 recipients had ≥2 early-HL senders.
- Labels came from the Blockscout metadata API (OLI tags), Sourcify contract and implementation names (EIP-1967 and beacon slots read at latest), `name()`/`symbol()`, an address index built from DefiLlama-Adapters (including `registries/*`) and dimension-adapters, and GitHub code search for the unidentified crossers.
- I excluded routers and aggregators, AMM pools and pairs, bridges and warp routes, CEX and EOA recipients (eth_getCode), HL's own bridges, multisigs, adapters, and the zero address. That left 584.
- Age came from the Sourcify deployment block, or else the contract's own first log.
- New = births from 2023-11-01 to 2024-12-31: 160 contracts. 31 more were excluded once enriched, leaving 129. These were grouped into **92 protocol units**: 75 truly new, 17 new contracts of protocols established before 2023. Unidentified contracts count as their own unit.

**3. Backtest.**
- For the 36 contracts with ≥5 early arrivals, I read all incoming transfers of the 4 tokens for their first 60 days (topic2 = contract).
- I computed the cohort counts among the first 500 senders, for both the early-HL sample and the late group.

**4. Outcomes.** DefiLlama `/protocol/{slug}` history: peak TVL, latest TVL, `gecko_id` and symbol, at the parent-protocol level.

## Results

| Set | Units | Primary success (≥$50M peak and alive) | Token launched |
|---|---|---|---|
| Truly new: crossers (≥5 early) | 25 | **5 (20%)** [9–39] | 8 (32%) |
| Truly new: non-crossers (1–4 early) | 50 | 3 (6%) [2–16] | 11 (22%) |
| Truly new: all cohort-touched | 75 | 8 (11%) | 19 (25%) |
| All units: crossers | 31 | 6 (19%) [9–36] | 13 (42%) |
| All units: non-crossers | 61 | 8 (13%) | 21 (34%) |
| Crossers with ≥10 early | 18 | 4 (22%) | 8 (44%) |
| Crossers with ≥20 early | 6 | 2 (33%) | 3 (50%) |
| External base: DefiLlama Arbitrum protocols listed Nov 2023–Dec 2024 (excluding CEX/chain/bridge) | 215 | 30 (14%) | 109 (51%) |

**Threshold crossers.** "Early" is the number of the 1,500 sampled wallets that arrived within 60 days. "A/late in first 500" counts how many of the contract's first 500 senders came from each sample.

| Protocol | Type | Early | Success | Peak TVL | A / late in first 500 |
|---|---|---|---|---|---|
| Reya | perp chain | 156 | **yes** | $81M | 10 / 0 |
| Aevo | perp | 105 | **yes** | $100M | 5 / 0 |
| Pike Finance | lending (exploited) | 42 | no | $3M | 3 / 1 |
| Blackwing | perp | 33 | no (peak $73M, now $0.7M) | $73M | 4 / 0 |
| Cega | options | 20 | no | $40M | 18 / 0 |
| nftperp | perp | 20 | no | $8M | 15 / 0 |
| AirdropBroker (unidentified) | other | 18 | no | none | 6 / 0 |
| 2 unidentified contracts | ? | 15, 14 | no | none | 3/1, 2/0 |
| Harmonix | vault | 10 | no | $18M | 6 / 0 |
| ZeroBase (identified from a GitHub README) | vault | 10 | **yes** | $559M | 2 / 0 |
| LBA sale (unidentified) | token sale | 10 | no | none | 8 / 0 |
| Synonym Finance | lending | 10 | no (unlisted) | none | 9 / 0 |
| Skate | vault | 10 | no | $32M | 0 / 0 |
| Fluid | lending | 7 | **yes** | $2.7B | 3 / 0 |
| Manta CeDeFi | points campaign | 7 | **yes** | $142M | 1 / 0 |
| Launchpad, Aethir node sale, LogX, Nautilus, JOJO, 4 unidentified | various | 5–7 | no | ≤$16M | — |
| Established-protocol new contracts: Compound V3 ✓, Stryke, Polynomial, Thetanuts, Impossible IDOs, Radiant | | 6–18 | 1 of 6 | | |

**Does a higher cohort share predict success?**
- **Share:** no. Among crossers, the median early-HL share of the first 500 senders was 0.5% for successes (n = 6) and 1.0% for failures (n = 25). Cega (3.6%) and nftperp (3.0%) had the highest shares, and both failed.
- **Raw count:** only weakly. The median early count was 14 for successes and 10 for failures. The top two by count succeeded; ranks 3 to 6 all failed.
- **Late group:** it is almost absent from these early depositor lists (0–1 of 500 nearly everywhere). Relative to their sample sizes, early-HL wallets are heavily over-represented. That confirms *earliness*. It does not confirm *picking ability*.

**Do HL-like perp DEXs dominate the hits?**
- Perp-like crossers succeeded 2/7 (29%); non-perp crossers 4/24 (17%).
- Both of the largest convergences, and both perp successes, are perp venues (Reya, Aevo).
- The other perp crossers (Blackwing, nftperp, LogX, JOJO) failed.
- So perps dominate the *largest* convergences, not the hit list as a whole.

## Gaps and caveats

- **Arbitrum only, ERC-20 only, 4 tokens.** This misses:
  - native ETH deposits;
  - other tokens such as ARB, GMX and LSTs;
  - other chains: Ethereum L1 (where Lighter, EigenLayer-era restaking, Ethena and Pendle activity mostly lived), Base, Solana, Blast.
  - Protocols on other chains are invisible. That is probably why Lighter-style hits from Part 1 do not appear.
- **Window.** Outflows run Nov 2023 to Feb 2025. Births are Nov 2023 to Dec 2024. Protocols from 2025 onward are not tested.
- **Labelled-wallet and label-coverage bias.**
  - 36 of the 92 units, 10 of them crossers (6 unknown contracts plus 4 unidentified sale or airdrop contracts), could not be identified. By the pre-registered rule they count as failures. Leaving out the 6 fully unknown crossers, precision is 26% for truly new protocols (5/19) and 24% for all (6/25).
  - The infra exclusion relies on labels. Unlabeled routers or pools can leak in; I removed 6 found by GitHub search. Unlabeled real protocols may have been wrongly dropped.
- **"New" uses contract age, not protocol age.** I flagged established protocols by hand and report them separately.
- **Births use the Sourcify deployment block or the first own log.** For proxies that launched long after deployment, the 60-day window may close early, which undercounts early arrivals.
- **The sample is 1,500 of 6,064 farmer-cleaned early-HL wallets.** "≥5 of 1,500" corresponds to about ≥20 of the full cohort. The thresholds scale with that.
- **The success rule depends on DefiLlama coverage.** Points campaigns, node sales and IDOs rarely have TVL, so they mostly count as failures by construction. On the token rule, the crosser vs non-crosser gap is 32% vs 22% for truly new protocols, also not significant.
- **Throughput.** arb1 throttled to about 1 query/s. The scan, plus about 1,500 follow-up queries, took about 3 hours.

## Files (`early/ft/`)

- `PREREGISTERED_RULE.txt`
- `cohort_ft.json`: sampled wallets (private)
- `out_*.jsonl`: raw outflows
- `first_by_recipient.json`
- `labels.json`, `enrich.json`, `deploy.json`, `age.json`: age and first-500 senders
- `mapped.json`: contract → protocol, type and exclusions
- `llama_hist.json`
- `units.json`
- `step5_output.txt`: the full printed results
- Scripts: `scan_out2.py`, `step1_parse.py`, `labels.py`, `deploy.py`, `step3b.py`, `enrich.py`, `mapping.py`, `step5.py`
