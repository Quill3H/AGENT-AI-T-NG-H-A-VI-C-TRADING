"""
src/research/ledger.py
======================
The research ledger: every paper backtest a research round runs is appended here, so later
rounds (people or the bot) can read what was tried, what it returned and which data has
already been spent on final tests.

Safety rules the ledger enforces or records:
- Records are append-only JSON lines; nothing is rewritten.
- A final test is "spent" data: `spent_final_data` lists every (symbol, window) used by a
  final stage, and `check_untouched` refuses to plan a new final test on spent data, so the
  bot cannot quietly re-tune on its own holdout.
- Records carry the commit that froze the selection; a lesson is a plain sentence written
  after the run, never a parameter change.
"""
import datetime as dt
import json
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "docs" / "research" / "ledger" / "ledger.jsonl"
FINAL_STAGES = ("final", "final-whatif")


def trades_per_week(summary, start, end):
    weeks = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days / 7.0
    return round(summary.get("completed_trades", 0) / max(weeks, 1e-9), 2)


def record(round_id, stage, candidate, strategy, label, start, end, symbols, risk, summary,
           source="", config_files=(), frozen_commit=None, path=LEDGER):
    """Append one run. Returns the record written."""
    entry = {
        "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "round": round_id, "stage": stage, "candidate": candidate, "strategy": strategy, "label": label,
        "source": source, "config_files": [str(Path(f).name) for f in config_files],
        "window": [start, end], "symbols": list(symbols), "risk": risk, "frozen_commit": frozen_commit,
        "return_pct": summary.get("total_return_pct"), "max_drawdown_pct": summary.get("max_drawdown_pct"),
        "trades": summary.get("completed_trades"), "trades_per_week": trades_per_week(summary, start, end),
        "win_rate_pct": summary.get("win_rate_pct"), "yearly_return_pct": summary.get("yearly_return_pct"),
        "mean_trade_usd_95ci": summary.get("mean_trade_usd_95ci"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, default=str) + "\n")
    return entry


def load(path=LEDGER):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def spent_final_data(records):
    """{symbol: [(start, end), ...]} already used by a final test."""
    spent = {}
    for r in records:
        if r["stage"] in FINAL_STAGES:
            for symbol in r["symbols"]:
                window = tuple(r["window"])
                if window not in spent.setdefault(symbol, []):
                    spent[symbol].append(window)
    return spent


def _overlaps(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def check_untouched(symbols, start, end, records):
    """Raise ValueError if any symbol/window pair overlaps data a final test already used."""
    spent = spent_final_data(records)
    clashes = [(s, w) for s in symbols for w in spent.get(s, []) if _overlaps((start, end), w)]
    if clashes:
        raise ValueError(f"final-test data already spent: {clashes}")


def note(round_id, lesson, path=LEDGER):
    """Append a lesson learned (plain text) for a round."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "round": round_id, "stage": "lesson", "lesson": lesson}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def summary_markdown(records):
    """A readable digest: one table row per run, then the lessons, newest round last."""
    runs = [r for r in records if r["stage"] != "lesson"]
    lines = ["| Round | Stage | Candidate | Strategy | Window | Symbols | Risk | Return % | Max DD % | Trades/week | Win % |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in runs:
        lines.append(f"| {r['round']} | {r['stage']} | {r['candidate']} | {r['strategy']} | {r['window'][0]}..{r['window'][1]} | "
                     f"{'/'.join(s.replace('USDT', '') for s in r['symbols'])} | {r['risk']} | {r['return_pct']} | "
                     f"{r['max_drawdown_pct']} | {r['trades_per_week']} | {r['win_rate_pct']} |")
    lines += ["", "## Lessons", ""]
    lines += [f"- Round {r['round']}: {r['lesson']}" for r in records if r["stage"] == "lesson"]
    return "\n".join(lines) + "\n"
