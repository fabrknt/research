-- One row per symbol per minute: where the Worker ran, Binance's HTTP status and its body as quoted.
CREATE TABLE IF NOT EXISTS quotes (
  t INTEGER NOT NULL,      -- unix seconds of the round
  colo TEXT,               -- Cloudflare location the scheduled run used (cdn-cgi/trace)
  symbol TEXT NOT NULL,
  status INTEGER,          -- HTTP status, 0 if the fetch threw
  body TEXT,               -- response as quoted, or the error
  PRIMARY KEY (t, symbol)
);
