"""Research ledger (src/research/ledger.py)."""
import pytest

from src.research import ledger

SUMMARY = {"total_return_pct": 5.0, "max_drawdown_pct": 2.0, "completed_trades": 52, "win_rate_pct": 50.0,
           "yearly_return_pct": {"2021": 5.0}, "mean_trade_usd_95ci": [1, 2]}


def test_record_appends_and_counts_trades_per_week(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record(7, "dev", "V1", "london_breakout", "x", "2021-01-01", "2021-12-31", ["BTCUSDT"], "1%", SUMMARY, path=path)
    ledger.note(7, "fees ate the edge", path=path)
    records = ledger.load(path)
    assert len(records) == 2 and records[0]["trades_per_week"] == pytest.approx(1.0, abs=0.01)
    assert "fees ate the edge" in ledger.summary_markdown(records)


def test_spent_final_data_blocks_a_new_final_on_the_same_coins(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record(6, "final", "K3", "s", "A", "2021-01-01", "2026-09-30", ["XLMUSDT"], "2%", SUMMARY, path=path)
    ledger.record(6, "dev", "K3", "s", "d", "2021-01-01", "2023-12-31", ["BTCUSDT"], "2%", SUMMARY, path=path)
    records = ledger.load(path)
    with pytest.raises(ValueError):
        ledger.check_untouched(["XLMUSDT"], "2025-01-01", "2025-06-30", records)
    ledger.check_untouched(["BTCUSDT", "TRXUSDT"], "2021-01-01", "2026-09-30", records)  # dev use is not spent
    ledger.check_untouched(["XLMUSDT"], "2026-10-01", "2026-12-31", records)  # later data is fresh


def test_round7_selection_requires_five_trades_a_week():
    from scripts.reproduce_sessions import pick
    rare = {**SUMMARY, "total_return_pct": 50.0, "completed_trades": 100, "yearly_return_pct": {"2021": 1, "2022": 1, "2023": 1}}
    busy = {**SUMMARY, "total_return_pct": 5.0, "completed_trades": 900, "yearly_return_pct": {"2021": 1, "2022": 1, "2023": 1}}
    assert pick({"rare": rare, "busy": busy}) == ("busy", "full")
    assert pick({"rare": rare}) == ("rare", "none")


def test_a_void_run_frees_its_data_once(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record(7, "final", "V5", "s", "A: TRX", "2021-01-01", "2026-09-30", ["TRXUSDT"], "1%", SUMMARY, path=path)
    with pytest.raises(ValueError):
        ledger.check_untouched(["TRXUSDT"], "2021-01-01", "2026-09-30", ledger.load(path))
    ledger.void(7, "A: TRX", "no leverage table, 0 trades", path=path)
    ledger.check_untouched(["TRXUSDT"], "2021-01-01", "2026-09-30", ledger.load(path))
    ledger.record(7, "final", "V5", "s", "A: TRX", "2021-01-01", "2026-09-30", ["TRXUSDT"], "1%", SUMMARY, path=path)
    records = ledger.load(path)
    with pytest.raises(ValueError):
        ledger.check_untouched(["TRXUSDT"], "2021-01-01", "2026-09-30", records)
    assert len([r for r in records if r["stage"] == "final"]) == 2


def test_trials_and_fold_scores_are_recorded_for_later_dsr_and_pbo(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record(19, "dev", "A", "s", "a", "2021-01-01", "2021-12-31", ["BTCUSDT"], "1%", SUMMARY, path=path,
                  variants_tried=3, fold_scores={"F1": 1.5, "F2": -0.25, "F3": None})
    ledger.record(19, "dev", "B", "s", "b", "2021-01-01", "2021-12-31", ["BTCUSDT"], "1%", SUMMARY, path=path,
                  variants_tried=4, fold_scores={"F1": 0.5, "F2": 0.75, "F3": 0.0})
    ledger.record(18, "dev", "C", "s", "c", "2021-01-01", "2021-12-31", ["BTCUSDT"], "1%", SUMMARY, path=path)
    ledger.void(19, "b", "setup fault", path=path)
    records = ledger.load(path)
    assert records[2]["variants_tried"] is None and records[2]["fold_scores"] is None
    assert ledger.variants_tried_by_round(records) == {19: 4}  # a void run still counts as a trial
    assert ledger.fold_matrix(records, 19) == {"A | a": {"F1": 1.5, "F2": -0.25, "F3": None}}
    assert ledger.fold_matrix(records, 18) == {}


@pytest.mark.parametrize("trials, folds", [(0, None), (2.0, None), (True, None), (None, {}),
                                           (None, {"F1": float("nan")}), (None, {"F1": "1.0"})])
def test_bad_trials_or_fold_scores_are_refused_before_writing(tmp_path, trials, folds):
    path = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError):
        ledger.record(19, "dev", "A", "s", "a", "2021-01-01", "2021-12-31", ["BTCUSDT"], "1%", SUMMARY, path=path,
                      variants_tried=trials, fold_scores=folds)
    assert not path.exists()
