#!/usr/bin/env python3
"""btc_oi_contraction_reclaim_v1, docs/research/2026-10-22-btc-oi-reclaim-v1.md (paper only).

  python scripts/reproduce_oi_reclaim.py --data-dir <forward dir> --oi <BTCUSDT_metrics_raw.csv.gz> \\
      --oi-manifest <BTCUSDT_metrics_raw_manifest.json> --frozen-commit <sha> --out-dir <dir>

Writes data_check.json, summary.json and, per window and scenario, trades / events / cashflow
CSVs and the 15m equity curve (--curve-dir, gzip). Every run is appended to the research ledger
(round 18): stage validation (both windows are seen data) when the data passed, stage
data-quality-failed with no metrics when it did not. A failed run's numbers stay in summary.json
under diagnostic_not_scored and are never scored or ledgered as a result.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_layer import oi_metrics  # noqa: E402
from src.data_layer.vision_dataset import load_bars, load_funding  # noqa: E402
from src.report.performance_summary import curve_summary  # noqa: E402
from src.research import ledger  # noqa: E402
from src.strategies import oi_reclaim  # noqa: E402

ROUND = 18
CONFIG = PROJECT_ROOT / "config" / "research" / "oi_reclaim_2026_10_22" / "btc_oi_contraction_reclaim_v1.yaml"
# scenario: (config changes, uses OI)
SCENARIOS = {
    "base_actual": {},
    "base_no_positive": {"funding_mode": "no_positive"},
    "cost2x_actual": {"taker_pct": 0.001, "slippage_pct": 0.0006},
    "cost2x_no_positive": {"taker_pct": 0.001, "slippage_pct": 0.0006, "funding_mode": "no_positive"},
    "delay15m_actual": {"entry_delay_bars": 1},
    "delay15m_no_positive": {"entry_delay_bars": 1, "funding_mode": "no_positive"},
    "price_only_no_positive": {"use_oi": False, "funding_mode": "no_positive"},
    "oi_lag60_no_positive": {"oi_lag_minutes": 60, "funding_mode": "no_positive"},
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def drawdown_pct(curve, start_equity):
    """Max drawdown on the 15m closes, the start equity being the first peak (no intrabar lows)."""
    values = np.concatenate([[float(start_equity)], curve.to_numpy(dtype=float)])
    peak = np.maximum.accumulate(values)
    return float(((peak - values) / peak).max() * 100.0)


def stats(result, cfg):
    trades = result["trades"]
    pnl = [t.net_pnl for t in trades]
    curve = result["curve"]  # 15m, stamped at the bar close; the last close is the window end
    # Stamp each value with its bar open, so the settlement at the window end stays in the window
    # (and in its own year / month) instead of being cut or opening a new year.
    by_bar = curve.copy()
    by_bar.index = curve.index - oi_reclaim.QUARTER
    summary = curve_summary(by_bar, cfg["initial_equity"], result["start"], result["end"], pnl)
    final = float(curve.iloc[-1])
    booked = sum(e["amount"] for e in result["cashflows"])
    gap = max(abs(final - cfg["initial_equity"] - sum(pnl)), abs(final - cfg["initial_equity"] - booked),
              abs(final - result["final_cash"]))
    if gap > 1e-6 * cfg["initial_equity"]:
        raise AssertionError(f"final equity {final} does not reconcile with trades {sum(pnl)} / cashflows {booked}")
    dd = drawdown_pct(curve, cfg["initial_equity"])
    summary["max_drawdown_pct"] = round(dd, 2)
    wins = sorted((p for p in pnl if p > 0), reverse=True)
    total = sum(pnl)
    summary.update({
        "expectancy_usd": round(float(np.mean(pnl)), 2) if pnl else None,
        "price_pnl_usd": round(sum(t.price_pnl for t in trades), 2),
        "funding_usd": round(sum(t.funding for t in trades), 2),
        "funding_positive_skipped_usd": round(sum(t.funding_skipped_positive for t in trades), 2),
        "fees_usd": round(sum(t.fees for t in trades), 2),
        "slippage_usd": round(sum(t.slippage_cost for t in trades), 2),
        "exit_reasons": pd.Series([t.exit_reason for t in trades]).value_counts().to_dict() if trades else {},
        "top_trade_share_of_net_pct": {k: (round(100 * sum(wins[:k]) / total, 1) if total > 0 else None) for k in (1, 2, 5)},
        "max_drawdown_pct_exact": dd, "drawdown_basis": "15m closes incl. start equity; intrabar lows not seen",
        "reconciliation": {"final_equity": final, "initial_plus_trade_net_pnl": cfg["initial_equity"] + sum(pnl),
                           "initial_plus_cashflows": cfg["initial_equity"] + booked, "max_abs_diff": gap},
        "breaker": result["breaker"], "risk_multipliers": [t.risk_multiplier for t in trades],
        "layers": result["layers"], "rejects": result["rejects"],
        "missing_oi_event_times": result["missing_oi_event_times"],
        "evidence": "chưa đủ bằng chứng (<30 giao dịch)" if len(trades) < 30 else ">= 30 giao dịch (sàn số mẫu, không phải kiểm định)",
    })
    return summary


def run_scenario(bars, funding, oi, cfg, start, end):
    """One scored run, or DATA_QUALITY_FAILED: a missing bar / funding settlement stops the run
    (no metrics at all); a price shock without its OI snapshots keeps the numbers only as an
    unscored diagnostic. Returns (summary, result or None)."""
    try:
        result = oi_reclaim.Simulator(bars, funding, oi, cfg).run(start, end)
    except oi_reclaim.DataQualityError as exc:
        return {"status": "DATA_QUALITY_FAILED", "reason": str(exc)}, None
    s = stats(result, cfg)
    if cfg["use_oi"] and result["layers"]["oi_missing"]:
        return {"status": "DATA_QUALITY_FAILED",
                "reason": f"{result['layers']['oi_missing']} price shocks without the OI snapshots at t and t-1h",
                "missing_oi_event_times": result["missing_oi_event_times"], "diagnostic_not_scored": s}, result
    return {"status": "OK", **s}, result


def preflight(bars, funding, start, end):
    """The simulator's own bar / funding schedule check for one window: OK or the failure text."""
    sim = oi_reclaim.Simulator(bars, funding, None)
    try:
        sim.preflight(pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1))
    except oi_reclaim.DataQualityError as exc:
        return f"DATA_QUALITY_FAILED: {exc}"
    return "OK"


