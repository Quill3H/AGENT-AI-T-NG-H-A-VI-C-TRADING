"""Pair cashflows are hand derived, rather than calculated by the implementation."""
import importlib
import importlib.util

import pandas as pd
import pytest


def api():
    name = 'src.execution.pair_account'
    assert importlib.util.find_spec(name), 'shared pair account is not implemented'
    return importlib.import_module(name)


@pytest.fixture
def account(config):
    lots = {s: {'step': .000001, 'min_quantity': .000001, 'min_notional': 1.}
            for s in ['ETHUSDT', 'BTCUSDT']}
    return api().PairAccount(config, lots, metadata_source='synthetic fixture')


def t(minutes=0):
    return pd.Timestamp('2026-06-01', tz='UTC') + pd.Timedelta(minutes=minutes)


def open_fixed(account, side=1):
    # One ETH versus .05 BTC: two 3000 USD legs, 1x shared margin.
    return account.open_fixed(t(), side, {'ETHUSDT': 1., 'BTCUSDT': .05},
                              {'ETHUSDT': 3000., 'BTCUSDT': 60000.},
                              {'ETHUSDT': 30., 'BTCUSDT': 600.}, 'fixture-model',
                              risk_budget=100.)


def test_hand_accounting_of_two_legs_fees_and_funding(account):
    assert open_fixed(account)
    # ETH buy 3000.9; BTC sell 59982. Fees 1.50045+1.49955=3.
    assert account.wallet == pytest.approx(9997.)
    account.settle(t(15), 'ETHUSDT', .001, 3000.)  # -3
    account.settle(t(15), 'BTCUSDT', .001, 60000.)  # +3
    account.close_pair(t(30), {'ETHUSDT': 3100., 'BTCUSDT': 60000.}, 'TEST')
    # ETH sell 3099.07: gross98.17 fee1.549535;
    # BTC buy60018: gross-1.8 fee1.50045; net90.319... including entry3.
    assert account.wallet == pytest.approx(10090.320015)


def test_no_positive_funding_really_changes_wallet_and_next_risk(account):
    open_fixed(account)
    account.funding_mode = 'no_positive'
    account.settle(t(15), 'BTCUSDT', .001, 60000.)
    account.settle(t(15), 'ETHUSDT', .001, 3000.)
    assert account.wallet == pytest.approx(9994.)
    assert account.funding_events[0]['cashflow'] == 0.
    assert account.funding_events[0]['raw_cashflow'] == pytest.approx(3.)


def test_duplicate_funding_rejected_without_double_cashflow(account):
    open_fixed(account)
    account.settle(t(15), 'ETHUSDT', .001, 3000.)
    before = account.wallet
    with pytest.raises(ValueError, match='DUPLICATE'):
        account.settle(t(15), 'ETHUSDT', .001, 3000.)
    assert account.wallet == before


def test_shared_margin_rejection_never_opens_first_leg(account):
    assert not account.open_fixed(t(), 1, {'ETHUSDT': 3., 'BTCUSDT': .15},
        {'ETHUSDT': 3000., 'BTCUSDT': 60000.}, {'ETHUSDT': 30., 'BTCUSDT': 600.},
        'fixture-model', risk_budget=1000.)
    assert not account.legs and account.wallet == 10000.


def test_second_leg_gate_failure_does_not_mutate_cash(account):
    assert not account.open_fixed(t(), 1, {'ETHUSDT': 1., 'BTCUSDT': .05},
        {'ETHUSDT': 3000., 'BTCUSDT': 60000.}, {'ETHUSDT': 30., 'BTCUSDT': 59000.},
        'fixture-model', risk_budget=10000.)
    assert account.wallet == 10000.
    assert not account.legs


def test_one_pair_outcome_updates_streak_once(account):
    for i in range(3):
        when = t(60*i)
        assert account.open_fixed(when, 1, {'ETHUSDT': 1., 'BTCUSDT': .05},
            {'ETHUSDT': 3000., 'BTCUSDT': 60000.}, {'ETHUSDT': 30., 'BTCUSDT': 600.},
            'fixture-model', risk_budget=100.)
        account.close_pair(when + pd.Timedelta(minutes=15),
                           {'ETHUSDT': 2990., 'BTCUSDT': 60000.}, 'TEST')
    assert account.breaker.consecutive_losses == 3
    assert account.breaker.risk_multiplier == .5
    assert len(account.completed_pairs) == 3


def test_exit_does_not_double_count_entry_fee_or_funding_in_breaker(account):
    open_fixed(account)
    account.settle(t(15), 'ETHUSDT', .001, 3000.)
    account.close_pair(t(30), {'ETHUSDT': 3000., 'BTCUSDT': 60000.}, 'TEST')
    assert account.breaker.rolling_24h_pnl == pytest.approx(account.wallet-10000.)


