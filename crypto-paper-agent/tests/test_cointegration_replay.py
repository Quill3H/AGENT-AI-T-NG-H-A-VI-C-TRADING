import importlib
import importlib.util

import numpy as np
import pandas as pd
import pytest


def api():
    name = 'src.research.cointegration'
    assert importlib.util.find_spec(name), 'pair replay is not implemented'
    return importlib.import_module(name)


def market():
    rng = np.random.default_rng(4)
    start, end = pd.Timestamp('2026-06-01',tz='UTC'), pd.Timestamp('2026-06-15',tz='UTC')
    index = pd.date_range(start-pd.Timedelta(days=94),end-pd.Timedelta(minutes=15),freq='15min')
    btc = 600000+np.cumsum(rng.normal(0,1000,len(index)))
    spread = np.zeros(len(index))
    for i in range(1,len(index)):
        spread[i]=.994*spread[i-1]+rng.normal(0,30)
    frames={}
    for symbol,close in [('BTCUSDT',btc),('ETHUSDT',1000+.05*btc+spread)]:
        opened=np.r_[close[0],close[:-1]]
        frames[symbol]=pd.DataFrame({'open':opened,'high':np.maximum(opened,close)+10,
            'low':np.minimum(opened,close)-10,'close':close},index=index)
    fundindex=pd.date_range(index[0].ceil('8h'),end-pd.Timedelta(hours=1),freq='8h')
    funding={s:pd.DataFrame({'funding_rate':0.,'funding_interval_hours':8.},index=fundindex)
             for s in frames}
    lots={s:{'step':1e-6,'min_quantity':1e-6,'min_notional':1.} for s in frames}
    return frames,funding,lots,start,end


def test_missing_execution_bar_fails_before_performance(config):
    frames,funding,lots,start,end=market()
    frames['ETHUSDT']=frames['ETHUSDT'].drop(start+pd.Timedelta(minutes=30))
    with pytest.raises(ValueError,match='DATA_GAP'):
        api().replay(frames,funding,config,lots,start,end)


def test_missing_standard_funding_is_not_synthesized_as_zero(config):
    frames,funding,lots,start,end=market()
    funding['ETHUSDT']=funding['ETHUSDT'].drop(start+pd.Timedelta(hours=8))
    with pytest.raises(ValueError,match='FUNDING_GAP'):
        api().replay(frames,funding,config,lots,start,end)


def test_replay_is_causal_and_next_open_is_strictly_later(config):
    frames,funding,lots,start,end=market()
    original=api().replay(frames,funding,config,lots,start,end)
    assert original['summary']['completed_pairs'] > 0
    assert original['summary']['eligible_weeks'] == 2
    cut=start+pd.Timedelta(days=7)
    revised={s:f.copy() for s,f in frames.items()}
    for f in revised.values():
        f.loc[f.index>=cut,['open','high','low','close']]*=1.1
    future=api().replay(revised,funding,config,lots,start,end)
    for key in ['signals','fills']:
        assert [x for x in original[key] if pd.Timestamp(x['time'])<cut] == [
            x for x in future[key] if pd.Timestamp(x['time'])<cut]
    for fill in original['fills']:
        if fill['kind']=='ENTRY':
            assert pd.Timestamp(fill['time'])>pd.Timestamp(fill['signal_time'])
    assert original['summary']['accounting_error_usd']==pytest.approx(0.,abs=1e-8)
    assert original['summary']['open_legs']==0


def test_delayed_second_leg_really_has_later_fill(config):
    frames,funding,lots,start,end=market()
    result=api().replay(frames,funding,config,lots,start,end,second_leg_delay=1)
    entries=[f for f in result['fills'] if f['kind']=='ENTRY']
    assert len(entries)>=2
    assert pd.Timestamp(entries[1]['time'])-pd.Timestamp(entries[0]['time'])==pd.Timedelta(minutes=15)
    assert result['summary']['open_legs']==0


