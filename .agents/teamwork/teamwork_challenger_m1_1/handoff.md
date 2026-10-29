# Handoff Report — Adversarial Empirical Challenge of Milestone 1

**Agent ID**: `teamwork_challenger_m1_1`  
**Parent Conversation ID**: `2c3b8d46-0ade-47e9-ba40-a2ceba159ff5`  
**Working Directory**: `d:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\.agents\teamwork\teamwork_challenger_m1_1`  
**Target Codebase**: `crypto-paper-agent`  
**Python Environment**: `D:\v\Scripts\python.exe`  
**Status**: TASK COMPLETE (Hard Handoff)  
**Verdict**: **REQUEST_CHANGES**  
**Date**: 2026-10-29  

---

## 1. Observation

### 1.1 Scope and Test Execution
An adversarial empirical probe suite was designed, implemented, and executed in `tests/test_adversarial_m1.py` using `D:\v\Scripts\python.exe`.

Command executed:
```powershell
cd crypto-paper-agent
D:\v\Scripts\python.exe -m pytest tests/test_adversarial_m1.py -v -s
```

Verbatim Execution Result:
```
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.2.0, pluggy-1.7.0 -- D:\v\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\Attachments\DU AN\AGENT-AI-T-NG-H-A-VI-C-TRADING\crypto-paper-agent
configfile: pytest.ini
plugins: cov-7.1.0
collecting ... collected 25 items

tests/test_adversarial_m1.py::test_adv_future_4h_tampering_zero_impact_on_15m PASSED
tests/test_adversarial_m1.py::test_adv_rejects_future_4h_candle_in_on_candle_close PASSED
tests/test_adversarial_m1.py::test_adv_trailing_stop_never_loosens_under_wild_oscillations PASSED
tests/test_adversarial_m1.py::test_adv_trailing_stop_boolean_type_confusion Boolean type coercion result: pos.stop_loss_price=1.0
PASSED
tests/test_adversarial_m1.py::test_adv_smc_setup_crash_on_inverted_stop_loss Empirically caught crash: For LONG order, stop_loss_price (99.9) must be < signal_price (95.0)
PASSED
tests/test_adversarial_m1.py::test_adv_smc_setup_crash_on_short_inverted_stop_loss Empirically caught SHORT crash: For SHORT order, stop_loss_price (100.1) must be > signal_price (105.0)
PASSED
tests/test_adversarial_m1.py::test_adv_smc_setup_counter_trend_execution_after_regime_flip Empirical observation: Long order issued into regime: TREND_BEAR
PASSED
tests/test_adversarial_m1.py::test_adv_breakout_zombie_setup_blocks_new_setups_on_regime_flip Breakout state after flip: type=SetupType.BREAKOUT, dir=OrderDirection.LONG, age=2
PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[non_monotonic] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[duplicates] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[naive_tz] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[wrong_tz] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[missing_column] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[nan_price] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[inf_price] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[boolean_price] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[zero_price] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[negative_price] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[negative_volume] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[high_less_than_low] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[high_less_than_open] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[low_greater_than_close] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[not_a_dataframe] PASSED
tests/test_adversarial_m1.py::test_adv_universe_loader_fail_closed_on_corruptions[empty_dataframe] PASSED
tests/test_adversarial_m1.py::test_adv_4h_resampling_geometry_invariants PASSED

============================= 25 passed in 0.47s ==============================
```

### 1.2 Direct Code Observations

1. **`src/strategies/synthesized.py` lines 533-556 (`_evaluate_smc_setup`)**:
```python
533:                         if s.direction == OrderDirection.LONG:
534:                             extreme = s.sweep_extreme if s.sweep_extreme is not None else l
535:                             base_ref = ob_low if ob_low is not None and not np.isnan(ob_low) else extreme
536:                             stop = min(extreme, base_ref) * (1.0 - self.smc_buffer_pct)
537:                         else:
538:                             extreme = s.sweep_extreme if s.sweep_extreme is not None else h
539:                             base_ref = ob_high if ob_high is not None and not np.isnan(ob_high) else extreme
540:                             stop = max(extreme, base_ref) * (1.0 + self.smc_buffer_pct)
541: 
542:                         res = {
543:                             "setup_type": SetupType.SMC_SWEEP,
544:                             "direction": s.direction,
545:                             "signal_price": c,
546:                             "stop_loss_price": stop,
```
**Observation**: Unlike `_evaluate_pullback_setup` (line 342: `if stop_loss < c:`) and `_evaluate_breakout_setup` (line 425: `if stop < c:`), `_evaluate_smc_setup` has **NO validation** verifying that `stop < c` (for LONG) or `stop > c` (for SHORT). When price drops below the stop on the FVG candle (`c <= stop`), `_evaluate_smc_setup` emits an invalid stop loss. When `on_candle_close` invokes `OrderRequest` (line 764), `OrderRequest.__post_init__` (`src/execution/order_models.py` line 151) triggers an unhandled:
`ValueError: For LONG order, stop_loss_price (...) must be < signal_price (...)`.

