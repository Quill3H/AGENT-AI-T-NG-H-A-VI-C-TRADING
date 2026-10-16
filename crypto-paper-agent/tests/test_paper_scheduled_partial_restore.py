"""Hand oracles for scheduled partial exits across funding and exact restarts."""
from copy import deepcopy
from datetime import timedelta

import pytest

from src.execution.order_models import OrderRequest, OrderStatus
from src.paper.causal_runner import CausalRunner
from src.paper.public_stream import SYMBOLS
from test_local_paper_session import BASE
from test_paper_causal_runner import batch, runner_fixture


FEE = 0.0005
SLIPPAGE = 0.0003
FUNDING = 0.0001


def scheduled_runner(config, direction, phase):
    seed = runner_fixture(config)
    cfg = deepcopy(seed.config)
    cfg['fees'] = {'taker_pct': FEE, 'maker_pct': 0.0002, 'slippage_pct': SLIPPAGE}
    runner = CausalRunner(cfg, 'trend_following', BASE)
    runner.initialize(seed.signal_history, batch(BASE - timedelta(minutes=15)))
    runner.broker.submit_order(OrderRequest(
        symbol='BTCUSDT', direction=direction, signal_price=100,
        stop_loss_price=98 if direction == 'LONG' else 102,
        signal_time=BASE, requested_quantity=1, leverage=2,
        partial_exits=[(1.5, 0.4), (3, 0.3)],
    ))
    runner.advance(batch(BASE))
    assert runner.broker.order_history[0].status == OrderStatus.FILLED
    assert not runner.broker.trade_history
    for index in range(1, 16):
        bars = batch(BASE + timedelta(minutes=15 * index))
        signals = {
            symbol: dict(bars[symbol], open_time=BASE,
                         close_time=BASE + timedelta(hours=4),
                         timeframe='4h', volume=80)
            for symbol in SYMBOLS
        } if index == 15 else None
        runner.advance(bars, signals)
    assert not runner.broker.funding_history
    assert not runner.broker.trade_history
    assert runner.broker.positions['BTCUSDT'].quantity == 1

    closing_price = 107 if direction == 'LONG' else 93
    bars = batch(BASE + timedelta(hours=4), closing_price if phase == 'gap' else 100)
    if phase == 'intrabar':
        for bar in bars.values():
            bar.update(high=108 if direction == 'LONG' else 101,
                       low=99 if direction == 'LONG' else 92, close=closing_price)
    runner.advance(bars)
    return runner, closing_price


