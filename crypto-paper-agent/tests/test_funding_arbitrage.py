"""Independent two-leg oracle and fail-closed basket regressions."""
from copy import deepcopy
import pandas as pd
import pytest
from src.strategies.funding_arbitrage import FundingArbitrageSimulator


def config():
    return {'fees': {'taker_pct': .0005, 'slippage_pct': 0.0},
            'news_filter': {'enabled': False},
            'funding_arbitrage': {'min_apr': .15, 'funding_period_hours': 8, 'stop_pct': .02}}


def quotes():
    idx = pd.date_range('2024-01-01', periods=5, freq='8h', tz='UTC')
    return pd.DataFrame({'spot_close':[100,100,100.5,101,101],
                         'perp_close':[100,100,100.6,101.1,101.2],
                         'observed_funding_rate':[.0002]*5,'observed_funding_time':idx,
                         'funding_rate':[.0002,.0002,.0002,-.0001,-.0001],
                         'funding_time':idx,'funding_readiness':True},index=idx)


def test_two_leg_hand_oracle_negative_distinct_settlements():
    r = FundingArbitrageSimulator(config()).simulate(quotes(), 10000, 4000)
    # q=40 at second quote; 8000 collateral+spot, 4 entry fees; cash=1996.
    # funding = 40*(100.6*.0002-101.1*.0001-101.2*.0001) = -.0044
    # spot pnl=40, perp pnl=-48; exit fee=40*(101+101.2)*.0005=4.044
    assert r.entered and r.exited
    assert r.entry_time == quotes().index[1]
    assert r.exit_reason == 'NEGATIVE_FUNDING_TWO_CYCLES'
    assert r.quantity == 40
    assert r.funding_cashflow == pytest.approx(-.0044)
    assert r.spot_pnl == 40
    assert r.perp_pnl == pytest.approx(-48)
    assert r.fees_paid == pytest.approx(8.044)
    assert r.cash == pytest.approx(9983.9516)
    assert r.equity == pytest.approx(10000+r.net_pnl)
    assert len([e for e in r.ledger if e['kind']=='FUNDING']) == 3
    assert r.spot_inventory == r.perp_collateral == r.unrealized_pnl == 0


@pytest.mark.parametrize('value', [True, float('nan'), float('inf'), 0, -1])
@pytest.mark.parametrize('field', ['initial_capital','notional_usd'])
def test_invalid_money_rejected(value, field):
    args={'initial_capital':10000,'notional_usd':4000}; args[field]=value
    with pytest.raises((TypeError,ValueError)):
        FundingArbitrageSimulator(config()).simulate(quotes(), **args)


def test_capital_never_double_spent_and_excess_requested_rejected():
    r = FundingArbitrageSimulator(config()).simulate(quotes(), 10000, 10000)
    assert not r.entered and not r.ledger
    assert 'INSUFFICIENT_BASKET_CAPITAL' in r.rejections[0]['reasons']
    r = FundingArbitrageSimulator(config()).simulate(quotes().iloc[:2],10000,force_close=False)
    assert r.cash >= -1e-8
    assert r.spot_notional+r.perp_notional+r.fees_paid <= 10000+1e-8


def test_empty_no_entry_and_open_end_schema():
    f=quotes()
    assert FundingArbitrageSimulator(config()).simulate(f.iloc[:0],10000).equity == 10000
    f['observed_funding_rate']=0.0
    assert not FundingArbitrageSimulator(config()).simulate(f,10000).entered
    f=quotes().iloc[:3]
    r=FundingArbitrageSimulator(config()).simulate(f,10000,4000,force_close=False)
    assert r.entered and not r.exited
    assert r.unrealized_pnl == pytest.approx(-4)
    assert r.realized_pnl == pytest.approx(-4+.8048)
    closed=FundingArbitrageSimulator(config()).simulate(f,10000,4000)
    assert closed.exited and closed.fees_paid > r.fees_paid


@pytest.mark.parametrize('change', ['duplicate','conflicting_duplicate','reversed','naive','missing','future','stale','readiness','schedule'])
def test_time_and_funding_provenance_fail_before_mutation(change):
    f=quotes()
    if change in ('duplicate','conflicting_duplicate'):
        extra=f.iloc[[2]].copy()
        if change=='conflicting_duplicate': extra['funding_rate']=.03
        f=pd.concat([f.iloc[:3],extra,f.iloc[3:]])
    elif change=='reversed': f=f.iloc[::-1]
    elif change=='naive': f.index=f.index.tz_localize(None)
    elif change=='missing': f=f.drop(columns='funding_time')
    elif change=='future': f.loc[f.index[2],'funding_time']=f.index[2]+pd.Timedelta(hours=1)
    elif change=='stale': f.loc[f.index[2],'funding_time']=f.index[2]-pd.Timedelta(hours=25)
    elif change=='readiness': f['funding_readiness']=False
    elif change=='schedule': f=f.drop(f.index[2])
    sim=FundingArbitrageSimulator(config())
    with pytest.raises((ValueError,TypeError)): sim.simulate(f,10000)
    assert sim.cb.current_timestamp is None


@pytest.mark.parametrize('change,reason', [('stop','EMERGENCY_STOP'),('liq','LIQUIDATION'),('funding','CIRCUIT_BREAKER_LOCK')])
def test_forced_paired_unwind(change,reason):
    f=quotes()
    if change=='stop': f.loc[f.index[2],'spot_close']=90
    if change=='liq': f.loc[f.index[2],'perp_close']=250
    if change=='funding': f.loc[f.index[2],'funding_rate']=-.2
    r=FundingArbitrageSimulator(config()).simulate(f,10000,4000)
    assert r.exit_reason==reason
    assert r.spot_inventory==0 and r.perp_collateral==0
    assert r.equity == pytest.approx(10000+r.net_pnl)


@pytest.mark.parametrize('section,key,value', [('fees','taker_pct',True),('fees','slippage_pct',float('nan')),
    ('fees','taker_pct',1),('funding_arbitrage','funding_period_hours',True),('funding_arbitrage','funding_period_hours',7)])
def test_malformed_config(section,key,value):
    cfg=config(); cfg[section][key]=value
    with pytest.raises((ValueError,TypeError)): FundingArbitrageSimulator(cfg)


def test_missing_spot_leg_fails_closed():
    f = quotes().drop(columns='spot_close')
    with pytest.raises(ValueError, match='explicit columns'):
        FundingArbitrageSimulator(config()).simulate(f,10000)
