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


def test_preregistration_must_precede_the_first_round_result(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record(18, "dev", "V1", "s", "first", "2021-01-01", "2021-12-31",
                  ["BTCUSDT"], "0.5%", SUMMARY, path=path)
    before = path.read_bytes()

    with pytest.raises(ValueError, match="must precede"):
        ledger.preregister(18, "h18", ["V1"], {"matched_random": {"seed": 7, "repetitions": 100}},
                           [1.0, 2.0], "abc123", path=path)

    assert path.read_bytes() == before


def test_protocol_run_rejects_an_undeclared_variant_or_cost_before_writing(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.preregister(19, "h19", ["V1"], {"matched_random": {"seed": 7, "repetitions": 100}},
                       [1.0, 2.0], "abc123", path=path)
    before = path.read_bytes()

    for variant, cost in (("V2", 1.0), ("V1", 3.0)):
        with pytest.raises(ValueError, match="undeclared"):
            ledger.record(
                19, "dev", variant, "s", "candidate", "2021-01-01", "2021-12-31",
                ["BTCUSDT"], "0.5%", SUMMARY, frozen_commit="abc123", path=path,
                protocol={"hypothesis_id": "h19", "variant_id": variant,
                          "run_role": "candidate", "cost_multiplier": cost},
            )
        assert path.read_bytes() == before


@pytest.mark.parametrize("controls", [
    {"matched_random": {"seed": True, "repetitions": 100}},
    {"matched_random": {"seed": 7, "repetitions": 0}},
    {"matched_random": {"seed": 7}},
])
def test_preregistration_rejects_an_invalid_matched_random_spec(tmp_path, controls):
    path = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError, match="matched_random"):
        ledger.preregister(19, "h19", ["V1"], controls, [1.0], "abc123", path=path)
    assert not path.exists()


def test_preregistered_round_rejects_a_result_without_protocol_metadata(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.preregister(19, "h19", ["V1"], {}, [1.0], "abc123", path=path)
    before = path.read_bytes()

    with pytest.raises(ValueError, match="requires protocol metadata"):
        ledger.record(19, "dev", "V1", "s", "untracked", "2021-01-01", "2021-12-31",
                      ["BTCUSDT"], "0.5%", SUMMARY, frozen_commit="abc123", path=path)

    assert path.read_bytes() == before


def test_new_round_cannot_use_the_legacy_unregistered_path(tmp_path):
    path = tmp_path / "ledger.jsonl"
    with pytest.raises(ValueError, match="requires preregistration"):
        ledger.record(19, "dev", "V1", "s", "unregistered", "2021-01-01", "2021-12-31",
                      ["BTCUSDT"], "0.5%", SUMMARY, frozen_commit="abc123", path=path)
    ledger.record(18, "dev", "V1", "s", "legacy", "2021-01-01", "2021-12-31",
                  ["BTCUSDT"], "0.5%", SUMMARY, path=path)


def test_protocol_run_ties_candidate_commit_role_and_control_spec_to_registration(tmp_path):
    path = tmp_path / "ledger.jsonl"
    control = {"seed": 7, "repetitions": 100}
    ledger.preregister(19, "h19", ["V1"], {"matched_random": control}, [1.0], "abc123", path=path)

    cases = [
        ("V2", "abc123", {"hypothesis_id": "h19", "variant_id": "V1",
                            "run_role": "candidate", "cost_multiplier": 1.0}, "candidate"),
        ("V1", "different", {"hypothesis_id": "h19", "variant_id": "V1",
                               "run_role": "candidate", "cost_multiplier": 1.0}, "frozen_commit"),
        ("V1", "abc123", {"hypothesis_id": "h19", "variant_id": "V1",
                            "run_role": "latency", "cost_multiplier": 1.0}, "undeclared control"),
        ("V1", "abc123", {"hypothesis_id": "h19", "variant_id": "V1",
                            "run_role": "matched_random", "cost_multiplier": 1.0,
                            "control_spec": {"seed": 8, "repetitions": 100}}, "control_spec"),
    ]
    for candidate, commit, protocol, message in cases:
        with pytest.raises(ValueError, match=message):
            ledger.record(19, "validation", candidate, "s", message, "2021-01-01", "2021-12-31",
                          ["BTCUSDT"], "0.5%", SUMMARY, frozen_commit=commit, path=path,
                          protocol=protocol)


def test_integrity_report_requires_all_variants_costs_controls_and_frozen_commits(tmp_path):
    path = tmp_path / "ledger.jsonl"
    control = {"seed": 7, "repetitions": 100}
    ledger.preregister(19, "h19", ["V1", "V2"], {"matched_random": control},
                       [1.0, 2.0], "abc123", path=path)

    def add(variant, role, cost, frozen="abc123"):
        ledger.record(
            19, "validation", variant, "s", f"{variant}-{role}-{cost}",
            "2021-01-01", "2021-12-31", ["BTCUSDT"], "0.5%", SUMMARY,
            frozen_commit=frozen, path=path,
            protocol={"hypothesis_id": "h19", "variant_id": variant,
                      "run_role": role, "cost_multiplier": cost,
                      **({"control_spec": control} if role != "candidate" else {})},
        )

    add("V1", "candidate", 1.0)
    add("V1", "candidate", 2.0)
    add("V2", "candidate", 1.0)
    report = ledger.research_integrity(ledger.load(path))[0]
    assert report["status"] == "PROTOCOL_INCOMPLETE"
    assert "V2 missing cost multipliers: [2.0]" in report["reasons"]
    assert "V1/matched_random missing cost multipliers: [1.0, 2.0]" in report["reasons"]
    assert "V2/matched_random missing cost multipliers: [1.0, 2.0]" in report["reasons"]

    add("V2", "candidate", 2.0)
    for variant in ("V1", "V2"):
        for cost in (1.0, 2.0):
            add(variant, "matched_random", cost)
    report = ledger.research_integrity(ledger.load(path))[0]
    assert report == {
        "round": 19,
        "hypothesis_id": "h19",
        "status": "PROTOCOL_COMPLETE",
        "observed_runs": 8,
        "observed_variants": 2,
        "declared_variants": 2,
        "bonferroni_alpha": 0.025,
        "reasons": [],
    }


def test_integrity_report_labels_legacy_rounds_and_hides_preregistration_from_runs(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger.record(18, "validation", "OIR1", "s", "legacy", "2024-01-01", "2024-12-31",
                  ["BTCUSDT"], "0.5%", SUMMARY, path=path)
    ledger.preregister(19, "h19", ["V1"], {}, [1.0], "abc123", path=path)
    records = ledger.load(path)

    reports = {r["round"]: r for r in ledger.research_integrity(records)}
    assert reports[18]["status"] == "LEGACY_UNREGISTERED"
    assert reports[18]["observed_runs"] == 1
    assert reports[19]["status"] == "PROTOCOL_INCOMPLETE"
    assert "h19" in ledger.integrity_markdown(records)
    assert "h19" not in ledger.summary_markdown(records)


def test_void_requires_an_unambiguous_run_and_targets_only_that_run(tmp_path):
    path = tmp_path / "ledger.jsonl"
    first = ledger.record(18, "final", "V1", "s", "same", "2021-01-01", "2021-12-31",
                          ["BTCUSDT"], "0.5%", SUMMARY, path=path)
    second = ledger.record(18, "final", "V2", "s", "same", "2022-01-01", "2022-12-31",
                           ["ETHUSDT"], "0.5%", SUMMARY, path=path)

    with pytest.raises(ValueError, match="ambiguous"):
        ledger.void(18, "same", "one is wrong", path=path)
    ledger.void(18, "same", "first is wrong", path=path, run_id=first["run_id"])

    spent = ledger.spent_final_data(ledger.load(path))
    assert "BTCUSDT" not in spent
    assert spent == {"ETHUSDT": [("2022-01-01", "2022-12-31")]}
    assert first["run_id"] != second["run_id"]
