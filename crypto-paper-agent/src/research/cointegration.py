"""Causal shared-account replay for the owner-approved fixed ETH/BTC experiment."""
from collections import Counter
from dataclasses import asdict
import hashlib
import math

import numpy as np
import pandas as pd

from src.execution.pair_account import PairAccount
from src.strategies.eth_btc_cointegration import SYMBOLS, crossing, fit_week, model_payload, simple_atr, utc

BAR = pd.Timedelta(minutes=15)
SIGNAL_BAR = pd.Timedelta(hours=4)


def validate_market(frames, funding, start, end):
    expected = pd.date_range(start,end-BAR,freq='15min')
    normalized = {}
    for s in SYMBOLS:
        frame = frames[s]
        if (not isinstance(frame.index,pd.DatetimeIndex) or frame.index.tz is None
                or frame.index.has_duplicates or not frame.index.is_monotonic_increasing):
            raise ValueError(f'DATA_GAP: invalid index {s}')
        observed = frame.loc[(frame.index>=start)&(frame.index<end)]
        if not observed.index.as_unit('ns').equals(expected.as_unit('ns')):
            raise ValueError(f'DATA_GAP: execution {s}')
        values=frame[['open','high','low','close']].to_numpy(dtype=float)
        if (not np.isfinite(values).all() or (values<=0).any()
                or (values[:,1]<np.maximum(values[:,0],values[:,3])).any()
                or (values[:,2]>np.minimum(values[:,0],values[:,3])).any()):
            raise ValueError(f'INVALID_OHLC: {s}')
        source = funding[s].copy()
        if (not isinstance(source.index,pd.DatetimeIndex) or source.index.tz is None
                or source.index.has_duplicates or not source.index.is_monotonic_increasing):
            raise ValueError(f'FUNDING_GAP: invalid index {s}')
        rates=source['funding_rate'].to_numpy(dtype=float)
        if not np.isfinite(rates).all():
            raise ValueError(f'FUNDING_GAP: nonfinite {s}')
        # ADR0013: nominal settlement time is not the event availability time.
        boundary=source.index.floor('h')
        if ((source.index-boundary)>pd.Timedelta(seconds=1)).any() or boundary.has_duplicates:
            raise ValueError(f'FUNDING_GAP: ambiguous event {s}')
        source['funding_source_time']=source.index
        source.index=boundary
        baseline=pd.date_range(start.ceil('8h'),end,freq='8h')
        baseline=baseline[baseline<end]
        if not baseline.isin(source.index).all():
            raise ValueError(f'FUNDING_GAP: missing scheduled event {s}')
        # Extra observed events are retained; never discard off-00/08/16 events.
        normalized[s]=source.loc[(source.index>=start)&(source.index<end)]
    return normalized


def closed_four_hour(frames):
    result={}
    for s in SYMBOLS:
        bars=frames[s].resample('4h',label='left',closed='left').agg(
            {'open':'first','high':'max','low':'min','close':'last'})
        counts=frames[s]['close'].resample('4h').count()
        result[s]=bars.loc[counts==16]
    return result


def formation_diagnostics(signal, start, end):
    closes=pd.DataFrame({s:signal[s]['close'] for s in SYMBOLS})
    monday=start.normalize()-pd.Timedelta(days=start.weekday())
    return {week:fit_week(closes,week) for week in pd.date_range(monday,end,freq='7D') if week<end}


