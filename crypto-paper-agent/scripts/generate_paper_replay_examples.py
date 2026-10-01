"""Generate API examples from actual synthetic session/broker transitions, never performance evidence."""
import argparse
from datetime import timedelta
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from jsonschema import Draft202012Validator, FormatChecker
from src.execution.order_models import OrderRequest
from src.paper.replay_session import PaperReplaySession
from src.paper.public_stream import SYMBOLS
from test_local_paper_session import BASE
from test_paper_replay_recovery import RangeSource, stream_event


def generate():
    examples = {}
    with tempfile.TemporaryDirectory(prefix='paper-contract-qa-') as temporary:
        source = RangeSource()
        session = PaperReplaySession(source=source, journal_dir=Path(temporary) / 'account', clock=lambda: BASE)
        examples['empty_unallocated'] = session.state()
        session.start()
        session.broker.submit_order(OrderRequest(symbol='BTCUSDT', direction='SHORT', signal_time=BASE,
            signal_price=100, stop_loss_price=150, requested_quantity=1))
        session.checkpoint()
        session.clock = lambda: BASE + timedelta(minutes=15, seconds=2)
        source.now = int((BASE + timedelta(minutes=16)).timestamp() * 1000)
        session.on_connection(True, None)
        for symbol in SYMBOLS:
            session.on_stream_event(stream_event(symbol, BASE + timedelta(minutes=15), closed=False))
        assert session.status != 'RECOVERY_REQUIRED', session.error
        examples['normal_public_fixture'] = session.state()
        session.on_connection(False, 'synthetic fixture disconnect')
        examples['disconnected'] = session.state()
        session.pause()
        assert session.runner.intent == 'PAUSED', session.error
        examples['paused'] = session.state()
        session.shutdown()
        source.now = int((BASE + timedelta(hours=5, minutes=1)).timestamp() * 1000)
        restarted = PaperReplaySession(source=source, journal_dir=Path(temporary) / 'account', auto_resume=True,
                                       clock=lambda: BASE + timedelta(hours=5))
        examples['restart_replayed_paused'] = restarted.state()
        restarted.shutdown()
        blocked = Path(temporary) / 'broken'
        blocked.mkdir()
        (blocked / 'paper.sqlite3').write_bytes(b'fixture torn database')
        invalid = PaperReplaySession(source=source, journal_dir=blocked, auto_resume=True)
        examples['recovery_required'] = invalid.state()
        invalid.shutdown()
    return {'label': 'SYNTHETIC_API_EXAMPLES_NOT_MARKET_RESULTS', 'api_version': 3, 'examples': examples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    document = generate()
    schema = json.loads((ROOT / 'docs/operations/paper_replay_state_v3.schema.json').read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for state in document['examples'].values():
        validator.validate(state)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, allow_nan=False), encoding='utf-8')
    print(f'Validated {len(document["examples"])} backend-generated synthetic states')


if __name__ == '__main__':
    main()
