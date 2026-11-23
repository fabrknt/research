//! Replays the post's market maker (`strategy.rs`) on two markets with rdk-clob as the exchange:
//!
//!   A. a random-bot market: bots trade at random, crossing a 20 bp spread around a hidden
//!      price that wanders and comes back (the price does not trend; takers know nothing).
//!   B. Elysium's HYPE/USDC flow, 2026-11-18 00:00 to 11-21 05:00 UTC: 57,393 recorded swaps,
//!      each with its time, side, average price and size (tape/elysium_hype_usdc.csv).
//!
//! Each recorded trade arrives as an immediate-or-cancel taker at the price it actually got: it
//! fills against our quote when our quote is at least as good, up to the trade's size, and the
//! rest goes elsewhere. Our order is always first in line (no queue, no other makers), so fills
//! are an upper bound, the way a paper trade is. A takes its times and sizes from the same tape.
//!
//! Market rule (optional): a directional fee, paid by the taker to the maker, when the trade
//! moves toward the reference price E (B: HyperCore's HYPE price times Elysium's basis over the
//! previous 30 minutes, from fabrknt/research 2026-11-21-elysium-direction; A: the hidden price).
//! Fee = max(30 bp, distance from our quote to E), at most 300 bp, as Shadowbook's DirectionalFee
//! hook sets it. A taker pays it only if the all-in price is still no worse than what it got.
//!
//! Hedge (results/hedged.txt, B only): every fill is offset on HyperCore's HYPE perp at the open of
//! the minute after it (column h of the tape: known only after the fill, so no hindsight), paying a
//! stated cost per dollar of perp traded, and the perp pays or earns HYPE's hourly funding
//! (data/funding_hype.csv from fetch_funding.py). The perp position is always minus the inventory.
//!
//! usage: python3 -I fetch_funding.py; cargo run --release
//!        (writes results/summary.txt, results/equity_hourly.csv and results/hedged.txt)

mod strategy;

use rdk_clob::{AccountId, Book, Order, OrderId, OrderType, Price, Qty, Side};
use std::fmt::Write as _;
use strategy::{ME, NaiveMm, PX, QX};

#[derive(Clone, Copy)]
struct Trade {
    t: u64,
    buy: bool, // the taker buys HYPE
    px: f64,
    usd: f64,
    e: f64,  // reference price
    h: f64,  // HyperCore HYPE perp, open of the minute after the trade (the hedge price)
    ec: f64, // E from what is known at the trade: this minute's open x median basis of earlier trades
}

fn load_tape(path: &str) -> Vec<Trade> {
    let text = std::fs::read_to_string(path).unwrap_or_else(|e| panic!("{path}: {e}"));
    text.lines()
        .skip(1)
        .map(|l| {
            let f: Vec<&str> = l.split(',').collect();
            Trade {
                t: f[0].parse().unwrap(),
                buy: f[1] == "buy",
                px: f[2].parse().unwrap(),
                usd: f[3].parse().unwrap(),
                e: f[4].parse().unwrap(),
                h: f[5].parse().unwrap(),
                ec: f[6].parse().unwrap(),
            }
        })
        .collect()
}

/// xorshift64* and Box-Muller: fixed seed, no dependency, same market every run.
struct Rng(u64);
impl Rng {
    fn next(&mut self) -> f64 {
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        ((self.0.wrapping_mul(0x2545_F491_4F6C_DD1D) >> 11) as f64 + 0.5) / (1u64 << 53) as f64
    }
    fn gauss(&mut self) -> f64 {
        (-2.0 * self.next().ln()).sqrt() * (std::f64::consts::TAU * self.next()).cos()
    }
}

const BOT_SPREAD_BP: f64 = 20.0; // bots cross this far from the hidden price
const BOT_NOISE_BP: f64 = 3.0;
const MOVE_BP: f64 = 1.82; // hidden price move per trade: B's per-trade move of E
const PULL: f64 = 0.01; // share of the distance from the start the hidden price gives back per trade

fn random_bot_market(tape: &[Trade]) -> Vec<Trade> {
    let mut rng = Rng(0x00C0_FFEE_2026_1123);
    let p0 = tape[0].px;
    let mut x = 0.0f64;
    tape.iter()
        .map(|r| {
            let fair = p0 * x.exp();
            x = x * (1.0 - PULL) + rng.gauss() * MOVE_BP / 1e4;
            let buy = rng.next() < 0.5;
            let away = (BOT_SPREAD_BP + (rng.gauss() * BOT_NOISE_BP).abs()) / 1e4;
            let px = if buy {
                fair * (1.0 + away)
            } else {
                fair * (1.0 - away)
            };
            Trade {
                t: r.t,
                buy,
                px,
                usd: r.usd,
                e: fair,
                h: fair,
                ec: fair,
            }
        })
        .collect()
}

