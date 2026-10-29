import hashlib
import importlib
import importlib.util
import io
import json
import zipfile

import pytest


def api():
    name='scripts.prepare_eth_btc_data'
    assert importlib.util.find_spec(name), 'checksummed data preparer is missing'
    return importlib.import_module(name)


def archive(tmp_path,tf='15m'):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        text='1601510400000,100,110,90,105,1,1601511299999,1,1,.5,.5,0\n'
        z.writestr('source.csv',text)
    raw=stream.getvalue()
    path=tmp_path/'source.zip'
    path.write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    path.with_suffix('.zip.CHECKSUM').write_text(digest+' source.zip')
    entry={'symbol':'ETHUSDT','timeframe':tf,'url':'https://data.binance.vision/source.zip',
           'sha256':digest,'status':'OK'}
    return path,entry


def test_checksum_mismatch_is_rejected(tmp_path):
    path,entry=archive(tmp_path)
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='CHECKSUM'):
        api().read_archive(tmp_path,entry)


def test_missing_source_is_not_a_short_dataset(tmp_path):
    path,entry=archive(tmp_path)
    entry['status']='MISSING'
    with pytest.raises(ValueError,match='SOURCE_UNAVAILABLE'):
        api().read_archive(tmp_path,entry)


def test_valid_source_rows_are_read_without_header(tmp_path):
    path,entry=archive(tmp_path)
    rows=api().read_archive(tmp_path,entry)
    assert len(rows)==1 and rows[0][1]=='100'


def test_network_requires_explicit_opt_in(tmp_path):
    output=tmp_path/'no'
    assert api().main(['--output',str(output)])==2
    assert not output.exists()
