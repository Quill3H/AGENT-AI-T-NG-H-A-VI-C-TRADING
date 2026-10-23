"""
src/research/model_governance.py
================================
Pre-registered rules for any future model (the ML study in
docs/research/thiet-ke-bang-chung-hoc-may-2026-10-23.md, or a rule strategy): probability
calibration, a champion/challenger decision with numeric promote/rollback thresholds, and one
scorecard row per model. Pure functions; nothing here trains a model, reads market data or places
an order.

Starting point: the champion is "no model" (cash, NO_TRADES), so a challenger is promoted only
when it clears every threshold on forward paper data collected after its lock date. Every
challenger counts as one more trial for the Deflated Sharpe budget (ledger.variants_tried).
"""
import math
from dataclasses import asdict, dataclass

import numpy as np

NO_MODEL = "no_model_cash"


# ------------------------------------------------------------------ calibration
def _checked(p, y):
    p, y = np.asarray(p, dtype=float), np.asarray(y, dtype=float)
    if p.shape != y.shape or p.ndim != 1 or len(p) == 0:
        raise ValueError("p and y must be 1-d and the same non-zero length")
    if not np.all((p >= 0) & (p <= 1)) or not np.all((y == 0) | (y == 1)):
        raise ValueError("p must be in [0, 1] and y must be 0/1")
    return p, y


def brier(p, y):
    p, y = _checked(p, y)
    return float(np.mean((p - y) ** 2))


def reliability_table(p, y, bins=10):
    """Rows (bin low, bin high, count, mean predicted, observed rate) for equal-width bins."""
    p, y = _checked(p, y)
    edges = np.linspace(0.0, 1.0, bins + 1)
    which = np.clip(np.searchsorted(edges, p, side="right") - 1, 0, bins - 1)
    rows = []
    for b in range(bins):
        mask = which == b
        if mask.any():
            rows.append({"low": float(edges[b]), "high": float(edges[b + 1]), "count": int(mask.sum()),
                         "mean_predicted": float(p[mask].mean()), "observed_rate": float(y[mask].mean())})
    return rows


def expected_calibration_error(p, y, bins=10):
    rows, n = reliability_table(p, y, bins), len(p)
    return float(sum(r["count"] / n * abs(r["mean_predicted"] - r["observed_rate"]) for r in rows))


def fit_isotonic(p, y):
    """Isotonic (pool-adjacent-violators) calibration map fitted on a calibration slice that the
    model was not trained on (the inner validation tail of each training window). Returns a
    function from raw probabilities to calibrated ones (step function, clipped at the ends)."""
    p, y = _checked(p, y)
    order = np.argsort(p, kind="stable")
    xs, blocks = p[order], [[float(v), 1.0] for v in y[order]]  # [mean, weight]
    starts = list(range(len(blocks)))
    merged, merged_start = [], []
    for start, (mean, weight) in zip(starts, blocks):
        merged.append([mean, weight])
        merged_start.append(start)
        while len(merged) > 1 and merged[-2][0] > merged[-1][0]:
            m2, w2 = merged.pop()
            merged_start.pop()
            m1, w1 = merged[-1]
            merged[-1] = [(m1 * w1 + m2 * w2) / (w1 + w2), w1 + w2]
    thresholds = np.array([xs[s] for s in merged_start])
    values = np.array([m for m, _ in merged])

    def calibrate(raw):
        raw = np.asarray(raw, dtype=float)
        idx = np.clip(np.searchsorted(thresholds, raw, side="right") - 1, 0, len(values) - 1)
        return values[idx]

    return calibrate


def break_even_probability(round_trip_cost, move):
    """Hit rate needed to break even with symmetric +/-move outcomes: 0.5 + cost / (2 * move)."""
    if move <= 0 or round_trip_cost < 0:
        raise ValueError("move must be > 0 and cost >= 0")
    return 0.5 + round_trip_cost / (2.0 * move)


# ------------------------------------------------------------------ performance
def probabilistic_sharpe(returns, benchmark_sharpe=0.0):
    """PSR (Bailey & Lopez de Prado 2012) on per-period returns; benchmark in the same units."""
    r = np.asarray(returns, dtype=float)
    if len(r) < 3 or r.std(ddof=1) == 0:
        return None
    sr = r.mean() / r.std(ddof=1)
    z = (r - r.mean()) / r.std(ddof=0)
    skew, kurt = float(np.mean(z ** 3)), float(np.mean(z ** 4))
    denom = 1 - skew * sr + (kurt - 1) / 4 * sr ** 2
    if denom <= 0:
        return None
    stat = (sr - benchmark_sharpe) * math.sqrt(len(r) - 1) / math.sqrt(denom)
    return 0.5 * (1 + math.erf(stat / math.sqrt(2)))


