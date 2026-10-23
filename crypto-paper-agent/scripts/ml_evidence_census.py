#!/usr/bin/env python3
"""Count how much evidence the held data can give a machine-learning study (paper only, no model).

  python scripts/ml_evidence_census.py --forward-dir <binance-vision-usdm-forward> \\
      --base-dir <binance-vision-usdm> --out <census.json>

Design: docs/reports-vi/thiet-ke-bang-chung-hoc-may-2026-10-23.md. The script fits nothing and selects
nothing. Per coin, timeframe and period it counts bars, triple-barrier events (long side, real
costs and funding), their overlap (average uniqueness) and the cross-coin return correlation,
then prints the sample sizes the power formulas ask for. It only opens data that a final test
already spent or earlier rounds used for development: `guard_seen` refuses the reserved coins
and anything after the last spent day, so the design phase cannot consume fresh evidence.
"""
import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_layer.vision_dataset import load_bars, load_funding  # noqa: E402
from src.research import ledger  # noqa: E402
from src.research.ml import stats  # noqa: E402

TOP10 = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "BNBUSDT", "SOLUSDT", "DOGEUSDT", "TRXUSDT", "ADAUSDT", "LINKUSDT", "AVAXUSDT"]
OTHERS = ["ETCUSDT", "ATOMUSDT", "NEARUSDT", "FILUSDT", "XLMUSDT", "BCHUSDT", "UNIUSDT", "AAVEUSDT", "DOTUSDT", "LTCUSDT"]
# Downloaded in round 7, dropped by amendment 1 before use, never in a final: kept unopened.
RESERVED = {"ALGOUSDT", "VETUSDT", "SANDUSDT"}
START = "2021-01-01"
LAST_SPENT_DAY = "2026-10-17"
PERIODS = {"P1_2021_2023": ("2021-01-01", "2023-12-31"), "P2_2024_2026_09": ("2024-01-01", "2026-09-30"),
           "P3_2026_10_01_17": ("2026-10-01", "2026-10-17")}
COST_ROUND_TRIP = 2 * (0.0005 + 0.0003)  # taker + slippage per side, config/default_config.yaml
# Measurement grid, fixed before any count was read; none of these is a model choice.
GRID = {"A_1h_k2_H24": ("1h", 2.0, 24), "B_4h_k2_H6": ("4h", 2.0, 6),
        "C_4h_k3_H30": ("4h", 3.0, 30), "D_1d_k2_H5": ("1d", 2.0, 5)}
RULE = {"1h": "1h", "4h": "4h", "1d": "1D"}
N = statistics.NormalDist()


def guard_seen(symbol, end, records):
    """Refuse a coin or day no earlier round has consumed (the future final/forward data)."""
    if symbol in RESERVED:
        raise ValueError(f"{symbol} is reserved untouched data")
    if end > LAST_SPENT_DAY:
        raise ValueError(f"{end} is after the last spent day {LAST_SPENT_DAY}")
    if symbol not in ledger.spent_final_data(records):
        raise ValueError(f"{symbol} has no spent final window")


def bars_for(directory, symbol, timeframe, end):
    raw = load_bars(directory, "15m", symbol=symbol)
    raw = raw[(raw.index >= START) & (raw.index < pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1))]
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return raw.resample(RULE[timeframe], label="left", closed="left").agg(agg).dropna()


