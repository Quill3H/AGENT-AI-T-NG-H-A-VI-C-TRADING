"""Self-written ML framework (src/research/ml): leak checks, labels, purged splits, statistics,
models and gate D on synthetic panels only (design docs/reports-vi/thiet-ke-bang-chung-hoc-may-2026-10-23.md)."""
import numpy as np
import pandas as pd
import pytest

from src.research.ml import features, gates, labels, models, splits, stats, synthetic, walkforward


# ------------------------------------------------------------------ helpers
def _bars(closes, freq="4h", start="2024-01-01"):
    idx = pd.date_range(start, periods=len(closes), freq=freq, tz="UTC")
    c = np.asarray(closes, dtype=float)
    o = np.concatenate([[c[0]], c[:-1]])
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.001, "low": np.minimum(o, c) * 0.999,
                         "close": c, "volume": 1.0}, index=idx)


@pytest.fixture(scope="module")
def small_panel():
    return synthetic.panel(n_coins=3, days=500, seed=1)


def _inputs(frames, fundings, sym="C1USDT"):
    return {"bars": frames[sym], "funding": fundings[sym], "context": {"BTCUSDT": frames["BTCUSDT"]}}


def _pipeline(edge, days=900, seed=0):
    frames, fundings = synthetic.panel(n_coins=6, days=days, edge=edge, seed=seed)
    feats = []
    for sym, f in frames.items():
        ctx = () if sym == "BTCUSDT" else ("BTCUSDT",)
        built = features.build({"bars": f, "funding": fundings[sym], "context": {"BTCUSDT": frames["BTCUSDT"]}}, context=ctx)
        feats.append(built.assign(symbol=sym).rename_axis("time").reset_index())
    feats = pd.concat(feats)
    cols = [c for c in feats.columns if c not in ("time", "symbol") and not c.startswith("BTCUSDT_")]
    panel = labels.market_neutral_labels({s: f["4h"] for s, f in frames.items()}, fundings, horizon=6)
    data = panel.merge(feats[["time", "symbol"] + cols], on=["time", "symbol"]).dropna()
    return walkforward.cross_sectional_demean(data, cols), cols


def _evaluate(data, cols, spec):
    preds = walkforward.run(data, cols, spec, "2022-03-01", "2023-06-30", train_days=365)
    book, pnl = walkforward.long_short_book(preds)
    ic = stats.information_coefficients(preds.assign(pred=preds["score"])[["time", "pred", "ret"]])
    return preds, book, pnl, ic


# ------------------------------------------------------------------ labels
def test_triple_barrier_sides_costs_funding_and_gap():
    closes = [100.0] * 30 + [100.0, 97.0, 80.0, 80.0, 80.0, 80.0, 80.0]
    frame = _bars(closes)
    frame.iloc[32, frame.columns.get_loc("open")] = 85.0  # gap through a long stop
    funding = pd.DataFrame({"funding_rate": [0.001]}, index=pd.DatetimeIndex([frame.index[31] + pd.Timedelta(hours=1)]))
    long_ = labels.triple_barrier(frame, funding, [30], k=2.0, horizon=6, side=1).iloc[0]
    short = labels.triple_barrier(frame, funding, [30], k=2.0, horizon=6, side=-1).iloc[0]
    assert long_["kind"] == "stop" and long_["start"] == 31
    assert long_["net"] == pytest.approx(long_["gross"] - labels.ROUND_TRIP - 0.001)
    assert short["kind"] == "target" and short["funding"] == pytest.approx(0.001)
    assert short["net"] == pytest.approx(short["gross"] - labels.ROUND_TRIP + 0.001)


def test_market_neutral_labels_sum_to_zero_and_do_not_overlap(small_panel):
    frames, fundings = small_panel
    panel = labels.market_neutral_labels({s: f["4h"] for s, f in frames.items()}, fundings, horizon=6)
    assert panel.groupby("time")["rel_ret"].sum().abs().max() < 1e-12
    one = panel[panel["symbol"] == "C1USDT"]
    assert (pd.DatetimeIndex(one["fill_time"].iloc[1:]) >= pd.DatetimeIndex(one["exit_time"].iloc[:-1])).all()