2. **`src/strategies/synthesized.py` lines 522-556 (`_evaluate_smc_setup` Regime Invalidation)**:
`_evaluate_smc_setup` arms only in `CHOP_RANGING` or pro-trend (line 559). However, inside the `WAIT_FVG` execution block (lines 522-556), there is **zero check** against `self.current_regime`. If the 4h macro regime flips to `TREND_BEAR` while an armed LONG SMC setup is waiting for FVG, the setup executes anyway, firing a LONG position directly into a BEAR trend with normal 2% risk.

3. **`src/strategies/synthesized.py` lines 418-477 (`_evaluate_breakout_setup` Zombie Setup)**:
If a breakout setup arms in `TREND_BULL` (line 465) and the regime subsequently flips to `TREND_BEAR`, the retest check `regime == MarketRegime.TREND_BULL` (line 423) fails. The setup is neither executed nor reset. It lingers until `age > bo_max_age` (8 bars). Because `self.setup.setup_type is not None`, the strategy cannot arm any new BEAR breakout setups during that window.

4. **`src/strategies/synthesized.py` line 822 (`update_trailing_stop`)**:
```python
821:             raw_ema = candle_15m.get(f"ema_{self.trailing_ema_period}")
822:             if raw_ema is not None and isinstance(raw_ema, (int, float)) and math.isfinite(float(raw_ema)):
```
`isinstance(True, (int, float))` evaluates to `True` in Python. Passing `ema_20 = True` coerces the stop loss to `$1.0` if `pos.stop_loss_price < 1.0 < mark_price`. Unlike line 595 in `_apply_funding_filter` (`type(raw_fr) is bool`), boolean filtering was omitted here.

5. **`src/data_layer/universe_loader.py` lines 424-481 (`validate_dataset`)**:
Confirmed all 16 adversarial corruptions (non-monotonic timestamps, duplicate timestamps, timezone-naive, wrong timezone, missing columns, NaNs, Infs, booleans, zero price, negative price, negative volume, $H < L$, $H < \max(O,C)$, $L > \min(O,C)$, non-DataFrame, empty DataFrame) fail-closed with `ValueError` or `TypeError`.

6. **`src/data_layer/universe_loader.py` lines 487-504 (`get_causal_4h_for_15m`)**:
Future tampering of 4h data has strictly zero impact on 15m causal alignment. Anti-lookahead boundary is mathematically preserved.

---

## 2. Logic Chain

1. **High Sample Volume Exposes Extreme Intrabar Volatility**:
   - The user requirement specifies a 1-year backtest with $\ge 2,000$ trades across 10 liquid perpetual pairs (350,400 fifteen-minute bars).
   - In crypto perpetual futures, liquidity sweeps frequently occur during massive wick expansions and flash crashes.
   - When an SMC setup arms on a swing low sweep at price $P_0$, and subsequent bars displace downwards or form an inverted FVG where the closing price drops below $P_0$, $stop = P_0 \times (1 - \text{buffer}) > c$.

2. **Unhandled Crash Invalidates Milestone 2 Backtest Execution**:
   - Because `_evaluate_smc_setup` does not check `if stop < c:` before returning the candidate dictionary, `on_candle_close` blindly passes `signal_price=c` and `stop_loss_price=stop` to `OrderRequest`.
   - `OrderRequest.__post_init__` strictly enforces that `stop_loss_price < signal_price` for LONG orders and raises `ValueError`.
   - In an automated 1-year backtest script, this unhandled exception crashes the process, failing Acceptance Criterion R2 ("runs end-to-end without unhandled errors").

