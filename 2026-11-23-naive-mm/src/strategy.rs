//! The strategy from the post, as it describes it: take the last trade as the fair price,
//! rest a bid a little below it and an ask a little above it, and after every trade cancel
//! both and quote again around the new last price. It never guesses the direction.
//!
//! `max_inventory_usd` is an inventory cap, which the post also suggests; `None` is
//! the strategy as the post describes it.

use rdk_clob::{AccountId, Book, Order, OrderId, OrderType, Price, Qty, Side};

pub const ME: AccountId = AccountId(1);
pub const PX: f64 = 1e6; // Price = micro-USD per HYPE
pub const QX: f64 = 1e6; // Qty = micro-HYPE

pub struct NaiveMm {
    pub half_spread_bp: f64,
    pub quote_usd: f64,
    pub max_inventory_usd: Option<f64>,
    bid: Option<OrderId>,
    ask: Option<OrderId>,
    next_id: u64,
}

impl NaiveMm {
    pub fn new(half_spread_bp: f64, quote_usd: f64, max_inventory_usd: Option<f64>) -> Self {
        Self {
            half_spread_bp,
            quote_usd,
            max_inventory_usd,
            bid: None,
            ask: None,
            next_id: 1,
        }
    }

    /// Called after every trade on the market: cancel, then quote around `fair`. The post
    /// passes the last trade price; `main.rs` also tries a reference price from elsewhere.
    pub fn on_trade(&mut self, book: &mut Book, fair: f64, inventory: f64) {
        for id in [self.bid.take(), self.ask.take()].into_iter().flatten() {
            book.cancel(id); // false when it was filled: nothing left to cancel
        }
        let d = self.half_spread_bp / 1e4;
        let cap = self.max_inventory_usd.unwrap_or(f64::INFINITY);
        if inventory * fair < cap {
            self.bid = Some(self.place(book, Side::Buy, fair * (1.0 - d)));
        }
        if inventory * fair > -cap {
            self.ask = Some(self.place(book, Side::Sell, fair * (1.0 + d)));
        }
    }

    fn place(&mut self, book: &mut Book, side: Side, px: f64) -> OrderId {
        let id = OrderId(self.next_id);
        self.next_id += 1;
        let price = Price((px * PX).round() as u64);
        let qty = Qty((self.quote_usd / px * QX).round() as u64);
        book.submit(Order {
            id,
            account: ME,
            side,
            qty,
            order_type: OrderType::Limit { price },
        });
        id
    }
}
