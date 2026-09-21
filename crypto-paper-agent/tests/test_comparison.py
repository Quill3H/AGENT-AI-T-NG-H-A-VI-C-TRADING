import pandas as pd
import pytest
from src.research.comparison import (
    walk_forward_splits,
    compare_metrics,
    run_walk_forward,
)


def frame(n=20):
    return pd.DataFrame(
        {"close": range(n)},
        index=pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC"),
    )


def test_walk_forward_rejects_unsorted_duplicate_non_utc():
    for f in [
        frame().iloc[::-1],
        pd.concat([frame(), frame().iloc[:1]]),
        frame().tz_convert(None),
    ]:
        with pytest.raises((TypeError, ValueError)):
            walk_forward_splits(f, 5, 3)


def test_walk_forward_no_train_test_overlap_and_oos_aggregate():
    f = frame()
    folds = walk_forward_splits(f, 5, 3, 3)
    assert all(x["train_end"] < x["test_start"] for x in folds)
    runners = {
        "a": lambda train, test: {"total_net_pnl": len(test), "total_trades": 2},
        "b": lambda train, test: {"total_net_pnl": -1, "sample_count": 1},
    }
    rows, agg = run_walk_forward(f, runners, 5, 3, 3)
    assert len(rows) == len(folds) * 2 and set(agg.strategy) == {"a", "b"}
    assert agg.iloc[0].strategy == "a"


def test_compare_requires_engine_metric_contract():
    with pytest.raises(KeyError):
        compare_metrics({"bad": {"pnl": 1}})


@pytest.mark.parametrize(
    "train,test,step",
    [(0, 3, None), (5, 0, None), (5, 3, 0), (5, 3, 2), (True, 3, None), (5, 3.5, None)],
)
def test_split_sizes_and_overlap_fail_closed(train, test, step):
    with pytest.raises((ValueError, TypeError)):
        walk_forward_splits(frame(), train, test, step)


def test_four_strategy_workflow_real_execution_and_artifacts(tmp_path):
    from src.research.synthetic import comparison_datasets
    from src.research.workflow import run_comparison
    import json

    cfg = {"account": {"initial_equity_usd": 10000}, "news_filter": {"enabled": False}}
    report = run_comparison(
        comparison_datasets(), cfg, tmp_path, 1440, 1440, source="SYNTHETIC_TEST"
    )
    assert len(report["folds"]) == 4
    assert set(row["strategy"] for row in report["folds"]) == {
        "trend_following",
        "breakout_retest",
        "smc_liquidity_sweep",
        "funding_arbitrage",
    }
    assert all(row["bars"] > 0 for row in report["folds"])
    assert report["account_mode"] == "independent_reset_accounts_per_fold"
    assert (tmp_path / "fold_reports.csv").is_file()
    assert list(tmp_path.rglob("trades.sqlite"))
    assert list(tmp_path.rglob("funding_arbitrage.report.json"))
    assert (
        json.loads((tmp_path / "walk_forward.report.json").read_text())["report"][
            "datasets"
        ]["basket"]["source"]
        == "SYNTHETIC_TEST"
    )


def test_research_manifest_matches_exact_file_and_sqlite_bytes(tmp_path):
    import hashlib, json, sqlite3
    from src.research.artifacts import persist_research_run

    persist_research_run(tmp_path, "fixture", {}, {"result": 12.0})
    raw = (tmp_path / "fixture.report.json").read_bytes()
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert hashlib.sha256(raw).hexdigest() == manifest["files"]["fixture.report.json"]
    with sqlite3.connect(tmp_path / "research.sqlite") as db:
        digest, payload = db.execute("SELECT sha256, payload FROM runs").fetchone()
    assert payload.encode("utf-8") == raw
    assert digest == hashlib.sha256(raw).hexdigest()
    persist_research_run(tmp_path, "fixture", {}, {"result": 12.0})
    with pytest.raises(ValueError, match="identity conflict"):
        persist_research_run(tmp_path, "fixture", {}, {"result": 13.0})
