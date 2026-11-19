// Once a minute: Binance's premium index (mark and index price) for both Anthropic symbols, stored as
// quoted with the HTTP status and the Cloudflare location, so a blocked location shows as a row too.
import { DurableObject } from "cloudflare:workers";

const SYMBOLS = ["ANTHROPICUSDT", "ANTUSDT"];
// Binance answered 403 from Cloudflare (KIX) on every round on 2026-11-19, so recording ended that day.
const LAST_DAY = "20261118";
const EVERY_MS = 60_000;

async function colo() {
  try {
    const r = await fetch("https://www.cloudflare.com/cdn-cgi/trace");
    return (await r.text()).match(/^colo=(\w+)$/m)?.[1] ?? null;
  } catch {
    return null;
  }
}

async function quote(symbol) {
  try {
    const r = await fetch(`https://fapi.binance.com/fapi/v1/premiumIndex?symbol=${symbol}`, {
      headers: { "User-Agent": "curl/8" },
    });
    return { status: r.status, body: (await r.text()).slice(0, 2000) };
  } catch (e) {
    return { status: 0, body: String(e) };
  }
}

const day = (ms) => new Date(ms).toISOString().slice(0, 10).replaceAll("-", "");

export class Recorder extends DurableObject {
  async start() {
    if ((await this.ctx.storage.getAlarm()) === null) await this.ctx.storage.setAlarm(Date.now() + 1000);
    return { alarm: await this.ctx.storage.getAlarm() };
  }

  async alarm() {
    const now = Date.now();
    if (day(now) > LAST_DAY) return; // not re-armed: the recorder stops
    // Re-arm first, on the minute, so a failed round does not stop the next.
    await this.ctx.storage.setAlarm(Math.floor(now / EVERY_MS) * EVERY_MS + EVERY_MS);
    const t = Math.floor(now / 1000);
    const [where, ...quotes] = await Promise.all([colo(), ...SYMBOLS.map(quote)]);
    await this.env.DB.batch(
      SYMBOLS.map((s, i) =>
        this.env.DB.prepare("INSERT OR REPLACE INTO quotes (t, colo, symbol, status, body) VALUES (?, ?, ?, ?, ?)")
          .bind(t, where, s, quotes[i].status, quotes[i].body),
      ),
    );
  }
}

export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname !== "/start") return new Response("not found", { status: 404 });
    const stub = env.RECORDER.get(env.RECORDER.idFromName("binance"), { locationHint: "apac" });
    return Response.json(await stub.start());
  },
};