3. **Regime Invalidation Leakage Degrades System Alpha**:
   - The core premise of the synthesized strategy is macro regime routing (Bull $\to$ Long pullbacks/breakouts; Bear $\to$ Short pullbacks/breakouts; Chop $\to$ SMC sweeps).
   - Allowing armed setups to fire counter-trend orders after the macro regime has flipped into an opposing trend induces severe adverse selection and drawdown.

---

## 3. Caveats

1. **Backtest Engine Calling Signature in M1 vs M2**:
   - `BacktestEngine.run` in `src/backtest/engine.py` was originally authored for single-timeframe 4h strategies. Milestone 2 will introduce the dedicated multi-timeframe runner `scripts/run_synthesized_backtest.py`. Our probes directly tested the strategy interface `on_candle_close` and `update_trailing_stop`.
2. **Reviewer Invariance**:
   - Reviewer 1 and the Forensic Auditor evaluated the happy-path unit test suites (`tests/test_synthesized_strategy.py`, `tests/test_universe_loader.py`), which did not include flash-crash FVG price action or regime flip race conditions. Those test suites passed 100% because the mocked data did not challenge extreme boundary conditions.

---

## 4. Conclusion

### Overall Risk Assessment: **HIGH**
### Final Verdict: **REQUEST_CHANGES**

Milestone 1 cannot be approved in its current state due to a critical defect in `src/strategies/synthesized.py` (`_evaluate_smc_setup`) that produces invalid order requests and raises unhandled `ValueError` crashes under flash-crash conditions, along with regime invalidation leakage.

### Required Remediations (for Worker):

1. **Fix Inverted Stop Loss Crash in `src/strategies/synthesized.py` (`_evaluate_smc_setup`)**:
   Add directional stop-loss price guards before emitting the candidate dictionary:
   ```python
   # For LONG:
   if stop >= c or stop <= 0.0:
       self.setup.reset()
       return None

   # For SHORT:
   if stop <= c or c <= 0.0:
       self.setup.reset()
       return None
   ```
2. **Add Regime Invalidation Check in `_evaluate_smc_setup`**:
   Before triggering FVG entry, verify current macro regime compatibility:
   - For LONG: verify `regime in (MarketRegime.CHOP_RANGING, MarketRegime.TREND_BULL)`. If regime flipped to `TREND_BEAR`, reset setup and return `None`.
   - For SHORT: verify `regime in (MarketRegime.CHOP_RANGING, MarketRegime.TREND_BEAR)`. If regime flipped to `TREND_BULL`, reset setup and return `None`.
3. **Prevent Zombie Breakout Starvation in `_evaluate_breakout_setup`**:
   If an armed breakout setup experiences a macro regime flip to the opposing trend (`direction == LONG and regime == TREND_BEAR` or `direction == SHORT and regime == TREND_BULL`), immediately call `self.setup.reset()`.
4. **Harden Boolean Type Guard in `update_trailing_stop`**:
   Add `type(raw_ema) is not bool` to line 822 of `src/strategies/synthesized.py`.

---

## 5. Verification Method

To independently verify the adversarial findings and empirical proof:

```powershell
cd crypto-paper-agent
# Run the adversarial stress test suite
D:\v\Scripts\python.exe -m pytest tests/test_adversarial_m1.py -v -s
```

Observe:
- `test_adv_smc_setup_crash_on_inverted_stop_loss`: Reproduces the unhandled crash `ValueError: For LONG order, stop_loss_price (99.9) must be < signal_price (95.0)`.
- `test_adv_smc_setup_crash_on_short_inverted_stop_loss`: Reproduces `ValueError: For SHORT order, stop_loss_price (100.1) must be > signal_price (105.0)`.
- `test_adv_smc_setup_counter_trend_execution_after_regime_flip`: Demonstrates LONG order emitted with metadata `regime: TREND_BEAR`.
- `test_adv_trailing_stop_boolean_type_confusion`: Demonstrates boolean `True` updating stop loss to `$1.0`.

Invalidation condition: When the worker applies the 4 required remediations, all 25 tests in `test_adversarial_m1.py` and all 56 tests in the baseline test suites will pass with zero crashes and zero invalid orders.