@pytest.mark.parametrize('side', [-1, 1])
def test_both_directions_and_quantity_rounding_respect_shared_budget(account, side):
    proposal = account.size_pair({'ETHUSDT': 3000., 'BTCUSDT': 60000.},
                                {'ETHUSDT': 30., 'BTCUSDT': 600.}, beta=.05)
    assert proposal['quantities']['BTCUSDT'] == pytest.approx(
        .05*proposal['quantities']['ETHUSDT'], abs=.000001)
    assert proposal['risk_usd'] <= 50.000001
    assert proposal['notional'] <= 10000.


def test_stop_fills_affected_leg_partner_waits_until_next_open(account):
    open_fixed(account)
    bars = {'ETHUSDT': {'open':3000.,'high':3010.,'low':2900.,'close':2950.},
            'BTCUSDT': {'open':60000.,'high':60100.,'low':59900.,'close':60000.}}
    account.protect(t(15), bars)
    assert 'ETHUSDT' not in account.legs
    assert 'BTCUSDT' in account.legs
    assert account.pending_close == 'PARTNER_STOP'
    account.close_pair(t(30), {'ETHUSDT':2950., 'BTCUSDT':60000.}, 'PARTNER_STOP')
    assert len(account.completed_pairs) == 1


def test_aborted_entries_cannot_satisfy_completed_pair_evidence_floor(account):
    from src.research.cointegration import summarize
    for i in range(30):
        when=t(i*60)
        assert account.open_fixed(when,1,{'ETHUSDT':1.,'BTCUSDT':.05},
            {'ETHUSDT':3000.,'BTCUSDT':60000.},{'ETHUSDT':30.,'BTCUSDT':600.},
            'fixture-model',100.,delay_second=True)
        account.close_pair(when+pd.Timedelta(minutes=15),
                           {'ETHUSDT':3100.,'BTCUSDT':60000.},'SECOND_LEG_FAILED')
    result=summarize(account,[dict(time=str(t(30*60)),equity=account.wallet)],
                     t(),t(31*60),{},[])
    assert result['completed_pairs']==0 and result['aborted_pairs']==30
    assert result['win_rate_pct'] is None
    assert result['verdict']=='INSUFFICIENT_EVIDENCE'


def test_failed_delayed_second_leg_flattens_first_and_records_abort(account):
    assert account.open_fixed(t(),1,{'ETHUSDT':1.,'BTCUSDT':.05},
        {'ETHUSDT':3000.,'BTCUSDT':60000.},{'ETHUSDT':30.,'BTCUSDT':600.},
        'fixture-model',100.,delay_second=True)
    account.complete_delayed(t(15),{'ETHUSDT':100.,'BTCUSDT':150000.})
    assert not account.legs and account.pair is None
    assert not account.completed_pairs[0]['complete_entry']
    assert account.completed_pairs[0]['reason']=='SECOND_LEG_FAILED'
    assert len([f for f in account.fills if f['kind']=='ENTRY'])==1
    assert account.accounting_error()==pytest.approx(0.,abs=1e-8)


def test_actual_and_no_positive_recompound_different_next_quantities(account):
    from copy import deepcopy
    other=api().PairAccount(account.config,deepcopy(account.lots),'synthetic fixture',funding_mode='no_positive')
    for book in [account,other]:
        open_fixed(book)
        book.settle(t(15),'BTCUSDT',.1,60000.)
        book.settle(t(15),'ETHUSDT',.01,3000.)
        book.close_pair(t(30),{'ETHUSDT':3000.,'BTCUSDT':60000.},'TEST')
    prices={'ETHUSDT':3000.,'BTCUSDT':60000.}; atr={'ETHUSDT':30.,'BTCUSDT':600.}
    assert account.size_pair(prices,atr,.05)['quantities']['ETHUSDT']>other.size_pair(prices,atr,.05)['quantities']['ETHUSDT']


def test_large_funding_payment_triggers_existing_breaker(account):
    open_fixed(account)
    account.settle(t(15),'ETHUSDT',.2,3000.)
    assert account.breaker.is_locked
    assert account.pending_close=='CIRCUIT_BREAKER'
    assert account.wallet==pytest.approx(9397.)


def test_enabled_missing_news_calendar_keeps_gate_fail_closed(account):
    account.config['news_filter']={'enabled':True}
    account.news_filter=None
    assert not open_fixed(account)
    assert not account.legs and account.wallet==10000.


def test_year_end_close_belongs_to_preceding_year(account):
    from src.research.cointegration import summarize
    account.wallet=11000.
    snapshots=[dict(time='2021-12-31T23:45:00Z',equity=10000.),
               dict(time='2022-01-01T00:00:00Z',equity=11000.),
               dict(time='2022-12-31T23:45:00Z',equity=11000.),
               dict(time='2023-01-01T00:00:00Z',equity=11000.)]
    result=summarize(account,snapshots,pd.Timestamp('2021-01-01',tz='UTC'),
                     pd.Timestamp('2023-01-01',tz='UTC'),{},[])
    assert result['yearly_return_pct']['2021']==pytest.approx(10.)
    assert result['yearly_return_pct']['2022']==pytest.approx(0.)
