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
import math
import uuid
from collections.abc import Mapping
from numbers import Integral, Real
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "docs" / "research" / "ledger" / "ledger.jsonl"
FINAL_STAGES = ("final", "final-whatif")
PREREGISTRATION_REQUIRED_FROM_ROUND = 19


def trades_per_week(summary, start, end):
    weeks = (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days / 7.0
    return round(summary.get("completed_trades", 0) / max(weeks, 1e-9), 2)


def _append(entry, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, default=str) + "\n")
    return entry


def _unique_names(values, name, allow_empty=False):
    values = list(values)
    if not allow_empty and not values:
        raise ValueError(f"{name} must not be empty")
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError(f"{name} must contain non-empty strings")
    if len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique")
    return values


def _cost_multipliers(values):
    costs = list(values)
    if not costs:
        raise ValueError("cost_multipliers must not be empty")
    if any(isinstance(value, bool) or not isinstance(value, Real)
           or not math.isfinite(float(value)) or value <= 0 for value in costs):
        raise ValueError("cost_multipliers must be finite and positive")
    costs = [float(value) for value in costs]
    if len(costs) != len(set(costs)):
        raise ValueError("cost_multipliers must be unique")
    return costs


def _control_specs(controls):
    if not isinstance(controls, Mapping):
        raise TypeError("controls must be a mapping")
    names = _unique_names(controls, "controls", allow_empty=True)
    specs = {}
    for name in names:
        spec = controls[name]
        if not isinstance(spec, Mapping):
            raise TypeError(f"control spec for {name} must be a mapping")
        spec = dict(spec)
        if name == "matched_random":
            if set(spec) != {"seed", "repetitions"}:
                raise ValueError("matched_random control requires exactly seed and repetitions")
            if isinstance(spec["seed"], bool) or not isinstance(spec["seed"], Integral):
                raise ValueError("matched_random seed must be an integer")
            if (isinstance(spec["repetitions"], bool)
                    or not isinstance(spec["repetitions"], Integral)
                    or spec["repetitions"] <= 0):
                raise ValueError("matched_random repetitions must be a positive integer")
        specs[name] = spec
    return specs


def preregister(round_id, hypothesis_id, variants, controls, cost_multipliers, frozen_commit,
                familywise_alpha=0.05, path=LEDGER):
    """Append a protocol before a round's first result; old rounds remain explicitly legacy."""
    if not isinstance(hypothesis_id, str) or not hypothesis_id.strip():
        raise ValueError("hypothesis_id must be a non-empty string")
    variants = _unique_names(variants, "variants")
    controls = _control_specs(controls)
    costs = _cost_multipliers(cost_multipliers)
    if not isinstance(frozen_commit, str) or not frozen_commit.strip():
        raise ValueError("frozen_commit must be a non-empty string")
    if (isinstance(familywise_alpha, bool) or not isinstance(familywise_alpha, Real)
            or not math.isfinite(float(familywise_alpha)) or not 0 < familywise_alpha < 1):
        raise ValueError("familywise_alpha must be between zero and one")
    records = load(path)
    if any(r.get("round") == round_id and r.get("stage") == "preregister" for r in records):
        raise ValueError(f"round {round_id} is already preregistered")
    if any(r.get("round") == round_id and r.get("stage") not in ("lesson", "void", "preregister")
           for r in records):
        raise ValueError("preregistration must precede the first round result")
    return _append({
        "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "round": round_id,
        "stage": "preregister",
        "hypothesis_id": hypothesis_id,
        "planned_variants": variants,
        "controls": controls,
        "cost_multipliers": costs,
        "frozen_commit": frozen_commit,
        "familywise_alpha": float(familywise_alpha),
        "bonferroni_alpha": float(familywise_alpha) / len(variants),
    }, path)


