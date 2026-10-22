"""Shared-capital, two-leg paper account, reusing the project's risk gates.

No exchange client. Stops on one symbol never fill the partner at a fabricated
simultaneous price: the coordinator closes the partner on the next open.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_DOWN
import math

import pandas as pd

from src.execution.order_models import OrderDirection
from src.execution.paper_broker import PaperBroker
from src.risk.invariant_checks import check_all_invariants

SYMBOLS = ('ETHUSDT', 'BTCUSDT')


def positive(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
        raise ValueError('expected finite positive number')
    return float(value)


def round_quantity(value, step):
    step = Decimal(str(positive(step)))
    return float((Decimal(str(positive(value))) / step).to_integral_value(rounding=ROUND_DOWN) * step)


class PairAccount:
    """One wallet, one breaker, one pair lifecycle, and explicit leg cashflows."""

    def __init__(self, config, lots, metadata_source, funding_mode='actual', cost_multiplier=1.):
        if funding_mode not in ('actual', 'no_positive'):
            raise ValueError('invalid funding mode')
        positive(cost_multiplier)
        if not metadata_source:
            raise ValueError('lot metadata source is required')
        self.config = deepcopy(config)
        for key in ('taker_pct','maker_pct','slippage_pct'):
            self.config.setdefault('fees', {})[key] = float(config.get('fees', {}).get(
                key, .0003 if key == 'slippage_pct' else .0005)) * cost_multiplier
        self.helper = PaperBroker(self.config)
        self.breaker = self.helper.circuit_breaker
        self.news_filter = self.helper.news_filter
        self.initial = self.helper.initial_balance
        self.wallet = self.initial
        self.fee = self.helper.taker_fee_pct
        self.slip = self.helper.slippage_pct
        self.funding_mode = funding_mode
        self.metadata_source = metadata_source
        self.lots = deepcopy(lots)
        for s in SYMBOLS:
            for key in ('step','min_quantity','min_notional'):
                positive(self.lots[s][key])
        self.legs = {}
        self.pair = None
        self.completed_pairs = []
        self.fills = []
        self.cashflows = []
        self.funding_events = []
        self.rejections = []
        self.settled = set()
        self.pending_close = None
        self.time = None
        self.sequence = 0

    @property
    def equity(self):
        return self.wallet + sum(p['sign']*p['quantity']*(p['mark']-p['entry']) for p in self.legs.values())

    @property
    def available(self):
        return self.wallet-sum(p['collateral'] for p in self.legs.values())

    def clock(self, when):
        when = pd.Timestamp(when)
        if when.tzinfo is None or (self.time is not None and when < self.time):
            raise ValueError('invalid or reversed account time')
        self.time = when
        self.breaker.advance_time(when.to_pydatetime())
        return when

    def mark(self, prices):
        for s,p in self.legs.items():
            p['mark'] = positive(float(prices[s]))

    def reject(self, when, reason):
        self.rejections.append(dict(time=str(when), reason=str(reason)))
        return False

    def _cash(self, when, amount, kind, symbol):
        self.wallet += amount
        self.cashflows.append(dict(time=str(when),amount=amount,kind=kind,symbol=symbol,
                                   pair_id=self.pair['pair_id'] if self.pair else None))
        self.breaker.record_cashflow(float(amount), when.to_pydatetime(), max(0.,self.equity))
        if self.breaker.is_locked:
            self.pending_close = 'CIRCUIT_BREAKER'

    def size_pair(self, prices, atr, beta):
        beta = positive(float(beta))
        equity = self.equity
        budget = .005*equity*self.breaker.risk_multiplier
        unit_notional = prices['ETHUSDT']+beta*prices['BTCUSDT']
        unit_loss = 3*atr['ETHUSDT']+beta*3*atr['BTCUSDT']+2*(self.fee+self.slip)*unit_notional
        q = min(budget/unit_loss, equity/(unit_notional*(1+self.fee+self.slip)))
        quantities = {s:round_quantity(q*factor,self.lots[s]['step'])
                      for s,factor in zip(SYMBOLS,[1.,beta])}
        if min(quantities.values()) <= 0:
            raise ValueError('LOT_TOO_SMALL')
        total = sum(quantities[s]*prices[s] for s in SYMBOLS)
        error = abs(quantities['BTCUSDT']-beta*quantities['ETHUSDT'])*prices['BTCUSDT']/total
        if error > .01:
            raise ValueError('HEDGE_ROUNDING_ERROR')
        loss = sum(quantities[s]*(3*atr[s]+2*(self.fee+self.slip)*prices[s]) for s in SYMBOLS)
        return dict(quantities=quantities,risk_usd=loss,risk_budget=budget,
                    notional=total,hedge_rounding_fraction=error)

    def _candidate(self, symbol, sign, quantity, price, stop_distance, when, risk_budget, available):
        quantity, price, distance = positive(float(quantity)), positive(float(price)), positive(float(stop_distance))
        lot = self.lots[symbol]
        if abs(quantity-round_quantity(quantity,lot['step'])) > 1e-10:
            raise ValueError('LOT_STEP')
        fill = price*(1+sign*self.slip)
        notional = quantity*fill
        if quantity < lot['min_quantity'] or notional < lot['min_notional']:
            raise ValueError('LOT_MINIMUM')
        stop = fill-sign*distance
        positive(stop)
        effective = risk_budget / self.equity
        order = dict(symbol=symbol,direction='LONG' if sign>0 else 'SHORT',entry_price=fill,
                     stop_loss_price=stop,leverage=1.,base_risk_percent=effective/self.breaker.risk_multiplier,
                     risk_percent=effective,conviction_tier='normal',position_size_usd=notional,timestamp=when)
        state = dict(equity=float(self.equity), available_margin=float(available), current_time=when,
                     circuit_breaker_state=self.breaker,news_filter=self.news_filter)
        valid,reasons = check_all_invariants(order,state,self.config)
        if not valid:
            raise ValueError('; '.join(reasons))
        direction = OrderDirection.LONG if sign>0 else OrderDirection.SHORT
        liquidation = self.helper._calculate_liquidation_price_for_collateral(
            symbol,direction,quantity,fill,notional)
        return dict(symbol=symbol,sign=sign,quantity=quantity,entry=fill,stop=stop,
                    collateral=notional,liquidation=liquidation,mark=price,
                    entry_fee=notional*self.fee,funding=0.,opened_at=str(when))

    def open_fixed(self, when, side, quantities, prices, distances, model_id, risk_budget,
                   signal_time=None, delay_second=False):
        when = self.clock(when)
        if side not in (-1,1):
            raise ValueError('invalid side')
        if self.pair or not self.breaker.is_trading_allowed(when.to_pydatetime()):
            return self.reject(when,'PAIR_OPEN_OR_BREAKER')
        if any(not math.isfinite(float(prices[s])) for s in SYMBOLS):
            raise ValueError('invalid prices')
        predicted_loss = sum(quantities[s]*(distances[s]+2*(self.fee+self.slip)*prices[s]) for s in SYMBOLS)
        if predicted_loss > risk_budget+1e-8:
            return self.reject(when,'PAIR_RISK_BUDGET')
        available = self.available
        candidates=[]
        try:
            for s,sign in zip(SYMBOLS,[side,-side]):
                p = self._candidate(s,sign,quantities[s],prices[s],distances[s],when,risk_budget,available)
                available -= p['collateral']+p['entry_fee']
                candidates.append(p)
            if sum(p['collateral'] for p in candidates) > self.equity or available < -1e-8:
                raise ValueError('PAIR_MARGIN')
        except (ValueError,TypeError) as error:
            return self.reject(when,error)
        self.sequence += 1
        self.pair = dict(pair_id=f'PAIR_{self.sequence:06d}', model_id=model_id, side=side,
                         entry_time=str(when), signal_time=str(signal_time or when),
                         wallet_before=self.wallet,closed_legs=[],complete_entry=not delay_second,
                         delayed=candidates[1] if delay_second else None,risk_budget=risk_budget)
        self._enter(when,candidates[0],prices[candidates[0]['symbol']])
        if not delay_second:
            self._enter(when,candidates[1],prices[candidates[1]['symbol']])
        return True

    def _enter(self,when,p,raw):
        self.legs[p['symbol']]=p
        self.fills.append(dict(time=str(when),signal_time=self.pair['signal_time'],kind='ENTRY',
            pair_id=self.pair['pair_id'],symbol=p['symbol'],quantity=p['quantity'],price=p['entry'],
            raw_price=raw,slippage_usd=abs(p['entry']-raw)*p['quantity'],fee=p['entry_fee']))
        self._cash(when,-p['entry_fee'],'ENTRY_FEE',p['symbol'])

    def complete_delayed(self,when,prices):
        when=self.clock(when)
        if not self.pair or not self.pair['delayed']:
            return
        old=self.pair['delayed']
        self.mark(prices)
        try:
            if self.pending_close or not self.breaker.is_trading_allowed(when.to_pydatetime()):
                raise ValueError('DELAYED_ENTRY_CANCELLED')
            candidate=self._candidate(old['symbol'],old['sign'],old['quantity'],prices[old['symbol']],
                abs(old['entry']-old['stop']),when,self.pair['risk_budget'],self.available)
            if sum(p['quantity']*prices[s] for s,p in self.legs.items())+candidate['collateral']>self.equity:
                raise ValueError('DELAYED_MARGIN')
            self._enter(when,candidate,prices[old['symbol']])
            self.pair['delayed']=None
            self.pair['complete_entry']=True
        except ValueError as error:
            self.reject(when,error)
            self.close_pair(when,prices,'SECOND_LEG_FAILED')

    def settle(self,when,symbol,rate,mark,source_time=None):
        when=self.clock(when)
        key=(symbol,when)
        if key in self.settled:
            raise ValueError('DUPLICATE_FUNDING')
        if isinstance(rate,bool) or not math.isfinite(float(rate)):
            raise ValueError('invalid funding rate')
        mark=positive(float(mark))
        if symbol not in self.legs:
            self.settled.add(key)
            return
        p=self.legs[symbol]
        raw=-p['sign']*p['quantity']*mark*float(rate)
        cash=min(0.,raw) if self.funding_mode=='no_positive' else raw
        direction=OrderDirection.LONG if p['sign']>0 else OrderDirection.SHORT
        liquidation=self.helper._calculate_liquidation_price_for_collateral(
            symbol,direction,p['quantity'],p['entry'],p['collateral']+cash)
        p['collateral']+=cash
        p['funding']+=cash
        p['liquidation']=liquidation
        self.settled.add(key)
        self.funding_events.append(dict(time=str(when),source_time=str(source_time or when),
            symbol=symbol,rate=float(rate),mark=mark,raw_cashflow=raw,cashflow=cash,
            pair_id=self.pair['pair_id']))
        self._cash(when,cash,'FUNDING',symbol)

    def close_leg(self,when,symbol,raw,reason):
        when=self.clock(when)
        if symbol not in self.legs:
            return
        p=self.legs[symbol]
        fill=positive(float(raw))*(1-p['sign']*self.slip)
        gross=p['sign']*p['quantity']*(fill-p['entry'])
        fee=fill*p['quantity']*self.fee
        self.fills.append(dict(time=str(when),kind='EXIT',pair_id=self.pair['pair_id'],symbol=symbol,
            quantity=p['quantity'],price=fill,raw_price=float(raw),fee=fee,
            slippage_usd=abs(fill-raw)*p['quantity'],reason=reason))
        del self.legs[symbol]
        self.pair['closed_legs'].append(dict(symbol=symbol,quantity=p['quantity'],gross_pnl=gross,
            funding=p['funding'],fees=p['entry_fee']+fee,reason=reason,exit_time=str(when)))
        self._cash(when,gross-fee,'EXIT_REALIZATION',symbol)
        if not self.legs:
            self.pair['exit_time']=str(when)
            self.pair['net_pnl']=self.wallet-self.pair['wallet_before']
            self.pair['reason']=reason
            self.breaker.record_trade_outcome(float(self.pair['net_pnl']),when.to_pydatetime())
            self.completed_pairs.append(self.pair)
            self.pair=None
            self.pending_close=None

    def close_pair(self,when,prices,reason):
        when=self.clock(when)
        self.mark(prices)
        for s in list(self.legs):
            self.close_leg(when,s,prices[s],reason)

    def protect(self,when,bars,gap_only=False,intrabar_only=False):
        when=self.clock(when)
        for s in list(self.legs):
            p=self.legs[s]
            b=bars[s]
            long=p['sign']>0
            gap_liq=b['open']<=p['liquidation'] if long else b['open']>=p['liquidation']
            gap_stop=b['open']<=p['stop'] if long else b['open']>=p['stop']
            if not intrabar_only and (gap_liq or gap_stop):
                self.close_leg(when,s,b['open'],'GAP_LIQUIDATION' if gap_liq else 'GAP_STOP')
            elif not gap_only:
                liq=b['low']<=p['liquidation'] if long else b['high']>=p['liquidation']
                stop=b['low']<=p['stop'] if long else b['high']>=p['stop']
                if liq or stop:
                    self.close_leg(when,s,p['liquidation'] if liq else p['stop'],
                                   'LIQUIDATION' if liq else 'STOP')
        if self.legs and len(self.legs)==1 and self.pair and not self.pair['delayed']:
            self.pending_close='PARTNER_STOP'

    def accounting_error(self):
        return self.wallet-self.initial-sum(c['amount'] for c in self.cashflows)
