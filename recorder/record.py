"""Run every source in sources.toml at its own interval for MINUTES, each in its own thread.

usage: record.py MINUTES OUT_DIR STATE_JSON

Rows go to OUT_DIR/<source>.jsonl.gz (appended; one gzip member per call). A failed call's message goes to
OUT_DIR/errors.jsonl, which is encrypted with the rows: messages can quote a third party's response.

OUT_DIR/count.json says, per source, how many calls worked, how many of those were complete, how many
failed (by exception type only), how many rows they gave, and the source's last public status. It holds
no data, so it is kept unencrypted for the health check, and so is the log.

STATE_JSON carries each source's state from one job to the next. A source's run(state) works on a copy
and may set state["status"] (small, public: {"incomplete": bool, "behind_s": seconds}); an incomplete
call is tried again within 10 minutes.
"""

import gzip
import json
import sys
import threading
import time
import tomllib
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "sources"))

RETRY = 60        # after a failed call, try again this soon (or at the interval, if shorter)
INCOMPLETE = 600  # after an incomplete call, try again this soon (or at the interval, if shorter)
GRACE = 900       # a call that started before the deadline may finish this long after it


def main(minutes: float, out: Path, state_path: Path) -> None:
    sources = tomllib.loads((HERE / "sources.toml").read_text())["source"]
    out.mkdir(parents=True, exist_ok=True)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    lock, stopping = threading.Lock(), threading.Event()
    start, deadline = time.time(), time.time() + 60 * minutes
    count = {s["name"]: {"every": s["every"], "ok": 0, "complete": 0, "failed": 0, "rows": 0,
                         "error_types": {}, "status": None} for s in sources}

    def save() -> None:  # under lock
        state_path.write_text(json.dumps(state))
        (out / "count.json").write_text(json.dumps({"start": start, "end": time.time(), "sources": count}, indent=1))

    def loop(src: dict) -> None:
        name, every = src["name"], src["every"]
        mod = __import__(src["module"])
        while not stopping.is_set():
            with lock:
                st = json.loads(json.dumps(state.get(name, {})))  # the source works on its own copy
            due = st.get("last", 0) + every
            if time.time() >= deadline or due >= deadline:
                return
            if due > time.time():
                time.sleep(due - time.time())
                continue
            began = time.time()
            try:
                rows = mod.run(st)
                for r in rows:
                    r.setdefault("t", began)
                status = st.get("status") or {}
                with lock:
                    if stopping.is_set():  # too late: the hour is being packed; keep the state as it was
                        return
                    if rows:
                        with gzip.open(out / f"{name}.jsonl.gz", "at") as f:
                            for r in rows:
                                f.write(json.dumps(r, separators=(",", ":")) + "\n")
                    st["last"] = began - every + min(every, INCOMPLETE) if status.get("incomplete") else began
                    state[name] = st
                    c = count[name]
                    c["ok"] += 1
                    c["complete"] += not status.get("incomplete")
                    c["rows"] += len(rows)
                    c["status"] = status
                    save()
            except Exception as e:
                with lock:  # what the failed call did to its copy is dropped
                    if stopping.is_set():
                        return
                    with open(out / "errors.jsonl", "a") as f:
                        f.write(json.dumps({"t": began, "source": name, "error": traceback.format_exc()}) + "\n")
                    state.setdefault(name, {})["last"] = began - every + min(every, RETRY)
                    c = count[name]
                    c["failed"] += 1
                    c["error_types"][type(e).__name__] = c["error_types"].get(type(e).__name__, 0) + 1
                    save()
            c = count[name]
            print(time.strftime("%H:%M:%S"), name, c["ok"], "ok", c["failed"], "failed",
                  round(time.time() - began, 1), "s", flush=True)

    threads = [threading.Thread(target=loop, args=(s,), daemon=True) for s in sources]
    for t in threads:
        t.start()
    for t in threads:
        t.join(max(0.0, deadline + GRACE - time.time()))
    with lock:  # from here no thread writes; one still running is cut off when the process exits
        stopping.set()
        save()
    late = [t.name for t in threads if t.is_alive()]
    if late:
        print("cut off after the grace period:", len(late), "source(s)", flush=True)


if __name__ == "__main__":
    main(float(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