#[derive(Default)]
struct Run {
    pnl: f64,
    volume: f64,
    fills: u64,
    fees: f64,
    max_long: f64,
    max_short: f64,
    max_dd: f64,
    end_inventory_usd: f64,
    markout5: f64,
    markout5_volume: f64, // fills with a full five minutes of tape after them
    hourly: Vec<(u64, f64)>,
    // with a hedge: the Elysium leg (cash + inventory at Elysium's last price), the perp leg before
    // costs, what the perp trades cost, funding, and the inventory's value at HyperCore's last price
    elysium_leg: f64,
    perp_leg: f64,
    hedge_costs: f64,
    funding: f64,
    inv_at_hl_last: f64,
    funding_hours: u32,
    funding_rate_sum: f64,
}

struct Hedge<'a> {
    cost_bp: f64,
    funding: &'a [(u64, f64)], // (hour start, rate): the perp pays rate x position value each hour
}

fn load_funding(path: &str) -> Vec<(u64, f64)> {
    let text = std::fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("{path}: {e} (run python3 -I fetch_funding.py first)"));
    text.lines()
        .skip(1)
        .map(|l| {
            let (t, r) = l.split_once(',').unwrap();
            (t.parse().unwrap(), r.parse().unwrap())
        })
        .collect()
}

fn directional_fee(our_px: f64, e: f64, taker_buys: bool) -> f64 {
    let toward = if taker_buys { our_px < e } else { our_px > e };
    if !toward {
        return 0.0;
    }
    (our_px / e - 1.0).abs().clamp(0.003, 0.03)
}