def max_drawdown(equity):
    e = np.asarray(equity, dtype=float)
    peaks = np.maximum.accumulate(e)
    return float(np.max((peaks - e) / peaks)) if len(e) else 0.0


@dataclass(frozen=True)
class Scorecard:
    """One row per model (or rule strategy) on one evaluation period."""
    model: str
    period: str
    data_kind: str  # "forward_paper" is the only kind that can promote
    days: int
    trades: int
    annual_return_pct: float
    sharpe_annual: float
    psr: object
    max_dd_pct: float
    brier: object = None
    ece: object = None
    hit_rate: object = None
    break_even_hit_rate: object = None

    def to_dict(self):
        return asdict(self)


def scorecard(model, period, data_kind, daily_returns, equity, trades, probs=None, outcomes=None,
              break_even=None):
    r = np.asarray(daily_returns, dtype=float)
    days = len(r)
    growth = float(np.prod(1 + r)) if days else 1.0
    annual = (growth ** (365.0 / days) - 1) * 100 if days else 0.0
    sd = r.std(ddof=1) if days > 1 else 0.0
    cal = {}
    if probs is not None:
        cal = {"brier": round(brier(probs, outcomes), 6), "ece": round(expected_calibration_error(probs, outcomes), 6),
               "hit_rate": float(np.mean(np.asarray(outcomes, dtype=float)))}
    psr = probabilistic_sharpe(r)
    return Scorecard(model=model, period=period, data_kind=data_kind, days=days, trades=int(trades),
                     annual_return_pct=round(annual, 4),
                     sharpe_annual=round(float(r.mean() / sd * math.sqrt(365)) if sd > 0 else 0.0, 4),
                     psr=None if psr is None else round(psr, 4), max_dd_pct=round(max_drawdown(equity) * 100, 4),
                     break_even_hit_rate=break_even, **cal)


# ------------------------------------------------------------------ champion / challenger
@dataclass(frozen=True)
class PromotionRules:
    """Numbers fixed before any challenger exists. Changing them is a new registered study."""
    min_days: int = 180
    min_trades: int = 100
    min_psr: float = 0.95
    min_annual_return_pct: float = 5.9  # bank deposit baseline
    max_dd_vs_champion: float = 1.25  # ignored while the champion is cash
    max_dd_pct: float = 30.0
    max_ece: float = 0.05
    min_hit_margin: float = 0.0  # hit rate must beat the cost break-even by at least this
    min_days_between_promotions: int = 90
    rollback_dd_multiple: float = 1.5  # of the dev out-of-sample drawdown
    rollback_psr_after_min_days: float = 0.05
    rollback_ece: float = 0.10


def promotion_decision(champion, challenger, rules=PromotionRules(), days_since_last_promotion=None):
    """'PROMOTE' only if every check passes; otherwise 'KEEP_CHAMPION' with the failed checks."""
    c = challenger
    checks = {
        "forward_paper_only": c.data_kind == "forward_paper",
        "min_days": c.days >= rules.min_days,
        "min_trades": c.trades >= rules.min_trades,
        "psr": c.psr is not None and c.psr >= rules.min_psr,
        "annual_return": c.annual_return_pct >= rules.min_annual_return_pct,
        "max_dd": c.max_dd_pct <= rules.max_dd_pct and (
            champion.model == NO_MODEL or c.max_dd_pct <= rules.max_dd_vs_champion * max(champion.max_dd_pct, 1e-9)),
        "beats_champion_return": champion.model == NO_MODEL or c.annual_return_pct > champion.annual_return_pct,
        "calibration": c.ece is None or c.ece <= rules.max_ece,
        "hit_rate_vs_break_even": c.hit_rate is None or c.break_even_hit_rate is None
        or c.hit_rate >= c.break_even_hit_rate + rules.min_hit_margin,
        "cool_down": days_since_last_promotion is None or days_since_last_promotion >= rules.min_days_between_promotions,
    }
    failed = [k for k, ok in checks.items() if not ok]
    return {"decision": "KEEP_CHAMPION" if failed else "PROMOTE", "failed": failed, "checks": checks}


def rollback_decision(live, dev_oos_max_dd_pct, rules=PromotionRules(), data_quality_ok=True):
    """For the running champion: 'ROLLBACK' to the previous champion (or cash) on any trigger."""
    triggers = []
    if not data_quality_ok:
        triggers.append("data_quality")
    if live.max_dd_pct > rules.rollback_dd_multiple * dev_oos_max_dd_pct:
        triggers.append("drawdown")
    if live.days >= rules.min_days and live.psr is not None and live.psr < rules.rollback_psr_after_min_days:
        triggers.append("psr")
    if live.ece is not None and live.ece > rules.rollback_ece:
        triggers.append("calibration_drift")
    return {"decision": "ROLLBACK" if triggers else "KEEP", "triggers": triggers}
