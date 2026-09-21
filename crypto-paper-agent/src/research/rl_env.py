"""Gymnasium adapter over PaperBroker, with train-only observation scaling.

Reward is dimensionless: realized net trade PnL / initial capital minus 0.5
 times the increase in fractional drawdown minus 1.0 per invalid/rejected action.
Entry fees and funding are included exactly once in each realized trade/slice;
they are not rewarded twice as separate cashflows. Terminal positions are closed.
"""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
import pandas as pd
import gymnasium as gym
from gymnasium import spaces

from src.backtest.engine import BacktestEngine
from src.execution.paper_broker import PaperBroker
from src.execution.order_models import OrderRequest, OrderDirection, OrderStatus
from src.data_layer.cache_manager import timeframe_to_timedelta
from src.research.validation import number, positive_int


def market_vectors(frame):
    previous=frame.close.shift(1).fillna(frame.close.iloc[0])
    arrays=[frame[c].to_numpy(dtype=float)/previous.to_numpy(dtype=float)-1 for c in ('open','high','low','close')]
    arrays.append(np.log1p(frame.volume.to_numpy(dtype=float)))
    masks=[]
    for name in ('oi_delta_pct','funding_rate','cvd'):
        v=frame[name].to_numpy(dtype=float) if name in frame else np.full(len(frame),np.nan)
        mask=np.isfinite(v); arrays.append(np.where(mask,v,0)); masks.append(mask.astype(float))
    return np.column_stack(arrays+masks)


class ObservationScaler:
    def __init__(self,mean,scale):
        self.mean=np.asarray(mean,dtype=float);self.scale=np.asarray(scale,dtype=float)
        if self.mean.shape!=(11,) or self.scale.shape!=(11,) or not np.isfinite(self.mean).all() or not np.isfinite(self.scale).all() or np.any(self.scale<=0):
            raise ValueError('invalid observation scaler')
    @classmethod
    def fit_train(cls,frame):
        BacktestEngine.validate_dataset(frame,'RL train')
        values=market_vectors(frame); sd=values.std(axis=0)
        return cls(values.mean(axis=0),np.where(sd>1e-12,sd,1))
    def to_dict(self): return {'mean':self.mean.tolist(),'scale':self.scale.tolist(),'fit_scope':'train_only'}


class RiskAwareTradingEnv(gym.Env):
    metadata={'render_modes':[]}
    def __init__(self,frame,config,scaler,timeframe='1m'):
        super().__init__()
        BacktestEngine.validate_dataset(frame,'RL')
        if len(frame)<2: raise ValueError('RL episode needs at least two closed candles')
        self.frame=frame.copy(); self.config=deepcopy(config);self.scaler=scaler
        self.timeframe=timeframe; self.duration=timeframe_to_timedelta(timeframe)
        self.symbol=config.get('data',{}).get('futures_symbol','BTCUSDT')
        rl=config.get('rl',{})
        self.stop_pct=number(rl.get('stop_pct',.02),'RL stop_pct',maximum=1,positive=True)
        self.base_risk=number(rl.get('base_risk_percent',.02),'RL base_risk_percent',maximum=1,positive=True)
        self.leverage=number(rl.get('leverage',2.0),'RL leverage',minimum=1)
        self.action_space=spaces.Discrete(4)  # hold, long, short, close
        self.observation_space=spaces.Box(-1e6,1e6,shape=(16,),dtype=np.float32)
        self.vectors=market_vectors(frame)
        self.broker=None; self.done=True

    def _candle(self,i):
        ts=self.frame.index[i];row=self.frame.iloc[i]
        candle={k:float(row[k]) for k in ('open','high','low','close','volume')}
        candle.update(symbol=self.symbol,timeframe=self.timeframe,open_time=ts,close_time=ts+self.duration)
        for name in ('funding_rate','funding_time','funding_readiness'):
            if name in row:
                value=row[name]
                if isinstance(value,np.bool_):value=bool(value)
                candle[name]=value
        return candle

    def reset(self,*,seed=None,options=None):
        super().reset(seed=seed)
        self.i=0;self.done=False;self.broker=PaperBroker(self.config)
        self.initial=self.broker.initial_balance;self.peak=self.initial;self.drawdown=0.0
        self.broker.process_candle(self._candle(0))
        return self._obs(), {'risk_violation':0,'realized_net_pnl':0.0}

    def _obs(self):
        b=self.broker;pos=b.positions.get(self.symbol)
        direction=0 if pos is None else (1 if pos.direction==OrderDirection.LONG else -1)
        market=(self.vectors[self.i]-self.scaler.mean)/self.scaler.scale
        values=np.r_[market,b.equity/self.initial,b.available_margin/self.initial,direction,b.circuit_breaker.risk_multiplier,self.drawdown]
        return np.clip(values,-1e6,1e6).astype(np.float32)

    def step(self,action):
        if self.done: raise RuntimeError('reset required after episode termination')
        b=self.broker; before_realized=sum(t.net_pnl for t in b.trade_history)
        before_rejections=sum(o.status==OrderStatus.REJECTED for o in b.order_history)
        invalid=0
        if not self.action_space.contains(action): invalid=1
        elif int(action) in (1,2):
            direction=OrderDirection.LONG if int(action)==1 else OrderDirection.SHORT
            price=float(self.frame.iloc[self.i].close)
            stop=price*(1-self.stop_pct if direction==OrderDirection.LONG else 1+self.stop_pct)
            b.submit_order(OrderRequest(self.symbol,direction,price,stop,self.frame.index[self.i]+self.duration,
                leverage=self.leverage,base_risk_percent=self.base_risk,conviction_tier='normal',
                metadata={'strategy':'PPO','causal_observation':True}))
        elif int(action)==3:
            if self.symbol not in b.positions: invalid=1
            else: b.request_close(self.symbol,self.frame.index[self.i]+self.duration)
        self.i+=1
        b.process_candle(self._candle(self.i))
        self.done=self.i==len(self.frame)-1 or b.is_halted or b.circuit_breaker.is_halted
        if self.done: b.finalize(self.frame.index[self.i]+self.duration,force_close=True)
        rejected=sum(o.status==OrderStatus.REJECTED for o in b.order_history)-before_rejections
        violation=int(invalid or rejected>0)
        realized=sum(t.net_pnl for t in b.trade_history)-before_realized
        self.peak=max(self.peak,b.equity)
        drawdown=max(0.0,(self.peak-b.equity)/self.peak)
        penalty=max(0.0,drawdown-self.drawdown)
        self.drawdown=drawdown
        reward=realized/self.initial-.5*penalty-1.0*violation
        return self._obs(),float(reward),bool(self.done),False,{'risk_violation':violation,
            'realized_net_pnl':realized,'drawdown_penalty':penalty,'equity':b.equity}


