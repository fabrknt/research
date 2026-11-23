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
//! usage: cargo run --release   (writes results/summary.txt and results/equity_hourly.csv)

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
    e: f64, // reference price
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
) -> Run {
    let fair = |r: &Trade| if around_ref { r.e } else { r.px };
    let mut book = Book::new();
    let mut mm = NaiveMm::new(half_spread_bp, 500.0, cap);
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
                out.volume += q * px;
                out.fills += 1;
            }
        }
        mm.on_trade(&mut book, fair(r), inv);
        let equity = cash + inv * r.px;
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
    out.pnl = cash + inv * last;
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
                let r = run(market, d, cap, rule, around_ref);
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
}
