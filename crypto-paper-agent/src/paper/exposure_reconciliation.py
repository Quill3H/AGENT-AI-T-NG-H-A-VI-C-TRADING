"""Semantic restore audit against broker-authored fills and realized lifecycles."""
from src.execution.funding_model import FixedFundingModel
from src.execution.order_models import OrderDirection, OrderStatus, PositionStatus
from src.paper.trials import finite, utc
import math


def equal(actual, expected, label):
    if not math.isclose(finite(actual), finite(expected), rel_tol=1e-9, abs_tol=1e-8):
        raise ValueError(f'execution lifecycle {label} disagrees with ledger')


def positive(value):
    result = finite(value)
    if result <= 0:
        raise ValueError('nonpositive execution lifecycle value')
    return result


def verify_execution_reconciliation(broker):
    """Quantity, collateral and fees cannot be validated from position totals alone."""
    fills = {}
    model = FixedFundingModel.from_config(broker.config)
    for order in broker.order_history:
        if order.status != OrderStatus.FILLED:
            continue
        terms = order.metadata.get('broker_entry')
        required = {'lifecycle_id', 'leverage', 'initial_stop_loss_price',
                    'initial_liquidation_price', 'take_profit_price', 'conviction_tier', 'partial_targets'}
        if type(terms) is not dict or set(terms) != required or not terms['lifecycle_id']:
            raise ValueError('filled execution lacks broker-authored lifecycle terms')
        identity = terms['lifecycle_id']
        if identity in fills or order.direction not in (OrderDirection.LONG, OrderDirection.SHORT):
            raise ValueError('duplicate/invalid filled execution lifecycle')
        q, price = positive(order.filled_quantity), positive(order.actual_fill_price)
        positive(order.reference_price)
        leverage = positive(terms['leverage'])
        if not 1 <= leverage <= 5:
            raise ValueError('execution leverage exceeds protected lifecycle')
        equal(order.notional_usd, q * price, 'entry notional')
        equal(order.fee_usd, q * price * broker.taker_fee_pct, 'entry fee')
        equal(order.slippage_usd, q * abs(price - order.reference_price), 'entry slippage')
        sign = 1 if order.direction == OrderDirection.LONG else -1
        stop = positive(terms['initial_stop_loss_price'])
        if sign * (price - stop) <= 0:
            raise ValueError('execution initial stop has invalid direction')
        liq = broker._calculate_liquidation_price_for_collateral(
            order.symbol, order.direction, q, price, q * price / leverage, identity)
        equal(terms['initial_liquidation_price'], liq, 'initial liquidation')
        if utc(order.processed_at) < utc(order.requested_at):
            raise ValueError('execution predates its causal request')
        if broker.current_time is None or utc(order.processed_at) > utc(broker.current_time):
            raise ValueError('execution exceeds broker clock')
        fills[identity] = {'order': order, 'terms': terms, 'trades': [], 'position': None, 'funding': []}

    for trade in broker.trade_history:
        group = fills.get(trade.metadata.get('lifecycle_id'))
        if group is None:
            raise ValueError('realization has no filled execution lifecycle')
        group['trades'].append(trade)
    for position in broker.positions.values():
        group = fills.get(position.position_id)
        if group is None or group['position'] is not None:
            raise ValueError('active exposure has no unique filled execution lifecycle')
        group['position'] = position
    for event in broker.funding_history:
        group = fills.get(event.position_id)
        if group is None:
            raise ValueError('funding has no filled execution lifecycle')
        group['funding'].append(event)

    for identity, group in fills.items():
        order, terms, trades, position = (group[k] for k in ('order', 'terms', 'trades', 'position'))
        q, price, leverage = order.filled_quantity, order.actual_fill_price, terms['leverage']
        sign = 1 if order.direction == OrderDirection.LONG else -1
        remaining_q = position.quantity if position else 0
        equal(sum(positive(t.quantity) for t in trades) + remaining_q, q, 'exposure quantity')
        previous = order.processed_at
        for record in [*trades, *([position] if position else [])]:
            if record.symbol != order.symbol or record.direction != order.direction:
                raise ValueError('exposure direction/symbol disagrees with filled execution')
            equal(record.entry_price, price, 'entry price')
            equal(record.leverage, leverage, 'leverage')
            equal(record.initial_margin, record.quantity * price / leverage, 'initial margin')
            equal(record.entry_fee, order.fee_usd * record.quantity / q, 'allocated entry fee')
            equal(record.initial_stop_loss_price, terms['initial_stop_loss_price'], 'initial stop')
            equal(record.metadata.get('lifecycle_quantity'), q, 'original quantity')
            if record.metadata.get('lifecycle_id') != identity:
                raise ValueError('exposure lifecycle identity disagrees with execution')
            if record.conviction_tier != terms['conviction_tier']:
                raise ValueError('exposure conviction disagrees with execution')
        allocated = [0.] * len(trades)
        active_funding = 0.
        seen = set()
        for event in group['funding']:
            stamp = utc(event.timestamp)
            if (event.symbol != order.symbol or event.direction != order.direction or stamp in seen
                    or stamp <= utc(order.processed_at) or stamp > utc(broker.current_time)
                    or stamp.hour not in broker.funding_hours or stamp.minute or stamp.second or stamp.microsecond):
                raise ValueError('invalid funding lifecycle timestamp/direction')
            seen.add(stamp)
            rate = finite(event.funding_rate)
            if model and stamp >= model.effective_at:
                equal(rate, model.rate_at(order.symbol, stamp), 'fixed funding rate')
                if event.event_id != model.event_id(identity, order.symbol, stamp):
                    raise ValueError('fixed funding lifecycle event identity mismatch')
            positive(event.position_quantity)
            equal(event.cashflow_usd, -sign * event.position_quantity * positive(event.settlement_mark_price) * rate,
                  'funding cashflow')
            available = q - sum(t.quantity for t in trades if t.exit_time < stamp)
            same = [i for i, t in enumerate(trades) if t.exit_time == stamp]
            # Gap exits precede funding; later same-timestamp exits follow it.
            # The authenticated settlement quantity determines that exact prefix.
            before = []
            for index in [None, *same]:
                if index is not None:
                    available -= trades[index].quantity
                    before.append(index)
                if math.isclose(available, event.position_quantity, rel_tol=1e-9, abs_tol=1e-8):
                    break
            else:
                raise ValueError('funding quantity disagrees with remaining execution exposure')
            for index, trade in enumerate(trades):
                if trade.exit_time > stamp or trade.exit_time == stamp and index not in before:
                    allocated[index] += event.cashflow_usd * trade.quantity / event.position_quantity
            active_funding += event.cashflow_usd * remaining_q / event.position_quantity
        for index, trade in enumerate(trades):
            if utc(trade.entry_time) != order.processed_at or not previous <= utc(trade.exit_time) <= utc(broker.current_time):
                raise ValueError('realized lifecycle chronology disagrees with execution')
            previous = trade.exit_time
            equal(trade.funding_cashflow, allocated[index], 'realized funding allocation')
            equal(trade.gross_price_pnl, sign * trade.quantity * (positive(trade.exit_price) - price), 'gross PnL')
            equal(trade.exit_fee, trade.quantity * trade.exit_price * broker.taker_fee_pct, 'exit fee')
            equal(trade.net_pnl, trade.gross_price_pnl - trade.entry_fee - trade.exit_fee + allocated[index], 'net PnL')
            equal(trade.return_pct, trade.net_pnl / trade.initial_margin * 100, 'return percent')
            equal(trade.estimated_liquidation_price, terms['initial_liquidation_price'], 'realized initial liquidation')
            equal(trade.initial_risk_usd, trade.quantity * abs(price - terms['initial_stop_loss_price']), 'initial risk')
            equal(trade.realized_r_multiple, trade.net_pnl / trade.initial_risk_usd, 'realized R')
            expected_targets = [] if terms['take_profit_price'] is None else [terms['take_profit_price']]
            if trade.take_profit_levels != expected_targets:
                raise ValueError('realized take-profit schedule disagrees with execution')
            if trade.metadata.get('lifecycle_complete') is not (position is None and index == len(trades) - 1):
                raise ValueError('realization completion disagrees with remaining exposure')
        if position:
            if position.status != PositionStatus.OPEN or utc(position.opened_at) != order.processed_at:
                raise ValueError('active exposure lifecycle/entry timestamp mismatch')
            equal(position.cumulative_funding, active_funding, 'active funding allocation')
            equal(position.isolated_collateral, position.initial_margin + active_funding, 'isolated collateral')
            equal(position.initial_liquidation_price, terms['initial_liquidation_price'], 'original liquidation')
            equal(position.liquidation_price, broker._calculate_collateral_aware_liquidation_price(position), 'current liquidation')
            mark = positive(broker.last_mark_prices.get(position.symbol))
            equal(getattr(position, '_last_unrealized_pnl', None),
                  position.calculate_unrealized_pnl(mark), 'cached mark PnL')
            equal(position.metadata.get('realized_slices_net', 0), sum(t.net_pnl for t in trades), 'realized slice total')
            if sign * (position.stop_loss_price - terms['initial_stop_loss_price']) < -1e-8:
                raise ValueError('active exposure stop loosened beyond execution risk')
            if sign * (mark - position.stop_loss_price) <= 0:
                raise ValueError('active exposure stop crosses the current execution mark')
            if terms['take_profit_price'] is None:
                if position.take_profit_price is not None:
                    raise ValueError('active exposure take-profit has no filled execution declaration')
            else:
                equal(position.take_profit_price, terms['take_profit_price'], 'active take-profit')
            targets = terms['partial_targets']
            if position.metadata.get('partial_targets', []) != targets:
                raise ValueError('active exposure partial schedule disagrees with execution')
            if targets:
                equal(position.metadata.get('original_quantity'), q, 'partial original quantity')
                if type(position.metadata.get('partials_done')) is not int or position.metadata['partials_done'] != len(trades):
                    raise ValueError('partial execution watermark disagrees with realizations')
    for request in broker.pending_orders:
        orders = [o for o in broker.order_history if o.status == OrderStatus.PENDING
                  and o.symbol == request.symbol and o.requested_at == request.signal_time]
        terms = {k: v for k, v in vars(request).items() if k != 'metadata'}
        if (len(orders) != 1 or orders[0].metadata.get('broker_request') != terms
                or orders[0].direction != request.direction or orders[0].order_type != request.order_type
                or orders[0].reference_price != request.signal_price):
            raise ValueError('pending request terms disagree with execution ledger')
