"""Independent acceptance probes; run explicitly, outside production testpaths."""
import copy
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.execution.paper_broker import PaperBroker
from src.execution.order_models import OrderRequest, OrderDirection, OrderType, OrderStatus, ExitReason
from src.risk.circuit_breakers import CircuitBreakerState

T = datetime(2026, 9, 1, 7, 59, tzinfo=timezone.utc)

def config():
    c = yaml.safe_load((ROOT / 'config/default_config.yaml').read_text(encoding='utf-8'))
    c['fees']['slippage_pct'] = 0.0
    c['leverage_brackets']['ETHUSDT'] = copy.deepcopy(c['leverage_brackets']['BTCUSDT'])
    return c

def candle(t, symbol='BTCUSDT', o=100., h=None, l=None, c=None, **extra):
    d = dict(open_time=t, symbol=symbol, open=o, high=o if h is None else h,
             low=o if l is None else l, close=o if c is None else c, timeframe='1m')
    d.update(extra)
    return d

def request(t=T, **extra):
    d = dict(symbol='BTCUSDT', direction=OrderDirection.LONG, signal_price=100.,
             stop_loss_price=98., take_profit_price=104., signal_time=t,
             leverage=2., base_risk_percent=.002, conviction_tier='low', requested_quantity=10.)
    d.update(extra)
    return OrderRequest(**d)

def opened(t=T, c=None, **req_args):
    b = PaperBroker(config=c or config())
    symbol = req_args.get('symbol', 'BTCUSDT')
    b.process_candle(candle(t-timedelta(minutes=1), symbol=symbol))
    r = b.submit_order(request(t=t, **req_args))
    b.process_candle(candle(t, symbol=symbol))
    assert r.status == OrderStatus.FILLED
    return b

def state(b):
    fields = {k:v for k,v in b.__dict__.items() if k not in ('news_filter','circuit_breaker')}
    fields['breaker_state'] = b.circuit_breaker.__dict__
    fields['news_state'] = b.news_filter.__dict__
    return copy.deepcopy(fields)

def test_control_flat_oracle_without_funding():
    b = opened()
    b.process_candle(candle(T+timedelta(minutes=1), h=104., funding_rate=0.))
    assert b.wallet_balance == pytest.approx(10038.98)

def test_control_stop_tightening_refuses_widening():
    b = opened()
    assert b.update_stop_loss('BTCUSDT', 97.) is False

@pytest.mark.parametrize('rate', [None, float('nan')])
def test_E1_missing_or_nonfinite_funding_fails_before_state_mutation(rate):
    b = opened()
    saved = state(b)
    with pytest.raises((ValueError, TypeError)):
        b.process_candle(candle(T+timedelta(minutes=1), funding_rate=rate))
    assert state(b) == saved

def test_E1_configured_settlement_hours_are_used():
    c = config(); c['funding_rate']['settlement_hours_utc'] = [9]
    b = opened(c=c)
    b.process_candle(candle(T+timedelta(minutes=1), funding_rate=.0001))
    assert not b.funding_history

def test_E1_gap_skipping_settlement_is_rejected():
    b = opened()
    saved = state(b)
    with pytest.raises(ValueError):
        b.process_candle(candle(T+timedelta(minutes=2)))
    assert state(b) == saved

def test_E2_liquidation_tracks_actual_funded_collateral():
    b = opened()
    b.process_candle(candle(T+timedelta(minutes=1), funding_rate=.01))
    p = b.positions['BTCUSDT']
    assert p.isolated_collateral == pytest.approx(490.)
    # First tier mmr .004, cumulative maintenance 0; independent margin equation.
    expected = (p.quantity*p.entry_price-p.isolated_collateral)/(p.quantity*(1-.004))
    assert p.liquidation_price == pytest.approx(expected)

def test_E3_funding_updates_rolling_cashflow_immediately_without_trade_streak():
    b = opened(requested_quantity=100., base_risk_percent=.02, conviction_tier='normal')
    b.process_candle(candle(T+timedelta(minutes=1), funding_rate=.06))
    assert b.circuit_breaker.is_locked, '600 USD funding loss must trigger the 5% guard before trade close'
    assert not b.positions

def test_E3_lock_closes_all_other_active_positions():
    t = T + timedelta(hours=3)
    b = opened(t=t, symbol='ETHUSDT', stop_loss_price=90., take_profit_price=None,
               requested_quantity=50., base_risk_percent=.05, conviction_tier='high')
    r = b.submit_order(request(t=t+timedelta(minutes=1), stop_loss_price=90.,
           take_profit_price=None, requested_quantity=49., base_risk_percent=.05, conviction_tier='high'))
    b.process_candle(candle(t+timedelta(minutes=1)))
    assert r.status == OrderStatus.FILLED
    b.process_candle(candle(t+timedelta(minutes=2), l=90., c=90.))
    assert b.circuit_breaker.is_locked
    assert not b.positions, 'ETH must be closed when BTC realized loss locks the account'

