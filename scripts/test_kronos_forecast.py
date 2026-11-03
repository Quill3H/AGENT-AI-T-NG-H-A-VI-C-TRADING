import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('worker', Path(__file__).with_name('kronos_forecast.py'))
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

class InputTests(unittest.TestCase):
    def sample(self):
        raw = json.dumps(dict(frame='15m', venue='OKX', symbol='SOLUSDT', cycleAt=36000000,
            intervalMs=900000, firstOpenTime=0, columns=['open','high','low','close','volume'],
            rows=[[100,102,98,101,100]]*40))
        return dict(symbol='SOLUSDT', inputJson=raw, inputSha256=hashlib.sha256(raw.encode()).hexdigest())

    def test_valid_and_omitted_amount(self):
        self.assertEqual(len(worker.decode_input(self.sample())['rows']), 40)

    def test_tampered_hash(self):
        s=self.sample(); s['inputJson'] += ' '
        with self.assertRaises(ValueError): worker.decode_input(s)

    def test_invalid_geometry_nan_negative_gap(self):
        for key,value in [('rows',[[100,1,98,101,100]]*40),('rows',[[100,102,98,float('nan'),100]]*40),('rows',[[100,102,98,101,-1]]*40),('firstOpenTime',1),('intervalMs',1),('symbol','UNKNOWN')]:
            s=self.sample(); d=json.loads(s['inputJson']); d[key]=value
            s['inputJson']=json.dumps(d);s['inputSha256']=hashlib.sha256(s['inputJson'].encode()).hexdigest()
            with self.assertRaises(ValueError): worker.decode_input(s)

if __name__ == '__main__': unittest.main()