def data_check(bars, funding, oi, dropped, manifest, windows):
    out = {"oi_manifest": oi_metrics.manifest_summary(manifest), "oi_invalid_rows_dropped": len(dropped),
           "oi_invalid_days": sorted({str(t.date()) for t in dropped}), "windows": {}}
    for name, (a, b) in windows.items():
        end = pd.Timestamp(b, tz="UTC") + pd.Timedelta(days=1)
        cov = oi_metrics.coverage(oi, a, end)
        w = bars[(bars.index >= pd.Timestamp(a, tz="UTC")) & (bars.index < end)]
        gaps = w.index.to_series().diff().dropna()
        hours = pd.date_range(pd.Timestamp(a, tz="UTC"), end, freq="h", inclusive="left")
        out["windows"][name] = {
            "oi_expected_5m": cov["expected"], "oi_missing_5m": cov["missing"], "oi_off_grid": cov["off_grid"],
            "oi_missing_hour_snapshots": int(len(hours.difference(oi.index))),
            "bars_15m": len(w), "bars_15m_gaps": int((gaps != pd.Timedelta("15min")).sum()),
            "bars_15m_zero_volume": int((w["volume"] <= 0).sum()) if "volume" in w else None,
            "funding_events": int(((funding.index >= pd.Timestamp(a, tz="UTC")) & (funding.index < end)).sum()),
            "funding_off_8h_schedule": int((((funding.index >= pd.Timestamp(a, tz="UTC")) & (funding.index < end))
                                            & ~np.isin(funding.index.hour, [0, 8, 16])).sum()),
            "preflight_15m_and_funding": preflight(bars, funding, a, b),
        }
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--oi", required=True)
    parser.add_argument("--oi-manifest", required=True)
    parser.add_argument("--frozen-commit", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--curve-dir", help="where the 15m equity curves go (default: --out-dir)")
    parser.add_argument("--no-ledger", action="store_true")
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    curves = Path(args.curve_dir) if args.curve_dir else out
    curves.mkdir(parents=True, exist_ok=True)
    spec = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    windows = spec.pop("windows")
    spec.pop("symbol")
    bars = load_bars(args.data_dir, "15m", symbol="BTCUSDT")
    funding = load_funding(args.data_dir, symbol="BTCUSDT")
    oi, dropped = oi_metrics.parse_oi(oi_metrics.load_raw(args.oi), invalid="drop")
    check = data_check(bars, funding, oi, dropped, args.oi_manifest, windows)
    check["inputs"] = {Path(p).name: sha256(p) for p in (args.oi, args.oi_manifest,
                       Path(args.data_dir) / "BTCUSDT_perp_15m.parquet", Path(args.data_dir) / "BTCUSDT_perp_funding.parquet", CONFIG)}
    check["frozen_commit"] = args.frozen_commit
    (out / "data_check.json").write_text(json.dumps(check, indent=2, default=str), encoding="utf-8")
    summary = {"frozen_commit": args.frozen_commit, "label": "SEEN_DATA_RETROSPECTIVE", "windows": {}}
    for wname, (a, b) in windows.items():
        summary["windows"][wname] = {}
        for sname, change in SCENARIOS.items():
            cfg = {**spec, **change}
            s, result = run_scenario(bars, funding, oi, cfg, a, b)
            summary["windows"][wname][sname] = s
            if result is not None:
                pd.DataFrame(oi_reclaim.trade_rows(result["trades"])).to_csv(out / f"{wname}_{sname}_trades.csv", index=False)
                pd.DataFrame(result["audit"]).to_csv(out / f"{wname}_{sname}_events.csv", index=False)
                pd.DataFrame(result["cashflows"], columns=["time", "bar", "event_id", "kind", "amount", "cash_after", "rate",
                                                           "dropped"]).to_csv(out / f"{wname}_{sname}_cashflows.csv", index=False)
                result["curve_detail"].to_csv(curves / f"{wname}_{sname}_equity_15m.csv.gz")
            scored = s["status"] == "OK"
            if not args.no_ledger:
                ledger.record(ROUND, "validation" if scored else "data-quality-failed", "OIR1", "btc_oi_contraction_reclaim_v1",
                              f"{wname} {sname} (seen)", a, b, ["BTCUSDT"], f"{cfg['risk_pct'] * 100:g}%", s if scored else {},
                              source="owner spec 2026-10-22, BTC 1h shock + OI contraction + reclaim",
                              config_files=[CONFIG], frozen_commit=args.frozen_commit)
            print(wname, sname, s["status"], s.get("total_return_pct"), s.get("completed_trades"), flush=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
