"""Research labeling; historical industry audit is opt-in, never a default task."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from janus_precision import export_dataset, load_release
from industry_membership import check_industry_membership


def run(dataset_root: Path, output_root: Path, *, max_rows: int = 1500000,
        verify_only: bool = False, require_industry: bool = False):
    dataset_root = Path(dataset_root).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()
    if max_rows < 1 or max_rows > 1500000:
        raise ValueError('ROW_LIMIT_OUT_OF_RANGE')
    if output_root == dataset_root or dataset_root in output_root.parents:
        raise ValueError('OUTPUT_MUST_NOT_OVERWRITE_CANONICAL_OR_DATASET_ROOT')
    if not (dataset_root / 'canonical' / 'CURRENT.json').is_file():
        raise FileNotFoundError('Dataset CURRENT.json 尚未在 ChatGPT 工作目錄就緒；不可假裝已可直接讀取 Drive')

    def preflight(data):
        if not require_industry:
            return {'status': 'NOT_REQUESTED',
                    'reason': 'historical_industry_audit_retired_by_default',
                    'industry_features_in_model_x': False}
        result = check_industry_membership(dataset_root, data.get('ohlcv'))
        if require_industry and result['status'] != 'VERIFIED':
            raise ValueError('INDUSTRY_MEMBERSHIP_NOT_VERIFIED:' + result['reason'])
        return result

    if verify_only:
        data, receipt = load_release(dataset_root, max_rows=max_rows)
        return {'state':'INPUT_VERIFIED_ONLY', 'input':receipt,
                'industry_membership_precheck':preflight(data),
                'publication_allowed':False}
    out, manifest = export_dataset(dataset_root,max_rows=max_rows,
                                   output_root=output_root,industry_preflight_fn=preflight)
    return {'state':manifest['state'],'output':str(out),'input_release':manifest['input'].get('release'),
            'version':manifest['version'],'files':manifest['files'],
            'industry_membership_precheck':json.loads((out/'industry_membership_precheck.json').read_text()),
            'publication_allowed':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Janus 四模型 ChatGPT 端研究貼標（預設不跑產業歷史稽核，不連網）')
    parser.add_argument('--dataset-root',type=Path,required=True,help='包含 canonical/CURRENT.json 的本地資料根')
    parser.add_argument('--output-root',type=Path,required=True,help='獨立研究輸出根，不可位於 dataset-root')
    parser.add_argument('--max-rows',type=int,default=1500000)
    parser.add_argument('--verify-only',action='store_true',help='只讀研究輸入，不寫研究產物')
    parser.add_argument('--require-industry',action='store_true',help='明確要求時才執行歷史產業檢查（預設關閉）')
    args=parser.parse_args(argv)
    result=run(args.dataset_root,args.output_root,max_rows=args.max_rows,
               verify_only=args.verify_only,require_industry=args.require_industry)
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
