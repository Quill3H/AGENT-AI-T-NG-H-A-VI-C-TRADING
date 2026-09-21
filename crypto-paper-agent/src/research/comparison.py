"""Chronological, non-overlapping OOS folds for independent strategy accounts."""
import math
import pandas as pd
from src.research.validation import positive_int, time_index, number


def walk_forward_splits(frame,train_bars,test_bars,step_bars=None,validation_bars=None):
    time_index(frame)
    train_bars=positive_int(train_bars,'train_bars');test_bars=positive_int(test_bars,'test_bars')
    step=test_bars if step_bars is None else positive_int(step_bars,'step_bars')
    if step<test_bars:raise ValueError('overlapping OOS windows are prohibited')
    validation_bars=max(1,train_bars//5) if validation_bars is None else positive_int(validation_bars,'validation_bars')
    if validation_bars>=train_bars:raise ValueError('validation must leave nonempty fit train')
    folds=[]
    for start in range(0,len(frame)-train_bars-test_bars+1,step):
        train=frame.iloc[start:start+train_bars-validation_bars].copy()
        validation=frame.iloc[start+train_bars-validation_bars:start+train_bars].copy()
        test=frame.iloc[start+train_bars:start+train_bars+test_bars].copy()
        folds.append({'fold':len(folds),'train':train,'validation':validation,'test':test,
            'train_start':train.index[0],'train_end':train.index[-1],
            'validation_start':validation.index[0],'validation_end':validation.index[-1],
            'test_start':test.index[0],'test_end':test.index[-1]})
    if not folds:raise ValueError('dataset is shorter than train_bars + test_bars')
    return folds


def compare_metrics(results):
    rows=[]
    for name,metrics in results.items():
        if 'total_net_pnl' not in metrics:raise KeyError(f'{name} is missing total_net_pnl')
        value=number(metrics['total_net_pnl'],'total_net_pnl',minimum=-float('inf'))
        count=metrics.get('total_trades',metrics.get('sample_count',0))
        if type(count) is not int or count<0:raise ValueError('sample_count must be a nonnegative integer')
        rows.append(dict(metrics,strategy=name,total_net_pnl=value,sample_count=count))
    if not rows:return pd.DataFrame(columns=['strategy','total_net_pnl','sample_count'])
    return pd.DataFrame(rows).sort_values(['total_net_pnl','strategy'],ascending=[False,True]).reset_index(drop=True)


def run_walk_forward(frame,strategy_runners,train_bars,test_bars,step_bars=None,initial_capital=10000.0):
    number(initial_capital,'initial_capital',positive=True)
    folds=walk_forward_splits(frame,train_bars,test_bars,step_bars);rows=[];aggregate={}
    for fold in folds:
        for name,runner in strategy_runners.items():
            metrics=dict(runner(fold['train'].copy(),fold['test'].copy()))
            checked=compare_metrics({name:metrics}).iloc[0]
            pnl=float(checked.total_net_pnl);count=int(checked.sample_count)
            rows.append({k:v for k,v in fold.items() if k not in ('train','validation','test')} |
                {'strategy':name,'total_net_pnl':pnl,'sample_count':count,'initial_capital':float(initial_capital)})
            agg=aggregate.setdefault(name,{'total_net_pnl':0.0,'sample_count':0,'fold_count':0})
            agg['total_net_pnl']+=pnl;agg['sample_count']+=count;agg['fold_count']+=1
    for a in aggregate.values():a['mean_fold_return_pct']=100*a['total_net_pnl']/(initial_capital*a['fold_count'])
    return pd.DataFrame(rows),compare_metrics(aggregate)