def test_invalid_funding_mode_or_delay_is_rejected(config):
    frames,funding,lots,start,end=market()
    with pytest.raises(ValueError):
        api().replay(frames,funding,config,lots,start,end,funding_mode='ignore_costs')
    with pytest.raises(ValueError):
        api().replay(frames,funding,config,lots,start,end,second_leg_delay=2)


def test_millisecond_market_indices_have_same_replay_as_microseconds(config):
    frames,funding,lots,start,end=market()
    expected=api().replay(frames,funding,config,lots,start,end)['summary']
    for f in frames.values():
        f.index=f.index.as_unit('ms')
    assert api().replay(frames,funding,config,lots,start,end)['summary']==expected


def test_protective_completion_cannot_leave_exit_order_for_next_pair(config):
    from src.strategies.eth_btc_cointegration import WeeklyModel
    start=pd.Timestamp('2026-06-01',tz='UTC')
    end=start+pd.Timedelta(days=1)
    index=pd.date_range(start-pd.Timedelta(days=3),end-pd.Timedelta(minutes=15),freq='15min')
    z=np.zeros(len(index))
    for a,b in [(3.75,7.5),(15.75,24)]:
        z[(index>=start+pd.Timedelta(hours=a))&(index<start+pd.Timedelta(hours=b))]=2.5
    frames={}
    for s,values in [('ETHUSDT',3000+100*z),('BTCUSDT',np.full(len(index),60000.))]:
        opened=np.r_[values[0],values[:-1]]
        frames[s]=pd.DataFrame({'open':opened,'high':np.maximum(opened,values)+10,
            'low':np.minimum(opened,values)-10,'close':values},index=index)
    frames['ETHUSDT'].loc[start+pd.Timedelta(hours=8),['high','low']]=[4000,2000]
    frames['BTCUSDT'].loc[start+pd.Timedelta(hours=8),['high','low']]=[62000,58000]
    funding={s:pd.DataFrame({'funding_rate':0.},index=pd.date_range(start,end,freq='8h')) for s in frames}
    lots={s:{'step':1e-6,'min_quantity':1e-6,'min_notional':1.} for s in frames}
    formation={start:dict(week=str(start),eligible=True,reason='ELIGIBLE',
        model=WeeklyModel(str(start),0,.05,0,100,.9,6.58,'controlled-model'))}
    result=api().replay(frames,funding,config,lots,start,end,formations=formation)
    assert len(result['pairs'])==2
    assert result['pairs'][1]['reason']=='END_OF_WINDOW'


def test_time_stop_is_36_hours_from_fill_not_40_hours(config):
    from src.strategies.eth_btc_cointegration import WeeklyModel
    start=pd.Timestamp('2026-06-01',tz='UTC'); end=start+pd.Timedelta(days=3)
    index=pd.date_range(start-pd.Timedelta(days=3),end-pd.Timedelta(minutes=15),freq='15min')
    z=np.where(index>=start+pd.Timedelta(hours=3.75),2.5,0.)
    frames={}
    for s,values in [('ETHUSDT',3000+100*z),('BTCUSDT',np.full(len(index),60000.))]:
        opened=np.r_[values[0],values[:-1]]
        frames[s]=pd.DataFrame({'open':opened,'high':np.maximum(opened,values)+10,
            'low':np.minimum(opened,values)-10,'close':values},index=index)
    funding={s:pd.DataFrame({'funding_rate':0.},index=pd.date_range(start,end,freq='8h')) for s in frames}
    lots={s:{'step':1e-6,'min_quantity':1e-6,'min_notional':1.} for s in frames}
    formation={start:dict(week=str(start),eligible=True,reason='ELIGIBLE',
        model=WeeklyModel(str(start),0,.05,0,100,.9,3.,'controlled-model'))}
    result=api().replay(frames,funding,config,lots,start,end,formations=formation)
    pair=result['pairs'][0]
    assert pair['reason']=='TIME_STOP'
    assert pd.Timestamp(pair['exit_time'])-pd.Timestamp(pair['entry_time'])==pd.Timedelta(hours=36)
