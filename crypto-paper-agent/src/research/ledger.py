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
- A run may declare how many variants its round tried (`variants_tried`) and its score on each
  fold (`fold_scores`). These are the inputs a later Deflated Sharpe (needs the trial count) or
  PBO/CSCV (needs a variant x fold matrix) would read; older records simply lack them.
"""
import datetime as dt
import json
import math
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "docs" / "research" / "ledger" / "ledger.jsonl"
FINAL_STAGES = ("final", "final-whatif")


def trades_per_week(summary, start, end):
    weeks = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days / 7.0
    return round(summary.get("completed_trades", 0) / max(weeks, 1e-9), 2)


def _checked_trials(variants_tried, fold_scores):
    if variants_tried is not None and (isinstance(variants_tried, bool) or not isinstance(variants_tried, int)
                                       or variants_tried < 1):
        raise ValueError(f"variants_tried must be a whole number >= 1, got {variants_tried!r}")
    if fold_scores is None:
        return None
    if not isinstance(fold_scores, dict) or not fold_scores:
        raise ValueError("fold_scores must be a non-empty {fold: score} mapping")
    scores = {}
    for fold, score in fold_scores.items():
        if score is not None and (isinstance(score, bool) or not isinstance(score, (int, float))
                                  or not math.isfinite(score)):
            raise ValueError(f"fold score for {fold!r} must be a finite number or None, got {score!r}")
        scores[str(fold)] = score
    return scores


def record(round_id, stage, candidate, strategy, label, start, end, symbols, risk, summary,
           source="", config_files=(), frozen_commit=None, path=LEDGER, variants_tried=None, fold_scores=None):
    """Append one run. Returns the record written.

    variants_tried: how many variants the round tried in total up to this run (all candidates,
    parameter sets and scenarios, kept or dropped). fold_scores: {fold name: score} for this run,
    None for a fold that could not be scored."""
    fold_scores = _checked_trials(variants_tried, fold_scores)
    entry = {
        "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "round": round_id, "stage": stage, "candidate": candidate, "strategy": strategy, "label": label,
        "source": source, "config_files": [str(Path(f).name) for f in config_files],
        "window": [start, end], "symbols": list(symbols), "risk": risk, "frozen_commit": frozen_commit,
        "return_pct": summary.get("total_return_pct"), "max_drawdown_pct": summary.get("max_drawdown_pct"),
        "trades": summary.get("completed_trades"), "trades_per_week": trades_per_week(summary, start, end),
        "win_rate_pct": summary.get("win_rate_pct"), "yearly_return_pct": summary.get("yearly_return_pct"),
        "mean_trade_usd_95ci": summary.get("mean_trade_usd_95ci"),
        "variants_tried": variants_tried, "fold_scores": fold_scores,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, default=str) + "\n")
    return entry


def load(path=LEDGER):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def void(round_id, label, reason, path=LEDGER):
    """Mark an earlier run void because of a setup fault (not its result). The run stays in
    the ledger; a void run no longer counts as spent final data, so it can be rerun once."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "round": round_id, "stage": "void", "label": label, "reason": reason}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
    return entry


def _voided(records):
    """(round, label) pairs voided so far; a later run with the same label is live again."""
    live, voided = {}, set()
    for i, r in enumerate(records):
        key = (r["round"], r.get("label"))
        if r["stage"] == "void":
            voided |= {j for j in live.get(key, [])}
        elif r["stage"] != "lesson":
            live.setdefault(key, []).append(i)
    return voided


def spent_final_data(records):
    """{symbol: [(start, end), ...]} already used by a final test (void runs excluded)."""
    spent, voided = {}, _voided(records)
    for i, r in enumerate(records):
        if r["stage"] in FINAL_STAGES and i not in voided:
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


def variants_tried_by_round(records):
    """{round: largest declared variants_tried}; rounds that never declared one are left out, so
    a missing count is never mistaken for a single trial."""
    counts = {}
    for r in records:
        if r.get("variants_tried") is not None:
            counts[r["round"]] = max(counts.get(r["round"], 0), r["variants_tried"])
    return counts


def fold_matrix(records, round_id):
    """{candidate label: {fold: score}} for one round's live runs that declared fold scores: the
    variant x fold matrix PBO/CSCV needs. Void runs are left out."""
    voided = _voided(records)
    return {f"{r['candidate']} | {r['label']}": dict(r["fold_scores"]) for i, r in enumerate(records)
            if r["round"] == round_id and r["stage"] not in ("lesson", "void") and i not in voided
            and r.get("fold_scores")}


def summary_markdown(records):
    """A readable digest: one table row per run, then the lessons, newest round last."""
    voided = _voided(records)
    runs = [r for i, r in enumerate(records) if r["stage"] not in ("lesson", "void") and i not in voided]
    lines = ["| Round | Stage | Candidate | Strategy | Window | Symbols | Risk | Return % | Max DD % | Trades/week | Win % |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in runs:
        lines.append(f"| {r['round']} | {r['stage']} | {r['candidate']} | {r['strategy']} | {r['window'][0]}..{r['window'][1]} | "
                     f"{'/'.join(s.replace('USDT', '') for s in r['symbols'])} | {r['risk']} | {r['return_pct']} | "
                     f"{r['max_drawdown_pct']} | {r['trades_per_week']} | {r['win_rate_pct']} |")
    lines += ["", "## Lessons", ""]
    lines += [f"- Round {r['round']}: {r['lesson']}" for r in records if r["stage"] == "lesson"]
    return "\n".join(lines) + "\n"
