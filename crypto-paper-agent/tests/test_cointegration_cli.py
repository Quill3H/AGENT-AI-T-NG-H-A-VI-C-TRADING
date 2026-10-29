import importlib
import importlib.util
import json


def module():
    name='scripts.run_eth_btc_cointegration'
    assert importlib.util.find_spec(name), 'reproduction CLI is missing'
    return importlib.import_module(name)


def test_missing_data_is_not_reported_as_zero_profit(tmp_path):
    output=tmp_path/'output'
    code=module().main(['--data-dir',str(tmp_path/'missing'),'--lot-metadata',str(tmp_path/'lots.json'),
                        '--output',str(output)])
    assert code==2
    assert not output.exists()


def test_legacy_append_ledger_rejected_before_dataset_or_output_work(tmp_path, capsys):
    output=tmp_path/'output'
    code=module().main(['--data-dir',str(tmp_path/'missing'),'--lot-metadata',str(tmp_path/'lots.json'),
                        '--output',str(output),'--append-ledger'])
    assert code==2
    assert 'LEDGER_PREREGISTRATION_REQUIRED' in capsys.readouterr().err
    assert not output.exists()


def test_existing_output_never_overwritten(tmp_path):
    output=tmp_path/'output'
    output.mkdir()
    marker=output/'marker.txt'
    marker.write_text('preserve')
    assert module().main(['--data-dir',str(tmp_path),'--lot-metadata',str(tmp_path/'lots.json'),
                          '--output',str(output)])==2
    assert marker.read_text()=='preserve'


def test_metadata_without_source_cannot_silently_use_synthetic_limits(tmp_path):
    path=tmp_path/'lots.json'
    path.write_text(json.dumps({'symbols':{}}))
    try:
        module().read_metadata(path)
    except ValueError as error:
        assert 'source' in str(error)
    else:
        raise AssertionError('unidentified metadata was accepted')
