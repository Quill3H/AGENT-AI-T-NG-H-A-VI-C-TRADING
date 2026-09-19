"""Independent Review 06 probes for requirements missed by Review 05 fixes."""
import copy
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.execution.paper_broker import PaperBroker
from src.execution.order_models import OrderRequest, OrderDirection, OrderStatus, ExitReason

T = datetime(2026, 9, 1, 7, 59, tzinfo=timezone.utc)

def cfg():
    c = yaml.safe_load((ROOT/'config/default_config.yaml').read_text(encoding='utf-8'))
    c['fees']['slippage_pct'] = 0.
    c['fees']['taker_pct'] = 0.
    c['leverage_brackets']['ETHUSDT'] = copy.deepcopy(c['leverage_brackets']['BTCUSDT'])
    return c

def candle(t, symbol='BTCUSDT', p=100., **kw):
    d=dict(open_time=t,symbol=symbol,open=p,high=p,low=p,close=p,timeframe='1m')
    if 'funding_rate' in kw:
        d['funding_time'] = t
        d['funding_readiness'] = True
    d.update(kw);return d

def req(t=T, symbol='BTCUSDT', qty=10., **kw):
    d=dict(symbol=symbol,direction=OrderDirection.LONG,signal_price=100.,stop_loss_price=98.,
           take_profit_price=None,signal_time=t,leverage=2.,base_risk_percent=.002,
           conviction_tier='low',requested_quantity=qty);d.update(kw);return OrderRequest(**d)

def open_one(c=None, **kw):
    b=PaperBroker(config=c or cfg());b.process_candle(candle(T-timedelta(minutes=1)))
    r=b.submit_order(req(**kw));b.process_candle(candle(T));assert r.status==OrderStatus.FILLED;return b

def state(b):
    fields={k:v for k,v in b.__dict__.items() if k not in ('news_filter','circuit_breaker')}
    fields['breaker']=b.circuit_breaker.__dict__;fields['news']=b.news_filter.__dict__
    return copy.deepcopy(fields)

def test_H1_entry_fee_hits_daily_guard_at_entry_without_counting_a_trade():
    c=cfg();c['fees']['taker_pct']=.06
    b=open_one(c=c, qty=100., base_risk_percent=.02, conviction_tier='normal')
    assert b.circuit_breaker.is_locked
    assert not b.positions
    assert b.circuit_breaker.consecutive_losses==0

def test_H1_funding_is_not_double_counted_when_trade_later_closes():
    b=open_one()
    b.process_candle(candle(T+timedelta(minutes=1),funding_rate=.01))
    assert b.circuit_breaker.rolling_24h_pnl==pytest.approx(-10.)
    b.close_all_positions(100.,T+timedelta(minutes=2),ExitReason.MANUAL)
    assert b.circuit_breaker.rolling_24h_pnl==pytest.approx(-10.)

def test_H1_closed_trade_records_gross_price_pnl_and_exit_fee_as_cashflows():
    c=cfg();c['fees']['taker_pct']=.001
    b=open_one(c=c)
    # Entry fee -1.0 must already be in rolling ledger.
    assert b.circuit_breaker.rolling_24h_pnl==pytest.approx(-1.)
    b.close_all_positions(104.,T+timedelta(minutes=1),ExitReason.MANUAL)
    # +40 gross -1 entry -1.04 exit = +37.96 cashflow, exactly once.
    assert b.circuit_breaker.rolling_24h_pnl==pytest.approx(37.96)

def test_H2_collateral_solver_uses_tier_at_liquidation_not_entry():
    c=cfg();c['account']['initial_equity_usd']=100000.
    b=PaperBroker(config=c)
    b.process_candle(candle(T-timedelta(minutes=1)))
    r=b.submit_order(req(qty=600.,base_risk_percent=.02,conviction_tier='normal'))
    b.process_candle(candle(T));assert r.status==OrderStatus.FILLED
    b.process_candle(candle(T+timedelta(minutes=1),funding_rate=.001))
    p=b.positions['BTCUSDT']
    # Root is in tier 1 (q*P < 50k): mmr .004, cum 0.
    expected=(p.quantity*p.entry_price-p.isolated_collateral)/(p.quantity*(1-.004))
    assert p.quantity*expected < 50000.
    assert p.liquidation_price==pytest.approx(expected)

def test_H2_invalid_brackets_never_fall_back_to_hardcoded_tier():
    b=open_one()
    b.config['leverage_brackets']={'BTCUSDT':'corrupt'}
    p=b.positions['BTCUSDT'];saved=state(b)
    with pytest.raises((ValueError,TypeError)):
        b._calculate_collateral_aware_liquidation_price(p)
    assert state(b)==saved

def test_H3_two_symbols_can_advance_at_the_same_market_timestamp():
    b=PaperBroker(config=cfg())
    b.process_candle(candle(T-timedelta(minutes=1),symbol='BTCUSDT'))
    # A second symbol at the same event time must not be called a duplicate BTC candle.
    b.process_candle(candle(T-timedelta(minutes=1),symbol='ETHUSDT'))

def test_H3_all_open_symbols_are_funded_once_at_same_settlement():
    b=PaperBroker(config=cfg())
    # Seed two prior candles and queue both entries for the same next-open boundary.
    b.process_candle(candle(T-timedelta(minutes=1),symbol='BTCUSDT'))
    b.process_candle(candle(T-timedelta(minutes=1),symbol='ETHUSDT'))
    rb=b.submit_order(req(symbol='BTCUSDT'));re=b.submit_order(req(symbol='ETHUSDT'))
    b.process_candle(candle(T,symbol='BTCUSDT'));b.process_candle(candle(T,symbol='ETHUSDT'))
    assert rb.status==re.status==OrderStatus.FILLED
    b.process_candle(candle(T+timedelta(minutes=1),symbol='BTCUSDT',funding_rate=.001))
    b.process_candle(candle(T+timedelta(minutes=1),symbol='ETHUSDT',funding_rate=.002))
    assert len(b.funding_history)==2

def test_H4_close_all_time_reversal_is_transactional():
    b=open_one();saved=state(b)
    with pytest.raises(ValueError):
        b.close_all_positions(100.,T-timedelta(minutes=1),ExitReason.MANUAL)
    assert state(b)==saved

def test_H4_malformed_funding_config_is_rejected():
    c=cfg();c['funding_rate']='bad'
    with pytest.raises((ValueError,TypeError)):
        PaperBroker(config=c)

def test_H4_mutated_pending_request_is_cleanly_rejected():
    b=PaperBroker(config=cfg());b.process_candle(candle(T-timedelta(minutes=1)))
    q=req();r=b.submit_order(q);q.direction='CORRUPT'
    b.process_candle(candle(T))
    assert r.status==OrderStatus.REJECTED
    assert not b.positions

def test_H5_finalize_prevents_future_entries():
    b=open_one()
    assert hasattr(b,'finalize')
    b.finalize(timestamp=T+timedelta(minutes=1),force_close=False)
    r=b.submit_order(req(t=T+timedelta(minutes=2),symbol='ETHUSDT'))
    assert r.status==OrderStatus.REJECTED
