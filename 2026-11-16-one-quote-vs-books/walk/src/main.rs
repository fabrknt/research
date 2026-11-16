//! Rebuild each saved Lighter / Hyperliquid book in rdk-clob and fill a market order of
//! $1k, $100k and $1M on each side. Reads collect.py's JSONL on stdin, writes one JSON line
//! per (round, market, venue): the mid and the average fill price per size, or null when
//! the saved book was too thin to fill it.
//!
//!     cat ../data/snap-*.jsonl | cargo run --release > ../data/walks.jsonl

use std::io::{self, BufRead, Write};

use rdk_clob::{AccountId, Book, Order, OrderId, OrderType, Price, Qty, Side};
use serde_json::{Value, json};

const PX: f64 = 1e6; // price minor units: 1e-6 USD
const SZ: f64 = 1e8; // size minor units: 1e-8 of the asset
const SIZES: [f64; 3] = [1e3, 1e5, 1e6];

fn num(v: &Value) -> Option<f64> {
    v.as_str()?.parse().ok()
}

/// Rest every saved order on a fresh book (makers on account 1).
fn load(levels: &Value) -> Option<(Book, f64, f64)> {
    let mut book = Book::new();
    let mut id = 0;
    for (side, key) in [(Side::Sell, "asks"), (Side::Buy, "bids")] {
        for lv in levels[key].as_array()? {
            let (p, q) = (num(&lv[0])?, num(&lv[1])?);
            if q <= 0.0 {
                continue;
            }
            id += 1;
            book.submit(Order {
                id: OrderId(id),
                account: AccountId(1),
                side,
                qty: Qty((q * SZ).round() as u64),
                order_type: OrderType::Limit { price: Price((p * PX).round() as u64) },
            });
        }
    }
    let bid = book.best_bid()?.0 as f64 / PX;
    let ask = book.best_ask()?.0 as f64 / PX;
    Some((book, bid, ask))
}

/// Average price of a market order for `usd` of notional at `mid`; None if the book runs out.
fn fill(book: &Book, side: Side, usd: f64, mid: f64) -> Option<f64> {
    let qty = Qty((usd / mid * SZ).round() as u64);
    let q = book.quote_market(side, qty);
    (q.filled == qty && qty.0 > 0).then(|| q.notional as f64 / q.filled.0 as f64 / PX)
}

fn main() {
    let out = io::stdout();
    let mut out = out.lock();
    for line in io::stdin().lock().lines() {
        let Ok(row) = serde_json::from_str::<Value>(&line.unwrap()) else { continue };
        for venue in ["lighter", "hl", "hl_coarse"] {
            let Some((book, bid, ask)) = row.get(venue).and_then(load) else { continue };
            let mid = (bid + ask) / 2.0;
            let sizes: Vec<Value> = SIZES
                .iter()
                .map(|&usd| {
                    json!({"usd": usd,
                           "buy": fill(&book, Side::Buy, usd, mid),
                           "sell": fill(&book, Side::Sell, usd, mid)})
                })
                .collect();
            let rec = json!({"t": row["t"], "var": row["var"], "venue": venue,
                             "book_t": row[venue]["t"], "bid": bid, "ask": ask, "sizes": sizes});
            writeln!(out, "{rec}").unwrap();
        }
    }
}