def test_E4_breaker_receives_post_close_equity_without_closed_unrealized():
    class Spy(CircuitBreakerState):
        def record_trade_result(self, pnl, timestamp, equity):
            self.received_equity = equity
            return super().record_trade_result(pnl, timestamp, equity)
    spy = Spy()
    b = PaperBroker(config=config(), circuit_breaker=spy)
    b.process_candle(candle(T-timedelta(minutes=1)))
    b.submit_order(request(requested_quantity=100., base_risk_percent=.02, conviction_tier='normal'))
    b.process_candle(candle(T, h=101., c=101.))
    b.process_candle(candle(T+timedelta(minutes=1), l=98., c=98., funding_rate=0.))
    assert spy.received_equity == pytest.approx(b.wallet_balance)

def test_E5_gap_fill_equal_stop_is_clean_order_rejection():
    b = PaperBroker(config=config())
    b.process_candle(candle(T-timedelta(minutes=1)))
    r = b.submit_order(request())
    b.process_candle(candle(T, o=98.))
    assert r.status == OrderStatus.REJECTED
    assert not b.positions
    assert b.wallet_balance == 10000.

def test_E5_take_profit_revalidated_against_actual_fill():
    b = PaperBroker(config=config())
    b.process_candle(candle(T-timedelta(minutes=1)))
    r = b.submit_order(request(requested_quantity=1.))
    b.process_candle(candle(T, o=105.))
    assert r.status == OrderStatus.REJECTED
    assert not b.trade_history

def test_E5_unsupported_entry_type_is_rejected():
    b = PaperBroker(config=config())
    b.process_candle(candle(T-timedelta(minutes=1)))
    try:
        r = b.submit_order(request(order_type=OrderType.STOP_MARKET))
    except (ValueError, TypeError):
        return
    b.process_candle(candle(T))
    assert r.status == OrderStatus.REJECTED
    assert not b.positions

def test_E5_explicit_declared_risk_not_silently_ignored():
    b = PaperBroker(config=config())
    b.process_candle(candle(T-timedelta(minutes=1)))
    r = b.submit_order(request(risk_percent=.0001))
    b.process_candle(candle(T))
    assert r.status == OrderStatus.REJECTED

def test_E6_invalid_close_time_has_no_financial_mutation():
    b = PaperBroker(config=config())
    b.submit_order(request())
    saved = state(b)
    with pytest.raises(ValueError):
        b.process_candle(candle(T, close_time=T-timedelta(seconds=1)))
    assert state(b) == saved

@pytest.mark.parametrize('tf', ['0m', '-1m', 'nonsense'])
def test_E6_invalid_duration_rejected_without_mutation(tf):
    b = PaperBroker(config=config()); b.submit_order(request())
    saved = state(b)
    with pytest.raises((ValueError, TypeError)):
        b.process_candle(candle(T, timeframe=tf))
    assert state(b) == saved

def test_E7_force_close_applies_exit_slippage():
    c = config(); c['fees']['slippage_pct'] = .0003
    b = opened(c=c, requested_quantity=1.)
    trades = b.close_all_positions(100., T+timedelta(minutes=1), ExitReason.FORCE_CLOSE_END_OF_DATA)
    assert trades[0].exit_price == pytest.approx(99.97)

def test_E7_stop_update_cannot_cross_current_mark():
    b = opened()
    assert b.update_stop_loss('BTCUSDT', 110.) is False
    assert b.positions['BTCUSDT'].stop_loss_price == 98.

def test_E7_gap_take_profit_exits_at_open_phase_before_funding():
    b = opened()
    b.process_candle(candle(T+timedelta(minutes=1), o=105., funding_rate=.0001))
    assert b.trade_history[0].exit_time == T+timedelta(minutes=1)
    assert not b.funding_history

@pytest.mark.parametrize('section,key,value', [
    ('fees','slippage_pct',float('nan')),
    ('fees','slippage_pct',-.01),
    ('fees','slippage_pct',1.1),
    ('account','initial_equity_usd',float('nan')),
    ('account','initial_equity_usd',-100.),
])
def test_E8_invalid_engine_configuration_is_rejected(section,key,value):
    c=config(); c[section][key]=value
    with pytest.raises((ValueError, TypeError)):
        PaperBroker(config=c)
