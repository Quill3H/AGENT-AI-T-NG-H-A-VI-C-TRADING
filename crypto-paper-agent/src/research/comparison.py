"""Deterministic strategy comparison and walk-forward split helpers."""
from typing import Any, Dict, Iterable, List
import pandas as pd

def walk_forward_splits(frame: pd.DataFrame, train_bars: int, test_bars: int, step_bars: int | None = None) -> List[Dict[str, Any]]:
    if train_bars <= 0 or test_bars <= 0: raise ValueError("train_bars and test_bars must be positive")
    step = step_bars or test_bars
    if step <= 0: raise ValueError("step_bars must be positive")
    out=[]; start=0
    while start + train_bars + test_bars <= len(frame):
        out.append({"train": frame.iloc[start:start+train_bars].copy(), "test": frame.iloc[start+train_bars:start+train_bars+test_bars].copy(), "train_start": frame.index[start], "test_end": frame.index[start+train_bars+test_bars-1]})
        start += step
    return out

def compare_metrics(results: Dict[str, Dict[str, float]]) -> pd.DataFrame:
    rows=[]
    for name, metrics in results.items():
        row={"strategy":name}; row.update(metrics); rows.append(row)
    return pd.DataFrame(rows).sort_values("net_pnl", ascending=False).reset_index(drop=True) if rows else pd.DataFrame(columns=["strategy","net_pnl"])