def evaluate_policy(env,policy,seed=42):
    obs,_=env.reset(seed=seed); done=False; reward=0.; violations=0; actions=[]
    while not done:
        action=int(policy(obs,env));actions.append(action)
        obs,r,terminated,truncated,info=env.step(action);done=terminated or truncated
        reward+=r;violations+=info['risk_violation']
    env.broker.verify_accounting_invariants()
    return {'reward':reward,'total_net_pnl':env.broker.equity-env.initial,
            'final_equity':env.broker.equity,'total_trades':len(env.broker.trade_history),
            'risk_violations':violations,'actions':actions}


def train_ppo(train,validation,holdout,config,output_dir,total_timesteps=256,seed=42,timeframe='1m'):
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_checker import check_env
    import torch
    positive_int(total_timesteps,'total_timesteps')
    if not train.index[-1]<validation.index[0] or not validation.index[-1]<holdout.index[0]:
        raise ValueError('train, validation, final holdout must be strictly chronological and disjoint')
    torch.set_num_threads(1)
    scaler=ObservationScaler.fit_train(train)
    env=RiskAwareTradingEnv(train,config,scaler,timeframe)
    check_env(env,warn=True)
    model=PPO('MlpPolicy',env,seed=seed,device='cpu',n_steps=64,batch_size=32,n_epochs=2,verbose=0)
    model.learn(total_timesteps=total_timesteps)
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=True)
    model.save(output/'ppo_model')
    loaded=PPO.load(output/'ppo_model',device='cpu')
    policy=lambda obs,env:int(model.predict(obs,deterministic=True)[0])
    loaded_policy=lambda obs,env:int(loaded.predict(obs,deterministic=True)[0])
    validation_result=evaluate_policy(RiskAwareTradingEnv(validation,config,scaler,timeframe),policy,seed)
    test_env=lambda:RiskAwareTradingEnv(holdout,config,scaler,timeframe)
    result=evaluate_policy(test_env(),policy,seed)
    reloaded=evaluate_policy(test_env(),loaded_policy,seed)
    if result!=reloaded: raise AssertionError('PPO save/load replay mismatch')
    no_trade=evaluate_policy(test_env(),lambda obs,env:0,seed)
    # Fixed causal trend baseline; same broker, stop/risk and costs as PPO.
    def baseline(obs,env):
        closes=env.frame.close.iloc[:env.i+1]
        if len(closes)<20:return 0
        long=closes.iloc[-5:].mean()>closes.iloc[-20:].mean()
        pos=env.broker.positions.get(env.symbol)
        if pos is None:return 1 if long else 2
        if (pos.direction==OrderDirection.LONG)!=long:return 3
        return 0
    rule=evaluate_policy(test_env(),baseline,seed)
    report={'status':'AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED','seed':seed,'requested_timesteps':total_timesteps,
            'actual_timesteps':model.num_timesteps,'device':'cpu','scaler':scaler.to_dict(),
            'validation':validation_result,'final_holdout':result,'no_trade':no_trade,'rule_based_ma_5_20':rule,
            'save_load_equal':True,'reward_units':'realized_USDT/initial_USDT - 0.5*incremental_fractional_DD - violations'}
    from src.research.artifacts import persist_research_run, dataset_manifest
    report['datasets']={k:dataset_manifest(f,'supplied_dataset','BTCUSDT','perpetual',timeframe)
                       for k,f in [('train',train),('validation',validation),('holdout',holdout)]}
    persist_research_run(output,'ppo',config,report)
    return report