@pytest.mark.parametrize('direction', ['LONG', 'SHORT'])
@pytest.mark.parametrize('phase', ['gap', 'intrabar'])
def test_scheduled_partial_funding_hand_oracle_and_repeated_restore(config, direction, phase):
    runner, closing_price = scheduled_runner(config, direction, phase)
    broker = runner.broker
    sign = 1 if direction == 'LONG' else -1
    entry_price = 100 * (1 + sign * SLIPPAGE)
    entry_fee = entry_price * FEE
    distance = abs(entry_price - (98 if direction == 'LONG' else 102))
    settlement_price = closing_price if phase == 'gap' else 100
    settlement_quantity = 0.3 if phase == 'gap' else 1
    total_funding = -sign * settlement_quantity * settlement_price * FUNDING
    active_funding = -sign * 0.3 * settlement_price * FUNDING
    quantities = [0.4, 0.3]
    partial_prices = [closing_price * (1 - sign * SLIPPAGE)] * 2 if phase == 'gap' else [
        (entry_price + sign * rr * distance) * (1 - sign * SLIPPAGE)
        for rr in (1.5, 3)
    ]
    gross_pnls = [sign * quantity * (price - entry_price)
                  for quantity, price in zip(quantities, partial_prices)]
    exit_fees = [quantity * price * FEE for quantity, price in zip(quantities, partial_prices)]
    partial_funding = [0, 0] if phase == 'gap' else [
        -sign * quantity * settlement_price * FUNDING for quantity in quantities
    ]
    wallet = 10000 - entry_fee + sum(gross_pnls) - sum(exit_fees) + total_funding
    unrealized = sign * 0.3 * (closing_price - entry_price)

    assert len(broker.order_history) == 1
    assert broker.order_history[0].fee_usd == pytest.approx(entry_fee)
    assert broker.order_history[0].slippage_usd == pytest.approx(abs(entry_price - 100))
    assert len(broker.trade_history) == 2
    assert [trade.quantity for trade in broker.trade_history] == pytest.approx(quantities)
    assert [trade.exit_price for trade in broker.trade_history] == pytest.approx(partial_prices)
    assert [trade.gross_price_pnl for trade in broker.trade_history] == pytest.approx(gross_pnls)
    assert [trade.exit_fee for trade in broker.trade_history] == pytest.approx(exit_fees)
    assert [trade.entry_fee for trade in broker.trade_history] == pytest.approx(
        [entry_fee * quantity for quantity in quantities])
    assert [trade.funding_cashflow for trade in broker.trade_history] == pytest.approx(partial_funding)
    assert [trade.net_pnl for trade in broker.trade_history] == pytest.approx([
        gross - entry_fee * quantity - fee + funding
        for gross, quantity, fee, funding in zip(gross_pnls, quantities, exit_fees, partial_funding)
    ])
    assert len(broker.funding_history) == 1
    event = broker.funding_history[0]
    assert event.timestamp == BASE + timedelta(hours=4)
    assert event.position_quantity == pytest.approx(settlement_quantity)
    assert event.settlement_mark_price == settlement_price
    assert event.cashflow_usd == pytest.approx(total_funding)
    position = broker.positions['BTCUSDT']
    assert position.quantity == pytest.approx(0.3)
    assert position.metadata['partials_done'] == 2
    assert position.stop_loss_price == pytest.approx(entry_price)
    assert position.initial_margin == pytest.approx(0.3 * entry_price / 2)
    assert position.entry_fee == pytest.approx(0.3 * entry_fee)
    assert position.cumulative_funding == pytest.approx(active_funding)
    assert position.isolated_collateral == pytest.approx(0.3 * entry_price / 2 + active_funding)
    assert broker.wallet_balance == pytest.approx(wallet)
    assert broker.unrealized_pnl == pytest.approx(unrealized)
    assert broker.equity == pytest.approx(wallet + unrealized)

    checkpoint, inputs, events = runner.capture(), runner.all_inputs(), runner.ledger_events()
    resumed = runner
    for _ in range(3):
        resumed = CausalRunner.restore(resumed.config, resumed.capture(), inputs, events)
        assert resumed.capture() == checkpoint
        assert resumed.broker.order_history == broker.order_history
        assert resumed.broker.trade_history == broker.trade_history
        assert resumed.broker.funding_history == broker.funding_history
        assert resumed.broker.positions == broker.positions
        assert resumed.trials.total_capital_injected == 10000

    for active in (runner, resumed):
        active.broker.request_close('BTCUSDT', active.broker.current_time)
        active.advance(batch(BASE + timedelta(hours=4, minutes=15), closing_price))
        assert not active.broker.positions
        assert not active.broker.pending_orders
        assert not active.broker.pending_closes
        assert len(active.broker.funding_history) == 1
        assert len(active.broker.trade_history) == 3
    final_price = closing_price * (1 - sign * SLIPPAGE)
    final_gross = sign * 0.3 * (final_price - entry_price)
    final_fee = 0.3 * final_price * FEE
    final_wallet = wallet + final_gross - final_fee
    assert runner.broker.equity == pytest.approx(final_wallet)
    assert runner.broker.wallet_balance == pytest.approx(final_wallet)
    assert runner.broker.reserved_collateral == 0
    assert sum(trade.quantity for trade in runner.broker.trade_history) == pytest.approx(1)
    assert sum(trade.entry_fee for trade in runner.broker.trade_history) == pytest.approx(entry_fee)
    assert sum(trade.funding_cashflow for trade in runner.broker.trade_history) == pytest.approx(total_funding)
    assert runner.capture() == resumed.capture()
    assert runner.broker.trade_history == resumed.broker.trade_history
    closed = CausalRunner.restore(runner.config, runner.capture(),
                                 runner.all_inputs(), runner.ledger_events())
    assert closed.capture() == runner.capture()
    assert closed.broker.equity == pytest.approx(final_wallet)