fn run(
    market: &[Trade],
    half_spread_bp: f64,
    cap: Option<f64>,
    rule: bool,
    around_ref: bool,
    hedge: Option<&Hedge>,
    quote_usd: f64,
) -> Run {
    // perp hedges wait until the minute after their fill opens; until then they are not on the perp
    let (mut perp, mut perp_cash, mut next_funding) = (0.0f64, 0.0f64, 0usize);
    let mut pending: std::collections::VecDeque<(u64, f64, f64)> = Default::default(); // (when, dq, price)
    let mut known_h = market[0].h; // latest HyperCore open known at the current time
    let mut k = 0usize; // trades whose next-minute open is known
    let execute = |until: u64,
                   perp: &mut f64,
                   perp_cash: &mut f64,
                   pending: &mut std::collections::VecDeque<(u64, f64, f64)>| {
        while pending.front().is_some_and(|p| p.0 <= until) {
            let (_, dq, price) = pending.pop_front().unwrap();
            *perp += dq;
            *perp_cash -= dq * price;
        }
    };
    let fair = |r: &Trade| if around_ref { r.e } else { r.px };
    let mut book = Book::new();
    let mut mm = NaiveMm::new(half_spread_bp, quote_usd, cap);
    let (mut inv, mut cash) = (0.0f64, 0.0f64);
    let mut out = Run::default();
    let mut peak = 0.0f64;
    let t0 = market[0].t;
    // reference price five minutes after each trade: E of the last trade at or before t + 300 s;
    // None when the tape ends before t + 300 s (those fills are left out of the 5-minute measure)
    let t_end = market.last().unwrap().t;
    let mut j = 0;
    let e5: Vec<Option<f64>> = market
        .iter()
        .map(|r| {
            while j + 1 < market.len() && market[j + 1].t <= r.t + 300 {
                j += 1;
            }
            (r.t + 300 <= t_end).then_some(market[j].e)
        })
        .collect();
    mm.on_trade(&mut book, fair(&market[0]), inv);
    for (i, r) in market.iter().enumerate().skip(1) {
        if let Some(hd) = hedge {
            while k < i && (market[k].t / 60 + 1) * 60 <= r.t {
                known_h = market[k].h;
                k += 1;
            }
            // funding for each hour that started before this trade, on the perp position held then
            while next_funding < hd.funding.len() && hd.funding[next_funding].0 <= r.t {
                let ft = hd.funding[next_funding].0;
                execute(ft, &mut perp, &mut perp_cash, &mut pending);
                if ft >= market[0].t {
                    out.funding -= perp * known_h * hd.funding[next_funding].1; // a long pays a positive rate
                    out.funding_hours += 1;
                    out.funding_rate_sum += hd.funding[next_funding].1;
                }
                next_funding += 1;
            }
            execute(r.t, &mut perp, &mut perp_cash, &mut pending);
        }
        let ours = if r.buy {
            book.best_ask()
        } else {
            book.best_bid()
        };
        if let Some(Price(p)) = ours {
            let our_px = p as f64 / PX;
            let f = if rule {
                directional_fee(our_px, r.e, r.buy)
            } else {
                0.0
            };
            // the most the taker accepts from us before the fee, given what it actually got
            let limit = if r.buy {
                r.px / (1.0 + f)
            } else {
                r.px / (1.0 - f)
            };
            let res = book.submit(Order {
                id: OrderId((1 << 40) + i as u64),
                account: AccountId(2),
                side: if r.buy { Side::Buy } else { Side::Sell },
                qty: Qty((r.usd / r.px * QX).round() as u64),
                order_type: OrderType::ImmediateOrCancel {
                    // a buyer's most is rounded down, a seller's least is rounded up
                    price: Price(if r.buy {
                        (limit * PX).floor()
                    } else {
                        (limit * PX).ceil()
                    } as u64),
                },
            });
            for fill in res.fills.iter().filter(|f| f.maker_account == ME) {
                let (q, px) = (fill.qty.0 as f64 / QX, fill.price.0 as f64 / PX);
                let fee = q * px * f;
                match fill.maker_side {
                    Side::Buy => {
                        inv += q;
                        cash -= q * px;
                        if let Some(e) = e5[i] {
                            out.markout5 += q * (e - px) + fee;
                            out.markout5_volume += q * px;
                        }
                    }
                    Side::Sell => {
                        inv -= q;
                        cash += q * px;
                        if let Some(e) = e5[i] {
                            out.markout5 += q * (px - e) + fee;
                            out.markout5_volume += q * px;
                        }
                    }
                }
                cash += fee;
                out.fees += fee;
                if let Some(hd) = hedge {
                    // offset the fill on the perp at the next minute's open
                    let dq = if fill.maker_side == Side::Buy { -q } else { q };
                    pending.push_back(((r.t / 60 + 1) * 60, dq, r.h));
                    out.hedge_costs += dq.abs() * r.h * hd.cost_bp / 1e4;
                }
                out.volume += q * px;
                out.fills += 1;
            }
        }
        mm.on_trade(&mut book, fair(r), inv);
        // costs are booked when the hedge is decided; pending hedges are not yet on the perp
        let equity = cash + inv * r.px + perp_cash + perp * known_h - out.hedge_costs + out.funding;
        peak = peak.max(equity);
        out.max_dd = out.max_dd.max(peak - equity);
        out.max_long = out.max_long.max(inv * r.px);
        out.max_short = out.max_short.min(inv * r.px);
        let hour = (r.t - t0) / 3600;
        match out.hourly.last_mut() {
            Some((h, e)) if *h == hour => *e = equity,
            _ => out.hourly.push((hour, equity)),
        }
    }
    let last = market.last().unwrap().px;
    let last_h = market.last().unwrap().h; // the open of the minute after the last trade
    execute(u64::MAX, &mut perp, &mut perp_cash, &mut pending);
    out.elysium_leg = cash + inv * last;
    out.perp_leg = perp_cash + perp * last_h;
    out.inv_at_hl_last = inv * last_h;
    out.pnl = out.elysium_leg + out.perp_leg - out.hedge_costs + out.funding;
    out.end_inventory_usd = inv * last;
    out
}

fn bp(x: f64, volume: f64) -> f64 {
    if volume > 0.0 { x / volume * 1e4 } else { 0.0 }
}