def _validate_protocol(round_id, candidate, protocol, frozen_commit, path):
    if not isinstance(protocol, dict):
        raise TypeError("protocol must be a mapping")
    required = {"hypothesis_id", "variant_id", "run_role", "cost_multiplier"}
    allowed = required | {"control_spec"}
    if not required <= set(protocol) or not set(protocol) <= allowed:
        raise ValueError(f"protocol fields must contain {sorted(required)} and optional control_spec")
    registrations = [r for r in load(path)
                     if r.get("round") == round_id and r.get("stage") == "preregister"]
    if len(registrations) != 1 or registrations[0]["hypothesis_id"] != protocol["hypothesis_id"]:
        raise ValueError("protocol run requires its matching preregistration")
    registration = registrations[0]
    if protocol["variant_id"] not in registration["planned_variants"]:
        raise ValueError(f"undeclared variant: {protocol['variant_id']}")
    if candidate != protocol["variant_id"]:
        raise ValueError("candidate must equal protocol variant_id")
    cost = protocol["cost_multiplier"]
    if (isinstance(cost, bool) or not isinstance(cost, Real) or not math.isfinite(float(cost))
            or float(cost) not in registration["cost_multipliers"]):
        raise ValueError(f"undeclared cost multiplier: {cost}")
    role = protocol["run_role"]
    if not isinstance(role, str) or not role.strip():
        raise ValueError("run_role must be a non-empty string")
    if role == "candidate":
        if "control_spec" in protocol:
            raise ValueError("candidate runs must not include control_spec")
    else:
        if role not in registration["controls"]:
            raise ValueError(f"undeclared control: {role}")
        if protocol.get("control_spec") != registration["controls"][role]:
            raise ValueError(f"control_spec does not match preregistration for {role}")
    if frozen_commit != registration["frozen_commit"]:
        raise ValueError("frozen_commit does not match preregistration")
    return {**protocol, "cost_multiplier": float(cost)}


def _requires_preregistration(round_id):
    return (not isinstance(round_id, Integral) or isinstance(round_id, bool)
            or round_id >= PREREGISTRATION_REQUIRED_FROM_ROUND)


def record(round_id, stage, candidate, strategy, label, start, end, symbols, risk, summary,
           source="", config_files=(), frozen_commit=None, path=LEDGER, protocol=None):
    """Append one run. Returns the record written."""
    records = load(path)
    registrations = [r for r in records
                     if r.get("round") == round_id and r.get("stage") == "preregister"]
    if not registrations and _requires_preregistration(round_id):
        raise ValueError(f"round {round_id} requires preregistration")
    if protocol is None and registrations:
        raise ValueError(f"preregistered round {round_id} requires protocol metadata")
    protocol = (_validate_protocol(round_id, candidate, protocol, frozen_commit, path)
                if protocol is not None else None)
    known_ids = {r.get("run_id") for r in records if r.get("run_id")}
    run_id = uuid.uuid4().hex
    while run_id in known_ids:
        run_id = uuid.uuid4().hex
    entry = {
        "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "run_id": run_id,
        "round": round_id, "stage": stage, "candidate": candidate, "strategy": strategy, "label": label,
        "source": source, "config_files": [str(Path(f).name) for f in config_files],
        "window": [start, end], "symbols": list(symbols), "risk": risk, "frozen_commit": frozen_commit,
        "return_pct": summary.get("total_return_pct"), "max_drawdown_pct": summary.get("max_drawdown_pct"),
        "trades": summary.get("completed_trades"), "trades_per_week": trades_per_week(summary, start, end),
        "win_rate_pct": summary.get("win_rate_pct"), "yearly_return_pct": summary.get("yearly_return_pct"),
        "mean_trade_usd_95ci": summary.get("mean_trade_usd_95ci"),
    }
    if protocol is not None:
        entry["protocol"] = protocol
    return _append(entry, path)