def summarize(account, snapshots, start, end, diagnostics, signals):
    equity=pd.Series([account.initial]+[x['equity'] for x in snapshots],
                     index=[start]+[pd.Timestamp(x['time']) for x in snapshots])
    equity=equity.groupby(level=0).last().sort_index()
    peak=equity.cummax()
    years={}
    for year in range(start.year,(end-pd.Timedelta(nanoseconds=1)).year+1):
        year_start=max(start,pd.Timestamp(f'{year}-01-01',tz='UTC'))
        year_end=min(end,pd.Timestamp(f'{year+1}-01-01',tz='UTC'))
        # End-labelled snapshots at Jan1 are the preceding Dec31 bar's close,
        # and simultaneously the following year's opening capital.
        opening=float(equity.loc[equity.index<=year_start].iloc[-1])
        close=float(equity.loc[equity.index<=year_end].iloc[-1])
        years[str(year)]=(close/opening-1)*100
    total=(account.wallet/account.initial-1)*100
    fees=sum(f['fee'] for f in account.fills)
    slip=sum(f['slippage_usd'] for f in account.fills)
    paid=sum(f['cashflow'] for f in account.funding_events)
    raw=sum(f['raw_cashflow'] for f in account.funding_events)
    gross=sum(p['gross_pnl'] for pair in account.completed_pairs for p in pair['closed_legs'])
    paired=[p for p in account.completed_pairs if p['complete_entry']]
    pnls=sorted((p['net_pnl'] for p in paired),reverse=True)
    enough=len(pnls)>=30
    verdict=('INSUFFICIENT_EVIDENCE' if not enough else 'V1_FAILED' if total<=0 else 'RESEARCH_CANDIDATE')
    return dict(start=str(start),end_exclusive=str(end),strategy='eth_btc_cointegration_v1',
        funding_mode=account.funding_mode,initial_equity_usd=account.initial,final_equity_usd=account.wallet,
        total_return_pct=total,max_drawdown_pct=float(((peak-equity)/peak).max()*100),
        completed_pairs=sum(p['complete_entry'] for p in account.completed_pairs),
        aborted_pairs=sum(not p['complete_entry'] for p in account.completed_pairs),
        win_rate_pct=100*sum(p>0 for p in pnls)/len(pnls) if pnls else None,
        price_pnl_before_slippage_usd=gross+slip,price_pnl_after_slippage_usd=gross,
        fees_usd=fees,slippage_usd=slip,funding_usd=paid,raw_funding_usd=raw,
        foregone_funding_usd=raw-paid,yearly_return_pct=years,open_legs=len(account.legs),
        formation_weeks=len(diagnostics),eligible_weeks=sum(d['eligible'] for d in diagnostics.values()),
        signal_count=len(signals),rejection_reasons=dict(Counter(x['reason'] for x in account.rejections)),
        holding_hours=[(pd.Timestamp(p['exit_time'])-pd.Timestamp(p['entry_time'])).total_seconds()/3600
                       for p in paired],
        top_pair_net_pnl_usd=pnls[:5],top_two_share_of_net_profit=sum(pnls[:2])/(account.wallet-account.initial)
        if pnls and account.wallet>account.initial else None,breaker_locks=account.breaker.lock_count,
        accounting_error_usd=account.accounting_error(),
        pnl_reconciliation_error_usd=(account.wallet-account.initial)-(gross-fees+paid),
        verdict=verdict,evidence='AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED',
        evaluation_type='SEEN_DATA_RETROSPECTIVE',
        limits=['15m last-price marking and intrabar protection; no orderbook fill proof',
                'funding uses settlement bar open proxy, not historical mark-price series',
                'at least 30 completed pairs is an evidence floor, not statistical significance'])


