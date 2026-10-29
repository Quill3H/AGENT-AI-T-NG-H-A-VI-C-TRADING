#!/usr/bin/env python3
"""Fixed ETH/BTC cointegration v1; offline public-data paper replay only.

python scripts/run_eth_btc_cointegration.py --data-dir <parquet-folder> \
  --lot-metadata <source-identified-json> --output <NEW-folder>
"""
import argparse
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from src.research.cointegration import closed_four_hour, formation_diagnostics, replay

PERIODS={'2021-2023':('2021-01-01','2024-01-01'),
         '2024-2026':('2024-01-01','2026-10-01')}
SCENARIOS=[('actual',1.,0),('no_positive',1.,0),('actual',2.,0),('no_positive',2.,0),
           ('actual',1.,1),('no_positive',1.,1)]


def read_metadata(path):
    obj=json.loads(Path(path).read_text(encoding='utf-8'))
    if not obj.get('source_url') and not obj.get('source'):
        raise ValueError('lot metadata requires source identity')
    return obj


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_report(summaries,path):
    lines=['# Hồi cứu ETH–BTC cointegration v1',
           '', 'Giao dịch giấy; dữ liệu đã từng được dự án sử dụng. '
           'AUTHOR_REPORTED / REVIEWER_NOT_VERIFIED; chưa nghiệm thu hiệu quả kinh tế.', '',
           '| Giai đoạn | Funding | Chi phí | Chậm chân BTC | Lãi/lỗ % | Sụt vốn % | Cặp hoàn tất | Kết luận |',
           '|---|---|---|---|---:|---:|---:|---|']
    for label,s in summaries.items():
        lines.append(f"| {s['period']} | {s['funding_mode']} | {s['cost_multiplier']}x | "
                     f"{s['second_leg_delay']} nến | {s['total_return_pct']:.4f} | "
                     f"{s['max_drawdown_pct']:.4f} | {s['completed_pairs']} | {s['verdict']} |")
    lines+=['','## Quy tắc không kiếm lời từ funding','',
            'Tài khoản no_positive loại từng khoản funding được nhận nhưng vẫn trừ khoản phải trả; '
            'số dư, khối lượng, ký quỹ và bộ ngắt được chạy lại độc lập. '
            'Không lấy kết quả tài khoản thường rồi trừ một tổng funding sau cùng.','',
            'Nếu chỉ tài khoản actual có lãi thì không đạt quy tắc của chủ dự án. '
            'Kết quả dương vẫn chưa chứng minh lợi thế trên dữ liệu mới.','',
            '## Phạm vi và giới hạn','',
            '- Quan hệ giá được kiểm định lại hằng tuần bằng 90 ngày nến đã đóng; tham số khóa trong tuần.',
            '- Một tài khoản dùng chung vốn; một mã vòng đời cho hai chân. Tỷ lệ hedge sau làm tròn được ghi nhận.',
            '- Quy tắc lot hiện tại được áp dụng như một giả định lịch sử có nguồn, không phải bộ lọc lịch sử đã xác minh.',
            '- Quan sát và bảo vệ trên nến 15 phút không tái dựng được đường giá trong nến hoặc độ sâu sổ lệnh.',
            '- Funding dùng giá mở nến thanh toán thay cho chuỗi mark lịch sử; đây là xấp xỉ cần kiểm tra độ nhạy.',
            '- Tài khoản 1x trong mô hình; giá thanh lý và buffer vẫn được kiểm tra theo bộ rủi ro hiện có.',
            '- 30 cặp là ngưỡng tối thiểu để không gắn nhãn ít mẫu; không tương đương ý nghĩa thống kê.',
            '', 'Chi tiết từng năm, tiền do giá, phí, trượt giá, funding, lý do từ chối, '
            'thời gian giữ và tập trung lợi nhuận nằm trong summary.json và từng tệp scenario JSON.',
            '', 'Không đổi ngưỡng, đổi cặp hoặc tăng đòn bẩy sau khi xem kết quả.']
    Path(path).write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir',required=True)
    parser.add_argument('--lot-metadata',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--period',choices=['all',*PERIODS],default='all')
    parser.add_argument('--append-ledger',action='store_true',help='unsupported legacy option; new ledger runs require preregistration')
    args=parser.parse_args(argv)
    if args.append_ledger:
        print('ERROR [LEDGER_PREREGISTRATION_REQUIRED]: legacy retrospective append is unsupported; '
              'run without --append-ledger to export artifacts without changing the ledger',file=sys.stderr)
        return 2
    output=Path(args.output)
    if output.exists():
        print('ERROR [OUTPUT_EXISTS]',file=sys.stderr)
        return 2
    directory=Path(args.data_dir)
    required=[directory/f'{s}_perp_{tf}.parquet' for s in ['ETHUSDT','BTCUSDT'] for tf in ['15m','funding']]
    if any(not p.is_file() for p in required) or not Path(args.lot_metadata).is_file():
        print('ERROR [DATASET_UNAVAILABLE]: market data and identified lot metadata required',file=sys.stderr)
        return 2
    try:
        metadata=read_metadata(args.lot_metadata)
        config=yaml.safe_load((ROOT/'config/default_config.yaml').read_text(encoding='utf-8'))
        # The approved experiment caps defaults; it never opts into old 10% research overrides.
        config['account']['initial_equity_usd']=10000
        config.setdefault('fees',{}).update(taker_pct=.0005,maker_pct=.0002,slippage_pct=.0003)
        frames={s:pd.read_parquet(directory/f'{s}_perp_15m.parquet') for s in ['ETHUSDT','BTCUSDT']}
        funding={s:pd.read_parquet(directory/f'{s}_perp_funding.parquet') for s in frames}
        periods=PERIODS if args.period=='all' else {args.period:PERIODS[args.period]}
        # Preflight every period before creating output or publishing any metrics.
        from src.research.cointegration import validate_market
        from src.execution.pair_account import PairAccount
        PairAccount(config,metadata['symbols'],metadata.get('source_url') or metadata['source'])
        for first,last in periods.values():
            validate_market(frames,funding,pd.Timestamp(first,tz='UTC'),pd.Timestamp(last,tz='UTC'))
    except (ValueError,KeyError,OSError,TypeError) as error:
        print(f'ERROR [INVALID_DATASET]: {error}',file=sys.stderr)
        return 2
    output.mkdir(parents=True)
    manifest={'strategy':'eth_btc_cointegration_v1','evaluation_type':'SEEN_DATA_RETROSPECTIVE',
              'inputs':{p.name:sha(p) for p in required},'lot_metadata':metadata,
              'lot_metadata_sha256':sha(args.lot_metadata),'config':config,
              'versions':{p:version(p) for p in ['numpy','pandas','statsmodels','pyarrow']},
              'files':{},'complete':False}
    provenance=directory/'source_manifest.json'
    if provenance.is_file():
        manifest['source_manifest_sha256']=sha(provenance)
    try:
        manifest['base_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except (OSError,subprocess.CalledProcessError):
        manifest['base_commit']='NOT_AVAILABLE'
    for rel in ['src/strategies/eth_btc_cointegration.py','src/execution/pair_account.py',
                'src/research/cointegration.py','scripts/run_eth_btc_cointegration.py']:
        manifest['files'][rel]=sha(ROOT/rel)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    summaries={}
    signal=closed_four_hour(frames)
    try:
        for period,(first,last) in periods.items():
            start,end=pd.Timestamp(first,tz='UTC'),pd.Timestamp(last,tz='UTC')
            formations=formation_diagnostics(signal,start,end)
            for mode,cost,delay in SCENARIOS:
                label=f'{period}-{mode}-cost{int(cost)}-delay{delay}'
                result=replay(frames,funding,config,metadata['symbols'],start,end,
                              funding_mode=mode,cost_multiplier=cost,second_leg_delay=delay,
                              metadata_source=metadata.get('source_url') or metadata['source'],formations=formations)
                result['summary'].update(period=period,cost_multiplier=cost,second_leg_delay=delay)
                if abs(result['summary']['pnl_reconciliation_error_usd'])>1e-6:
                    raise RuntimeError('PNL_RECONCILIATION_FAILED')
                (output/f'{label}.json').write_text(json.dumps(result,indent=1,allow_nan=False),encoding='utf-8')
                summaries[label]=result['summary']
                print(json.dumps(dict(label=label,summary=result['summary'])),flush=True)
        (output/'summary.json').write_text(json.dumps(summaries,indent=2,allow_nan=False),encoding='utf-8')
        write_report(summaries,output/'bao-cao.md')
        manifest['complete']=True
        manifest['outputs']={p.name:sha(p) for p in output.iterdir() if p.name!='manifest.json'}
    except Exception as error:
        manifest['error']=f'{type(error).__name__}: {error}'
        raise
    finally:
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