def load(path=LEDGER):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def void(round_id, label, reason, path=LEDGER, run_id=None):
    """Mark an earlier run void because of a setup fault (not its result). The run stays in
    the ledger; a void run no longer counts as spent final data, so it can be rerun once."""
    records = load(path)
    already_voided = _voided(records)
    targets = [(i, r) for i, r in enumerate(records)
               if i not in already_voided and r.get("round") == round_id
               and r.get("label") == label
               and r.get("stage") not in ("lesson", "void", "preregister")
               and (run_id is None or r.get("run_id") == run_id)]
    if not targets:
        raise ValueError("void target not found")
    if len(targets) > 1:
        raise ValueError("void target is ambiguous; provide run_id")
    target = targets[0][1]
    entry = {"recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "round": round_id, "stage": "void", "label": label, "reason": reason}
    if target.get("run_id"):
        entry["target_run_id"] = target["run_id"]
    else:
        entry["target_recorded_at"] = target["recorded_at"]
    return _append(entry, path)


def _voided(records):
    """Indexes of voided runs; legacy void rows retain their historical label semantics."""
    live, voided = {}, set()
    for i, r in enumerate(records):
        key = (r["round"], r.get("label"))
        if r["stage"] == "void":
            if r.get("target_run_id"):
                voided |= {j for j in live.get(key, [])
                           if records[j].get("run_id") == r["target_run_id"]}
            elif r.get("target_recorded_at"):
                voided |= {j for j in live.get(key, [])
                           if records[j].get("recorded_at") == r["target_recorded_at"]}
            else:
                voided |= {j for j in live.get(key, [])}
        elif r["stage"] not in ("lesson", "preregister"):
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
    entry = {"recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
             "round": round_id, "stage": "lesson", "lesson": lesson}
    return _append(entry, path)


def research_integrity(records):
    """Protocol completeness by round. This never decides whether a strategy is profitable."""
    voided = _voided(records)
    rounds = []
    for record in records:
        if record.get("round") not in rounds:
            rounds.append(record.get("round"))
    reports = []
    for round_id in rounds:
        registrations = [r for r in records
                         if r.get("round") == round_id and r.get("stage") == "preregister"]
        runs = [r for i, r in enumerate(records)
                if r.get("round") == round_id
                and r.get("stage") not in ("lesson", "void", "preregister") and i not in voided]
        if not registrations:
            variants = {(r.get("candidate"), r.get("strategy")) for r in runs}
            reports.append({
                "round": round_id,
                "hypothesis_id": None,
                "status": "LEGACY_UNREGISTERED",
                "observed_runs": len(runs),
                "observed_variants": len(variants),
                "declared_variants": None,
                "bonferroni_alpha": None,
                "reasons": ["no causal preregistration in the ledger"],
            })
            continue
        registration = registrations[0]
        protocol_runs = [r for r in runs if r.get("protocol", {}).get("hypothesis_id")
                         == registration["hypothesis_id"]]
        reasons = []
        roles = ["candidate", *registration["controls"]]
        for variant in registration["planned_variants"]:
            for role in roles:
                seen_costs = {r["protocol"]["cost_multiplier"] for r in protocol_runs
                              if r["protocol"]["variant_id"] == variant
                              and r["protocol"]["run_role"] == role}
                missing = [cost for cost in registration["cost_multipliers"]
                           if cost not in seen_costs]
                if missing:
                    prefix = variant if role == "candidate" else f"{variant}/{role}"
                    reasons.append(f"{prefix} missing cost multipliers: {missing}")
        reports.append({
            "round": round_id,
            "hypothesis_id": registration["hypothesis_id"],
            "status": "PROTOCOL_COMPLETE" if not reasons else "PROTOCOL_INCOMPLETE",
            "observed_runs": len(protocol_runs),
            "observed_variants": len({r["protocol"]["variant_id"] for r in protocol_runs}),
            "declared_variants": len(registration["planned_variants"]),
            "bonferroni_alpha": registration["bonferroni_alpha"],
            "reasons": reasons,
        })
    return reports


def integrity_markdown(records):
    lines = ["| Round | Hypothesis | Status | Runs | Observed / declared variants | Bonferroni alpha | Gaps |",
             "|---|---|---|---|---|---|---|"]
    for report in research_integrity(records):
        declared = report["declared_variants"] if report["declared_variants"] is not None else "?"
        alpha = report["bonferroni_alpha"] if report["bonferroni_alpha"] is not None else "n/a"
        gaps = "; ".join(report["reasons"]) or "none"
        lines.append(f"| {report['round']} | {report['hypothesis_id'] or '-'} | {report['status']} | "
                     f"{report['observed_runs']} | {report['observed_variants']} / {declared} | {alpha} | {gaps} |")
    return "\n".join(lines) + "\n"


def summary_markdown(records):
    """A readable digest: one table row per run, then the lessons, newest round last."""
    voided = _voided(records)
    runs = [r for i, r in enumerate(records)
            if r["stage"] not in ("lesson", "void", "preregister") and i not in voided]
    lines = ["| Round | Stage | Candidate | Strategy | Window | Symbols | Risk | Return % | Max DD % | Trades/week | Win % |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in runs:
        lines.append(f"| {r['round']} | {r['stage']} | {r['candidate']} | {r['strategy']} | {r['window'][0]}..{r['window'][1]} | "
                     f"{'/'.join(s.replace('USDT', '') for s in r['symbols'])} | {r['risk']} | {r['return_pct']} | "
                     f"{r['max_drawdown_pct']} | {r['trades_per_week']} | {r['win_rate_pct']} |")
    lines += ["", "## Lessons", ""]
    lines += [f"- Round {r['round']}: {r['lesson']}" for r in records if r["stage"] == "lesson"]
    return "\n".join(lines) + "\n"