def atr(frame, n=14):
    prev = frame["close"].shift()
    tr = pd.concat([frame["high"] - frame["low"], (frame["high"] - prev).abs(), (frame["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def cusum_events(close, span=100):
    """Symmetric CUSUM on log returns, threshold = past EWM std (known at the bar's close)."""
    r = np.log(close).diff()
    h = r.ewm(span=span, adjust=False).std().shift()
    events, s_pos, s_neg = [], 0.0, 0.0
    for i, (ri, hi) in enumerate(zip(r.to_numpy(), h.to_numpy())):
        if not (np.isfinite(ri) and np.isfinite(hi)):
            continue
        s_pos, s_neg = max(0.0, s_pos + ri), min(0.0, s_neg + ri)
        if s_pos > hi or s_neg < -hi:
            events.append(i)
            s_pos = s_neg = 0.0
    return events


def triple_barrier(frame, funding, k, horizon):
    """Long-side events: signal at bar i's close, fill at bar i+1's open, stop and target k ATR away,
    exit at the vertical barrier's close. Both barriers inside one bar count as the stop."""
    o, hi, lo, c = (frame[col].to_numpy() for col in ("open", "high", "low", "close"))
    a = atr(frame).to_numpy()
    idx, n = frame.index, len(frame)
    step = idx[1] - idx[0]
    f_times = funding.index
    f_cum = np.concatenate([[0.0], np.cumsum(funding["funding_rate"].to_numpy())])
    rows = []
    for i in cusum_events(frame["close"]):
        if i + 1 >= n or not np.isfinite(a[i]):
            continue
        entry = o[i + 1]
        up, dn = entry * (1 + k * a[i] / c[i]), entry * (1 - k * a[i] / c[i])
        last = min(i + horizon, n - 1)
        exit_price, exit_j, kind = c[last], last, "vertical"
        for j in range(i + 1, last + 1):
            if lo[j] <= dn:
                exit_price, exit_j, kind = dn, j, "stop"
                break
            if hi[j] >= up:
                exit_price, exit_j, kind = up, j, "target"
                break
        t0, t1 = idx[i + 1], idx[exit_j] + step
        a0, a1 = f_times.searchsorted(t0, side="right"), f_times.searchsorted(t1, side="right")
        fund = float(f_cum[a1] - f_cum[a0])  # settlements in (fill, exit]; long pays positive funding
        gross = exit_price / entry - 1
        rows.append({"start": i + 1, "end": exit_j, "kind": kind, "gross": gross, "funding": fund,
                     "net_long": gross - COST_ROUND_TRIP - fund, "net_short": -gross - COST_ROUND_TRIP + fund,
                     "time": idx[i]})
    return pd.DataFrame(rows), n


def uniqueness(events, n):
    if events.empty:
        return np.array([])
    conc = np.zeros(n + 1)
    np.add.at(conc, events["start"].to_numpy(), 1)
    np.add.at(conc, events["end"].to_numpy() + 1, -1)
    conc = np.cumsum(conc)[:n]
    inv = np.concatenate([[0.0], np.cumsum(1.0 / np.where(conc > 0, conc, np.inf))])
    s, e = events["start"].to_numpy(), events["end"].to_numpy()
    return (inv[e + 1] - inv[s]) / (e - s + 1)


def lag1(x):
    x = np.asarray(x, dtype=float)
    return float(np.corrcoef(x[:-1], x[1:])[0, 1]) if len(x) > 3 and x.std() > 0 else 0.0


def summarize(ev, u):
    if ev.empty:
        return {"events": 0}
    sign = np.sign(ev["net_long"].to_numpy())
    rho = lag1(sign)
    ess_factor = max((1 - rho) / (1 + rho), 0.0) if rho > 0 else 1.0
    abs_g = ev["gross"].abs()
    return {
        "events": int(len(ev)), "avg_uniqueness": round(float(u.mean()), 3), "sum_uniqueness": round(float(u.sum()), 1),
        "label_lag1_autocorr": round(rho, 3), "n_eff": round(float(u.sum()) * ess_factor, 1),
        "pct_target": round(100 * float((ev["kind"] == "target").mean()), 1),
        "pct_stop": round(100 * float((ev["kind"] == "stop").mean()), 1),
        "pct_vertical": round(100 * float((ev["kind"] == "vertical").mean()), 1),
        "median_abs_gross_pct": round(100 * float(abs_g.median()), 3),
        "cost_over_median_move": round(COST_ROUND_TRIP / float(abs_g.median()), 3),
        "pct_both_sides_lose": round(100 * float(((ev["net_long"] < 0) & (ev["net_short"] < 0)).mean()), 1),
        "pct_net_long_positive": round(100 * float((ev["net_long"] > 0).mean()), 1),
        "mean_net_long_pct": round(100 * float(ev["net_long"].mean()), 4),
        "mean_funding_long_pct": round(100 * float(ev["funding"].mean()), 4),
    }


def correlation_block(closes):
    out = {}
    for name, (a, b) in PERIODS.items():
        rets = pd.DataFrame({s: np.log(c[(c.index >= a) & (c.index <= b + " 23:59")]).diff() for s, c in closes.items()}).dropna(how="all")
        rets = rets.dropna(axis=1, thresh=int(0.9 * len(rets)))
        corr = rets.corr().to_numpy()
        m = corr.shape[0]
        rho = float(corr[~np.eye(m, dtype=bool)].mean())
        resid = rets.sub(rets.mean(axis=1), axis=0).corr().to_numpy()  # minus the equal-weight market
        rho_r = float(resid[~np.eye(m, dtype=bool)].mean())
        out[name] = {"coins": m, "days": int(len(rets)), "mean_pairwise_corr": round(rho, 3),
                     "m_eff": round(m / (1 + (m - 1) * rho), 2), "mean_pairwise_corr_market_neutral": round(rho_r, 3)}
    return out


# Power formulas (one-sided alpha, power 1 - beta).
def z(p):
    return N.inv_cdf(p)


def n_for_ic(ic, alpha=0.05, power=0.8):
    return math.ceil(((z(1 - alpha) + z(power)) / math.atanh(ic)) ** 2 + 3)


def n_for_accuracy(p1, p0=0.5, alpha=0.05, power=0.8):
    num = z(1 - alpha) * math.sqrt(p0 * (1 - p0)) + z(power) * math.sqrt(p1 * (1 - p1))
    return math.ceil((num / (p1 - p0)) ** 2)


def min_track_record(sr, sr_star=0.0, skew=0.0, kurt=3.0, alpha=0.05):
    """Bailey & Lopez de Prado (2012) MinTRL, in observations of the SR's own frequency."""
    return math.ceil(1 + (1 - skew * sr + (kurt - 1) / 4 * sr ** 2) * (z(1 - alpha) / (sr - sr_star)) ** 2)


def expected_max_sr(trials, var_sr):
    """Expected maximum Sharpe of `trials` skill-less strategies (Bailey et al. 2014, DSR)."""
    return stats.expected_max_sharpe(trials, var_sr)


def power_tables(trials_seen):
    days_per_year = 365
    out = {
        "n_independent_for_ic": {str(ic): n_for_ic(ic) for ic in (0.02, 0.03, 0.05, 0.08, 0.10)},
        "n_independent_for_accuracy": {str(p): n_for_accuracy(p) for p in (0.51, 0.52, 0.53, 0.55)},
        "min_track_record_days": {}, "min_track_record_trades": {},
        "trials_already_on_seen_data": trials_seen,
    }
    for sr_year in (0.5, 1.0, 1.5, 2.0, 3.0):
        sr_d = sr_year / math.sqrt(days_per_year)
        out["min_track_record_days"][str(sr_year)] = {
            "normal": min_track_record(sr_d), "skew-0.5_kurt8": min_track_record(sr_d, skew=-0.5, kurt=8)}
    for sr_trade in (0.05, 0.10, 0.15, 0.20, 0.30):
        out["min_track_record_trades"][str(sr_trade)] = min_track_record(sr_trade, skew=1.0, kurt=6)
    # Sharpe bar a deflated test raises after K trials: per-day SR, variance of SR estimates across
    # trials taken as 1/T for T days (skill-less strategies), annualised for reading.
    bars = {}
    for trials in (10, 50, 100, 300, 1000):
        for t_days in (365, 730, 1095, 2100):
            bars[f"K{trials}_T{t_days}"] = round(expected_max_sr(trials, 1 / t_days) * math.sqrt(days_per_year), 2)
    out["deflated_sr_bar_annualised"] = bars
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--forward-dir", required=True)
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    records = ledger.load()
    trials_seen = sum(1 for r in records if r["stage"] not in ("lesson", "void"))
    census, closes = {}, {}
    for symbol in TOP10 + OTHERS:
        directory, end = (args.forward_dir, LAST_SPENT_DAY) if symbol in TOP10 else (args.base_dir, "2026-09-30")
        guard_seen(symbol, end, records)
        funding = load_funding(directory, symbol)
        census[symbol] = {}
        frames = {tf: bars_for(directory, symbol, tf, end) for tf in RULE}
        closes[symbol] = frames["1d"]["close"]
        for key, (tf, k, horizon) in GRID.items():
            ev, n = triple_barrier(frames[tf], funding, k, horizon)
            u = uniqueness(ev, n)
            per = {}
            for name, (a, b) in PERIODS.items():
                if b > end:
                    continue
                sel = (ev["time"] >= a) & (ev["time"] <= b + " 23:59") if not ev.empty else []
                bars_n = int(((frames[tf].index >= a) & (frames[tf].index <= b + " 23:59")).sum())
                per[name] = {"bars": bars_n, "non_overlapping_labels": bars_n // horizon,
                             **summarize(ev[sel].reset_index(drop=True), u[np.asarray(sel)] if len(u) else u)}
            census[symbol][key] = per
        print(symbol, {k: v["P1_2021_2023"]["events"] for k, v in census[symbol].items()}, flush=True)
    result = {"cost_round_trip": COST_ROUND_TRIP, "grid": GRID, "periods": PERIODS, "reserved_unopened": sorted(RESERVED),
              "last_spent_day": LAST_SPENT_DAY, "census": census, "correlation_daily": {
                  "top10": correlation_block({s: closes[s] for s in TOP10}),
                  "all20": correlation_block(closes)}, "power": power_tables(trials_seen)}
    Path(args.out).write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"correlation_daily": result["correlation_daily"], "power": result["power"]}, indent=1))


if __name__ == "__main__":
    main()