def replay(frames, funding, config, lots, start, end, funding_mode='actual',cost_multiplier=1.,
           second_leg_delay=0, metadata_source='explicit caller-supplied metadata', formations=None):
    start,end=utc(start),utc(end)
    if start>=end or start!=start.floor('15min') or end!=end.floor('15min'):
        raise ValueError('invalid half-open period')
    if second_leg_delay not in (0,1):
        raise ValueError('second leg delay must be 0 or 1 bar')
    account=PairAccount(config,lots,metadata_source,funding_mode,cost_multiplier)
    events=validate_market(frames,funding,start,end)
    signal=closed_four_hour(frames)
    diagnostics=formation_diagnostics(signal,start,end) if formations is None else formations
    previous_model=None
    model=None
    previous_z=float('nan')
    armed=False
    pending_entry=None
    pending_exit=None
    delayed_due=None
    snapshots=[]
    signals=[]
    current_atr={}
    indices=pd.date_range(start,end-BAR,freq='15min')
    # Arrays avoid per-row DataFrame overhead during multi-year replays.
    arrays={s:frames[s].loc[indices,['open','high','low','close']].to_numpy(float) for s in SYMBOLS}
    funding_maps={s:{t:r for t,r in events[s].iterrows()} for s in SYMBOLS}
    for i,when in enumerate(indices):
        bars={s:dict(zip(['open','high','low','close'],arrays[s][i])) for s in SYMBOLS}
        opens={s:float(bars[s]['open']) for s in SYMBOLS}
        closes={s:float(bars[s]['close']) for s in SYMBOLS}
        account.clock(when)
        account.mark(opens)
        prior_pending=account.pending_close
        week=when.normalize()-pd.Timedelta(days=when.weekday())
        diagnostic=diagnostics[week]
        next_model=diagnostic['model'] if diagnostic['eligible'] else None
        if week != previous_model:
            if account.pair:
                pending_exit=(when,'WEEKLY_RESET',account.pair['pair_id'])
            pending_entry=None
            model=next_model
            previous_model=week
            previous_z=float('nan')
            armed=False
        account.protect(when,bars,gap_only=True)
        # Funding before voluntary exits and entries, after gap protection.
        for s in SYMBOLS:
            if when in funding_maps[s]:
                r=funding_maps[s][when]
                account.settle(when,s,float(r['funding_rate']),opens[s],r['funding_source_time'])
        if account.pair and (prior_pending or account.breaker.is_locked):
            account.close_pair(when,opens,prior_pending or 'CIRCUIT_BREAKER')
            pending_entry=pending_exit=None
            armed=False
        if account.pair and account.pair.get('holding_deadline') and when>=pd.Timestamp(account.pair['holding_deadline']):
            account.close_pair(when,opens,'TIME_STOP')
            pending_exit=None
            armed=False
        if pending_exit and (not account.pair or account.pair['pair_id']!=pending_exit[2]):
            pending_exit=None
        if account.pair and pending_exit and when>pending_exit[0]:
            account.close_pair(when,opens,pending_exit[1])
            pending_exit=None
            armed=False
        if delayed_due is not None and when>=delayed_due:
            account.complete_delayed(when,opens)
            delayed_due=None
        # At a 4h boundary, only the just-finished 4h bar is visible.
        if when==when.floor('4h') and model:
            label=when-SIGNAL_BAR
            if all(label in signal[s].index for s in SYMBOLS):
                values={s:float(signal[s].at[label,'close']) for s in SYMBOLS}
                z=model.z(values['ETHUSDT'],values['BTCUSDT'])
                if account.pair:
                    opened=pd.Timestamp(account.pair['entry_time'])
                    reason='MEAN_REVERSION' if abs(z)<=.5 else 'SPREAD_STOP' if abs(z)>=4 else None
                    if reason and pending_exit is None:
                        pending_exit=(when,reason,account.pair['pair_id'])
                elif not pending_entry:
                    side=crossing(previous_z,z) if armed else 0
                    if side:
                        current_atr={s:simple_atr(signal[s].loc[:label]) for s in SYMBOLS}
                        pending_entry=dict(time=when,side=side,model=model,atr=dict(current_atr))
                        signals.append(dict(time=str(when),z=z,side=side,model_id=model.model_id))
                        armed=False
                    elif abs(z)<2:
                        armed=True
                previous_z=z
        if pending_entry and when>pending_entry['time'] and not account.pair:
            entry=pending_entry
            pending_entry=None
            m=entry['model']
            z=m.z(opens['ETHUSDT'],opens['BTCUSDT'])
            if not (2<=abs(z)<4 and (-1 if z>0 else 1)==entry['side']):
                account.reject(when,'ENTRY_Z_REVALIDATION')
            else:
                try:
                    proposal=account.size_pair(opens,entry['atr'],m.beta)
                    q=proposal['quantities']['ETHUSDT']
                    expected=q*(abs(z)-.5)*m.sigma
                    costs=sum(proposal['quantities'][s]*opens[s]*2*(account.fee+account.slip) for s in SYMBOLS)
                    if expected<=2*costs:
                        account.reject(when,'CONVERGENCE_COST_GATE')
                    elif account.open_fixed(when,entry['side'],proposal['quantities'],opens,
                            {s:3*entry['atr'][s] for s in SYMBOLS},m.model_id,
                            proposal['risk_budget'],signal_time=entry['time'],delay_second=bool(second_leg_delay)):
                        account.pair['holding_deadline']=str(when+min(math.ceil(3*m.half_life),42)*SIGNAL_BAR)
                        if second_leg_delay:
                            delayed_due=when+BAR
                except ValueError as error:
                    account.reject(when,error)
        account.protect(when+BAR,bars,intrabar_only=True)
        account.mark(closes)
        if abs(account.accounting_error())>1e-6:
            raise RuntimeError('PAIR_ACCOUNTING_ERROR')
        snapshots.append(dict(time=str(when+BAR),equity=account.equity,wallet=account.wallet))
    if account.pair:
        account.close_pair(end,closes,'END_OF_WINDOW')
        snapshots[-1].update(equity=account.equity,wallet=account.wallet)
    result=dict(summary=summarize(account,snapshots,start,end,diagnostics,signals),
                models=[model_payload(d) for d in diagnostics.values()],signals=signals,
                fills=account.fills,pairs=account.completed_pairs,funding=account.funding_events,
                rejections=account.rejections,equity=snapshots)
    return result
