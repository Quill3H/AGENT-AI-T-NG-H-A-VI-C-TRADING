"""Calibration, scorecard and champion/challenger rules (src/research/model_governance.py); offline."""
import numpy as np
import pytest

from src.research import model_governance as g


def test_calibration_metrics_on_known_cases():
    y = np.array([0, 1, 0, 1])
    assert g.brier([0, 1, 0, 1], y) == 0.0 and g.brier([0.5] * 4, y) == pytest.approx(0.25)
    assert g.expected_calibration_error([0.5] * 4, y) == pytest.approx(0.0)
    assert g.expected_calibration_error([0.9] * 4, y) == pytest.approx(0.4)
    with pytest.raises(ValueError):
        g.brier([1.2], [1])


def test_isotonic_fixes_an_overconfident_model_on_held_out_data():
    rng = np.random.default_rng(3)
    true_p = rng.uniform(0.3, 0.7, 20000)
    y = (rng.uniform(size=true_p.size) < true_p).astype(int)
    raw = np.clip(0.5 + 2.0 * (true_p - 0.5), 0, 1)  # twice too confident
    calibrate = g.fit_isotonic(raw[:10000], y[:10000])
    before = g.expected_calibration_error(raw[10000:], y[10000:])
    after = g.expected_calibration_error(calibrate(raw[10000:]), y[10000:])
    assert before > 0.05 and after < 0.02
    assert np.all(np.diff(calibrate(np.linspace(0, 1, 101))) >= 0)  # monotone


def test_break_even_matches_the_design_note():
    assert g.break_even_probability(0.0016, 0.03) == pytest.approx(0.52667, abs=1e-4)


def test_psr_is_high_for_a_steady_edge_and_low_for_noise():
    rng = np.random.default_rng(5)
    assert g.probabilistic_sharpe(rng.normal(0.002, 0.01, 365)) > 0.95
    assert g.probabilistic_sharpe(rng.normal(-0.001, 0.01, 365)) < 0.5


def card(model="M", data_kind="forward_paper", days=200, trades=120, ret=12.0, psr=0.97, dd=10.0, ece=0.03,
         hit=0.56, be=0.527):
    return g.Scorecard(model, "2027", data_kind, days, trades, ret, 1.5, psr, dd, 0.24, ece, hit, be)


CASH = g.Scorecard(g.NO_MODEL, "2027", "forward_paper", 200, 0, 0.0, 0.0, None, 0.0)


def test_promotion_needs_every_check_and_forward_data():
    assert g.promotion_decision(CASH, card())["decision"] == "PROMOTE"
    cases = {"forward_paper_only": card(data_kind="dev_walk_forward"), "min_days": card(days=90),
             "min_trades": card(trades=40), "psr": card(psr=0.9), "annual_return": card(ret=5.0),
             "max_dd": card(dd=35.0), "calibration": card(ece=0.08), "hit_rate_vs_break_even": card(hit=0.52)}
    for check, challenger in cases.items():
        result = g.promotion_decision(CASH, challenger)
        assert result["decision"] == "KEEP_CHAMPION" and check in result["failed"]
    champion = card(model="old", ret=15.0, dd=6.0)
    failed = g.promotion_decision(champion, card(ret=12.0, dd=10.0))["failed"]
    assert {"max_dd", "beats_champion_return"} <= set(failed)
    assert "cool_down" in g.promotion_decision(CASH, card(), days_since_last_promotion=30)["failed"]


def test_rollback_triggers():
    assert g.rollback_decision(card(), dev_oos_max_dd_pct=10.0)["decision"] == "KEEP"
    assert g.rollback_decision(card(dd=16.0), 10.0)["triggers"] == ["drawdown"]
    assert g.rollback_decision(card(psr=0.02), 10.0)["triggers"] == ["psr"]
    assert g.rollback_decision(card(days=100, psr=0.02), 10.0)["decision"] == "KEEP"  # too early to judge
    assert g.rollback_decision(card(ece=0.12), 10.0)["triggers"] == ["calibration_drift"]
    assert g.rollback_decision(card(), 10.0, data_quality_ok=False)["triggers"] == ["data_quality"]


def test_scorecard_from_returns():
    rng = np.random.default_rng(1)
    r = rng.normal(0.0005, 0.01, 365)
    equity = 10000 * np.cumprod(1 + r)
    p = rng.uniform(0.4, 0.6, 50)
    y = (rng.uniform(size=50) < p).astype(int)
    row = g.scorecard("M", "2027", "forward_paper", r, equity, 80, p, y, break_even=0.527).to_dict()
    assert row["days"] == 365 and row["trades"] == 80 and 0 <= row["max_dd_pct"] < 100
    assert row["annual_return_pct"] == pytest.approx((np.prod(1 + r) - 1) * 100, rel=1e-6)
    assert row["brier"] is not None and row["break_even_hit_rate"] == 0.527