def test_uniqueness_halves_for_two_full_overlaps():
    u = labels.uniqueness([0, 0, 5], [3, 3, 6], 10)
    assert u == pytest.approx([0.5, 0.5, 1.0])


# ------------------------------------------------------------------ features and leak checks
def test_feature_build_passes_all_three_leak_checks(small_panel):
    frames, fundings = small_panel
    inputs = _inputs(frames, fundings)
    times = list(frames["C1USDT"]["4h"].index[[400, 1001, 1777, 2501]])
    assert features.truncation_check(features.build, inputs, times) == []
    assert features.future_shuffle_check(features.build, inputs, times[:2]) == []
    assert all(v == 0 for v in features.warmup_check(features.build, inputs, offsets_days=(0, 60), warmup_days=365).values())


def test_leak_checks_catch_open_time_join_and_future_shift(small_panel):
    frames, fundings = small_panel
    inputs = _inputs(frames, fundings)
    times = list(frames["C1USDT"]["4h"].index[[700, 1500]])

    def open_time_join(inp):  # the classic leak: the 1d bar joined by its open time
        base = inp["bars"]["4h"]
        daily = features.bar_features(inp["bars"]["1d"], "1d_")
        return daily.reindex(base.index, method="ffill")

    def peeks(inp):
        return features.bar_features(inp["bars"]["4h"], "4h_").shift(-1)

    assert features.truncation_check(open_time_join, inputs, times) == times
    assert features.future_shuffle_check(peeks, inputs, times) == times


def test_warmup_check_flags_a_feature_that_never_forgets_its_start(small_panel):
    frames, fundings = small_panel
    inputs = _inputs(frames, fundings)

    def expanding(inp):
        return inp["bars"]["4h"][["close"]].expanding().mean()

    assert features.warmup_check(expanding, inputs, offsets_days=(60,), warmup_days=100)[60] > 0


# ------------------------------------------------------------------ splits
def test_walk_forward_purges_labels_that_reach_the_test_block():
    t = pd.date_range("2022-01-01", periods=800, freq="D", tz="UTC")
    t1 = t + pd.Timedelta(days=5)
    for train, test, start, _ in splits.purged_walk_forward(t, t1, "2022-06-01", "2023-12-31", 365, 30):
        assert (t1[train] < start - pd.Timedelta(days=1)).all() and (t[test] >= start).all()
        assert t[train].min() >= start - pd.Timedelta(days=365)
    fit, cal = splits.inner_split(t, t1, np.arange(400))
    assert t1[fit].max() < t[cal].min()


def test_cpcv_counts_purge_and_paths():
    t = pd.date_range("2021-01-01", periods=1200, freq="D", tz="UTC")
    t1 = t + pd.Timedelta(days=3)
    out, groups = splits.cpcv(t, t1, n_groups=12, k_test=2)
    assert len(out) == 66
    for train, ids in out:
        assert not np.isin(groups[train], ids).any()
    paths = splits.cpcv_paths(12, 2)
    assert len(paths) == 11 and all(sorted(g for _, g in p) == list(range(12)) for p in paths.values())


# ------------------------------------------------------------------ statistics
def test_deflated_sharpe_falls_with_more_trials():
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.01, 1000)
    trials = rng.normal(0, 1 / np.sqrt(1000), 20)
    assert stats.deflated_sharpe(r, trials, n_trials=300) < stats.deflated_sharpe(r, trials, n_trials=5)


def test_pbo_is_high_for_noise_and_low_for_a_dominant_config():
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 0.01, (800, 8))
    assert stats.pbo_cscv(noise, n_blocks=8)["pbo"] > 0.3
    good = noise.copy()
    good[:, 0] += 0.004
    assert stats.pbo_cscv(good, n_blocks=8)["pbo"] < 0.1


def test_block_permutation_keeps_each_symbols_labels():
    t = pd.date_range("2022-01-01", periods=400, freq="D", tz="UTC")
    g = np.repeat(["A", "B"], 200)
    y = np.r_[np.ones(150), np.zeros(50), np.zeros(200)].astype(int)
    out = stats.block_permute(y, np.r_[t[:200], t[:200]], g, rng=np.random.default_rng(3))
    assert out[g == "B"].sum() == 0 and abs(out[g == "A"].mean() - 0.75) < 0.1