fn main() {
    let tape = load_tape("tape/elysium_hype_usdc.csv");
    let bots = random_bot_market(&tape);
    let days = (tape.last().unwrap().t - tape[0].t) as f64 / 86400.0;
    let mut s = String::new();
    writeln!(
        s,
        "settings: bots cross {BOT_SPREAD_BP} bp + |N(0, {BOT_NOISE_BP} bp)|, hidden price moves {MOVE_BP} bp a trade and gives back {}% a trade; directional fee toward E = max(30 bp, distance) up to 300 bp",
        PULL * 100.0
    )
    .unwrap();
    writeln!(
        s,
        "{} trades over {days:.2} days, quote $500 a side; P&L marked to each market's last price",
        tape.len()
    )
    .unwrap();
    let side_usd = |buy: bool| {
        tape.iter()
            .filter(|r| r.buy == buy)
            .map(|r| r.usd)
            .sum::<f64>()
    };
    let moves: Vec<f64> = tape.windows(2).map(|w| (w[1].e / w[0].e).ln()).collect();
    let mean = moves.iter().sum::<f64>() / moves.len() as f64;
    let sd = (moves.iter().map(|m| (m - mean).powi(2)).sum::<f64>() / moves.len() as f64).sqrt();
    writeln!(
        s,
        "Elysium tape: takers bought ${:.0}, sold ${:.0}; E moves {:.2} bp per trade (sd of log change)",
        side_usd(true),
        side_usd(false),
        sd * 1e4
    )
    .unwrap();
    writeln!(
        s,
        "HYPE on Elysium: {:.2} -> {:.2} ({:+.1}%), tape {} to {} (unix s)\n",
        tape[0].px,
        tape.last().unwrap().px,
        (tape.last().unwrap().px / tape[0].px - 1.0) * 100.0,
        tape[0].t,
        tape.last().unwrap().t
    )
    .unwrap();
    writeln!(
        s,
        "{:<10} {:>4} {:<17} {:>10} {:>11} {:>8} {:>8} {:>9} {:>10} {:>11} {:>10}",
        "market",
        "bp",
        "variant",
        "P&L/day",
        "volume/day",
        "bp/vol",
        "5min bp",
        "fees/day",
        "max DD",
        "max |inv|",
        "end inv"
    )
    .unwrap();
    let (mut b_losing, mut b_total) = (0usize, 0usize);
    let mut curves: Vec<(String, Vec<(u64, f64)>)> = Vec::new();
    for (name, market) in [("A bots", &bots), ("B Elysium", &tape)] {
        for d in [10.0, 20.0, 30.0, 50.0] {
            for (variant, cap, rule, around_ref) in [
                ("as posted", None, false, false),
                ("inventory cap 5K", Some(5_000.0), false, false),
                ("directional fee", None, true, false),
                ("quote around E", None, false, true),
            ] {
                let r = run(market, d, cap, rule, around_ref, None, 500.0);
                if name.starts_with('B') {
                    b_total += 1;
                    b_losing += usize::from(r.pnl < 0.0);
                }
                writeln!(s, "{:<10} {:>4} {:<17} {:>10.0} {:>11.0} {:>8.1} {:>8.1} {:>9.0} {:>10.0} {:>11.0} {:>10.0}",
                    name, d, variant, r.pnl / days, r.volume / days, bp(r.pnl, r.volume), bp(r.markout5, r.markout5_volume), r.fees / days,
                    r.max_dd, r.max_long.max(-r.max_short), r.end_inventory_usd).unwrap();
                if d == 30.0 {
                    curves.push((format!("{name} | {variant}"), r.hourly));
                }
            }
        }
        writeln!(s).unwrap();
    }
    writeln!(
        s,
        "B Elysium settings with P&L below zero: {b_losing} of {b_total}"
    )
    .unwrap();
    print!("{s}");
    std::fs::create_dir_all("results").unwrap();
    std::fs::write("results/summary.txt", &s).unwrap();
    let mut csv = String::from("hour");
    for (n, _) in &curves {
        write!(csv, ",{n}").unwrap();
    }
    csv.push('\n');
    let hours = curves
        .iter()
        .map(|(_, c)| c.last().map_or(0, |x| x.0))
        .max()
        .unwrap_or(0);
    let mut last = vec![0.0; curves.len()];
    for h in 0..=hours {
        write!(csv, "{h}").unwrap();
        for (k, (_, c)) in curves.iter().enumerate() {
            if let Some((_, e)) = c.iter().find(|x| x.0 == h) {
                last[k] = *e;
            }
            write!(csv, ",{:.0}", last[k]).unwrap();
        }
        csv.push('\n');
    }
    std::fs::write("results/equity_hourly.csv", csv).unwrap();
    hedged(&tape, days);
}

