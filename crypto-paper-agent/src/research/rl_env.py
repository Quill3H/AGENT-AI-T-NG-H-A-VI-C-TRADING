"""Optional RL research environment. PPO is deliberately optional and paper-only."""
from dataclasses import dataclass
from typing import Any, Dict, Tuple
import numpy as np

@dataclass
class RiskAwareTradingEnv:
    prices: np.ndarray
    initial_equity: float = 10_000.0
    max_risk_fraction: float = 0.02
    def reset(self) -> Tuple[np.ndarray, Dict[str, Any]]:
        self.i=0; self.equity=float(self.initial_equity); self.peak=self.equity; self.position=0; self.violations=0
        return np.array([self.prices[0], self.equity, 0.0], dtype=float), {}
    def step(self, action: int):
        if action not in (-1,0,1): raise ValueError("action must be -1, 0, or 1")
        if self.i >= len(self.prices)-1: return self._obs(), 0.0, True, False, {"risk_violation":0}
        old=self.equity; self.position=action; self.i += 1
        self.equity += self.position * float(self.prices[self.i]-self.prices[self.i-1])
        self.peak=max(self.peak,self.equity); dd=max(0.0,(self.peak-self.equity)/self.peak)
        violation=int(abs(self.position)*(abs(self.prices[self.i]-self.prices[self.i-1])/self.prices[self.i-1]) > self.max_risk_fraction)
        self.violations += violation
        reward=(self.equity-old) - 0.5*dd - 1.0*violation
        return self._obs(), reward, self.i >= len(self.prices)-1, False, {"risk_violation":violation,"drawdown":dd}
    def _obs(self): return np.array([self.prices[self.i], self.equity, float(self.position)], dtype=float)

def train_ppo(*args, **kwargs):
    try:
        from stable_baselines3 import PPO
    except ImportError as exc:
        raise RuntimeError("BLOCKED/NOT_VERIFIED: stable-baselines3 is not installed") from exc
    raise RuntimeError("PPO adapter requires an explicit Gymnasium wrapper and review before use")