def test_bootstrap_and_newey_west():
    x = np.random.default_rng(2).normal(0.3, 1, 500)
    draws = stats.bootstrap(np.mean, x, mean_block=10, reps=300)
    assert len(draws) == 300 and abs(draws.mean() - x.mean()) < 0.05
    assert stats.newey_west_t(x) > 1.5
    assert stats.permutation_p_value(3.0, [0.0] * 199) == pytest.approx(1 / 200)


# ------------------------------------------------------------------ models
def test_blend_and_dissimilarity_abstain():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(1200, 4))
    y = (x[:, 0] + rng.normal(0, 1, 1200) > 0).astype(int)
    x_test = np.vstack([x[:50], np.full((5, 4), 40.0)])
    p, score, abstain = models.fit_predict(models.ModelSpec("blend", use_di=True), x[:800], y[:800], np.ones(800),
                                           x[800:], y[800:], x_test)
    assert abstain[-5:].all() and not abstain[:50].all()
    assert ((p >= 0) & (p <= 1)).all() and len(score) == 55


# ------------------------------------------------------------------ gate D end to end
def test_gate_d_rejects_no_edge_and_passes_a_planted_edge():
    results = {}
    for edge in (0.0, 0.0006):
        data, cols = _pipeline(edge)
        specs = {"logistic": models.ModelSpec("logistic"), "logistic_di": models.ModelSpec("logistic", use_di=True)}
        books, chosen = {}, None
        for name, spec in specs.items():
            preds, book, pnl, ic = _evaluate(data, cols, spec)
            books[name] = walkforward.daily(book)
            if chosen is None:
                chosen = (books[name], pnl, book, ic)
        daily, pnl, book, ic = chosen
        matrix = pd.DataFrame(books).fillna(0.0)
        cost2x = walkforward.daily(book - labels.ROUND_TRIP)
        results[edge] = gates.gate_d(daily, cost2x, matrix, null_sharpes=[], monthly_ic=ic, profit_by_symbol=pnl,
                                     trade_pnls=book.to_numpy(), boot_reps=200)
    none, edge = results[0.0], results[0.0006]
    assert none["verdict"] == gates.FAIL
    # PBO only measures selection among near-identical configurations, so it is not an edge test;
    # the no-edge panel is rejected by return, deflated Sharpe and IC.
    assert none["D1_return"] == none["D3_dsr"] == none["D8_ic"] == gates.FAIL
    assert edge["D1_return"] == edge["D3_dsr"] == edge["D4_pbo"] == edge["D7_stability"] == edge["D8_ic"] == gates.PASS
    # No C1 baseline, no simple model and no 200-run permutation here: those checks block the verdict.
    assert edge["D2_vs_C1"] == edge["D5_permutation"] == edge["D6_vs_simple"] == gates.NOT_EVALUATED
    assert edge["verdict"] == gates.FAIL


def test_gate_d_permutation_and_trial_budget_rules():
    rng = np.random.default_rng(5)
    idx = pd.date_range("2023-01-01", periods=730, freq="D", tz="UTC")
    daily = pd.Series(rng.normal(0.002, 0.01, 730), index=idx)
    matrix = pd.DataFrame({f"k{i}": rng.normal(0, 0.01, 730) for i in range(25)}, index=idx)
    out = gates.gate_d(daily, daily - 0.0005, matrix, null_sharpes=rng.normal(0, 0.04, 200),
                       monthly_ic=np.full(24, 0.05), profit_by_symbol={"A": 1, "B": 1, "C": 1, "D": 1},
                       trade_pnls=np.ones(100), boot_reps=100)
    assert out["D3_dsr"] == gates.FAIL  # 25 configurations broke the K = 24 budget
    assert out["D5_permutation"] == gates.PASS


def test_permutation_null_sits_below_a_planted_edge():
    data, cols = _pipeline(0.0006, days=700)
    spec = models.ModelSpec("logistic")
    preds = walkforward.run(data, cols, spec, "2022-03-01", "2022-12-31", train_days=365)
    observed = stats.sharpe(walkforward.daily(walkforward.long_short_book(preds)[0]))
    null = walkforward.permutation_null(data, cols, spec, "2022-03-01", "2022-12-31", reps=5, train_days=365)
    assert observed > null.max()
