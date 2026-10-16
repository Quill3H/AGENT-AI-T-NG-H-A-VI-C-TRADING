import importlib.util
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]


def test_v3_schema_on_actual_synthetic_normal_disconnect_restart_and_recovery():
    spec = importlib.util.spec_from_file_location('contract_generator', ROOT / 'scripts/generate_paper_replay_examples.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    examples = module.generate()['examples']
    schema = json.loads((ROOT / 'docs/operations/paper_replay_state_v3.schema.json').read_text())
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    for state in examples.values():
        validator.validate(state)
    normal = examples['normal_public_fixture']
    assert len(normal['open_positions']) == 1
    assert normal['orders'][0]['status'] == 'FILLED'
    assert normal['account']['equity_usd'] != 10000
    assert examples['restart_replayed_paused']['session_id'] == normal['session_id']
    assert len(examples['restart_replayed_paused']['funding_events']) == 1
    assert examples['restart_replayed_paused']['operator_intent'] == 'PAUSED'
    assert examples['recovery_required']['account']['wallet_usd'] is None
    assert all(not p['valid'] and p['price'] is None for p in examples['disconnected']['current_prices'].values())
