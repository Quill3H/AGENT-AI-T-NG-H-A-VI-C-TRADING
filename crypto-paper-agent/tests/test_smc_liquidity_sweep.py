import pandas as pd
from datetime import datetime, timezone
from src.strategies.smc_liquidity_sweep import SMCLiquiditySweepStrategy

def test_smc_signal_is_causal_and_has_partial_exit_metadata():
    idx = pd.date_range(datetime(2024,1,1,tzinfo=timezone.utc), periods=12, freq="4h")
    close = [100,99,98,99,100,101,100,99,98,99,101,102]
    frame = pd.DataFrame({"open":close,"high":[x+1 for x in close],"low":[x-1 for x in close],"close":close,"volume":[10]*12}, index=idx)
    cfg={"smc":{"swing_n":2,"min_bos_pct":0.0},"take_profit":{"rrr_min":2},"stop_loss":{"buffer_pct":.001}}
    s=SMCLiquiditySweepStrategy(cfg)
    before=s.on_candle_close({"close_time":idx[-1].to_pydatetime()},frame,type("B",(),{"positions":{}})())
    altered=frame.copy(); altered.iloc[-1, altered.columns.get_loc("high")]=1000
    after=s.on_candle_close({"close_time":idx[-1].to_pydatetime()},altered,type("B",(),{"positions":{}})())
    assert before is None or before.metadata["causal_features"] is True
    assert after is None or after.metadata["causal_features"] is True