/// B with every fill offset on HyperCore's perp. P&L marks the inventory at Elysium's last price and
/// the perp at HyperCore's; "if basis closes" marks the inventory at HyperCore's last price instead
/// (what it would be worth after the canonical withdrawal, if the gap were gone by then).
fn hedged(tape: &[Trade], days: f64) {
    let funding = load_funding("data/funding_hype.csv");
    // the fee by direction and quoting around E decide on the E known at the trade (no hindsight)
    let hindsight = tape;
    let causal: Vec<Trade> = tape.iter().map(|r| Trade { e: r.ec, ..*r }).collect();
    let tape = &causal[..];
    let mut s = String::new();
    // the hours applied: those starting from the first trade up to the last one
    let (t0, t1) = (tape[0].t, tape.last().unwrap().t);
    let rates: Vec<f64> = funding
        .iter()
        .filter(|x| x.0 >= t0 && x.0 <= t1)
        .map(|x| x.1)
        .collect();
    writeln!(
        s,
        "B Elysium, every fill offset on HyperCore's HYPE perp at the next minute's open; E for the fee and quotes = this minute's open x median (price / its minute's open) of the trades in the previous 30 min (no hindsight); funding applied for {} hours starting inside the tape ({} fetched), mean {:+.3} bp/h",
        rates.len(),
        funding.len(),
        rates.iter().sum::<f64>() / rates.len() as f64 * 1e4
    )
    .unwrap();
    writeln!(
        s,
        "HyperCore perp (next-minute open): {:.3} -> {:.3}\n",
        tape[0].h,
        tape.last().unwrap().h
    )
    .unwrap();
    writeln!(
        s,
        "{:>4} {:<17} {:>5} {:>9} {:>11} {:>8} {:>10} {:>10} {:>9} {:>8} {:>9} {:>14}",
        "bp",
        "variant",
        "cost",
        "P&L/day",
        "volume/day",
        "bp/vol",
        "ely leg/d",
        "perp leg/d",
        "costs/d",
        "fund/d",
        "max DD",
        "if basis closes"
    )
    .unwrap();
    let mut positive = 0;
    let mut total = 0;
    let mut basis_gap = 0.0f64;
    for d in [10.0, 20.0, 30.0, 50.0] {
        for (variant, rule, around_ref) in [
            ("as posted", false, false),
            ("directional fee", true, false),
            ("quote around E", false, true),
        ] {
            for cost_bp in [4.5, 14.5] {
                let hd = Hedge {
                    cost_bp,
                    funding: &funding,
                };
                let r = run(tape, d, None, rule, around_ref, Some(&hd), 500.0);
                let closes = r.pnl - r.end_inventory_usd + r.inv_at_hl_last;
                total += 1;
                positive += usize::from(r.pnl > 0.0);
                basis_gap = basis_gap.max((closes - r.pnl).abs() / days);
                writeln!(
                    s,
                    "{:>4} {:<17} {:>5} {:>9.0} {:>11.0} {:>8.1} {:>10.0} {:>10.0} {:>9.0} {:>8.0} {:>9.0} {:>14.0}",
                    d, variant, cost_bp, r.pnl / days, r.volume / days, bp(r.pnl, r.volume),
                    r.elysium_leg / days, r.perp_leg / days, -r.hedge_costs / days, r.funding / days,
                    r.max_dd, closes / days
                )
                .unwrap();
            }
        }
    }
    writeln!(
        s,
        "\nhedged settings with P&L above zero: {positive} of {total}"
    )
    .unwrap();
    writeln!(s, "cost = bp of perp notional per trade: 4.5 = HyperCore taker fee only, 14.5 = plus 10 bp slippage").unwrap();
    writeln!(
        s,
        "largest change from marking the inventory at HyperCore's last price instead: ${basis_gap:.0} a day"
    )
    .unwrap();
    writeln!(
        s,
        "Elysium tape volume: ${:.0} a day",
        tape.iter().map(|r| r.usd).sum::<f64>() / days
    )
    .unwrap();
    writeln!(
        s,
        "\nthe same with the hindsight E (minute interpolated to its close), cost 4.5 bp:"
    )
    .unwrap();
    for d in [10.0, 20.0, 30.0, 50.0] {
        for (variant, rule, around_ref) in [
            ("directional fee", true, false),
            ("quote around E", false, true),
        ] {
            let hd = Hedge {
                cost_bp: 4.5,
                funding: &funding,
            };
            let r = run(hindsight, d, None, rule, around_ref, Some(&hd), 500.0);
            writeln!(s, "{:>4} {:<17} P&L/day {:>6.0}", d, variant, r.pnl / days).unwrap();
        }
    }
    writeln!(s, "\nlarger quotes, cost 14.5 bp:").unwrap();
    for d in [30.0, 50.0] {
        for (variant, rule) in [("as posted", false), ("directional fee", true)] {
            for q in [500.0, 2_000.0, 5_000.0] {
                let hd = Hedge {
                    cost_bp: 14.5,
                    funding: &funding,
                };
                let r = run(tape, d, None, rule, false, Some(&hd), q);
                writeln!(
                    s,
                    "{:>4} {:<17} quote ${:<6} P&L/day {:>6.0}  volume/day {:>8.0}  bp/vol {:>6.1}  max DD {:>6.0}",
                    d, variant, q, r.pnl / days, r.volume / days, bp(r.pnl, r.volume), r.max_dd
                )
                .unwrap();
            }
        }
    }
    print!("{s}");
    std::fs::write("results/hedged.txt", &s).unwrap();
}
