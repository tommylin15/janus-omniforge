"""Janus v3.8.2 ChatGPT-side research labeling, never downloads or mutates canonical.

Usage:
 python research/chatgpt/label_four_models.py --dataset-root /path/to/JanusDataset_v3_202610 --output-root /mnt/data/JanusResearch
 python research/chatgpt/label_four_models.py --dataset-root /path/to/JanusDataset_v3_202610 --output-root /mnt/data/JanusResearch --verify-only

Input must include canonical/CURRENT.json and the immutable referenced Parquet files.
This is research candidate X/Y, not strict historical PIT certification or deployment.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from janus_precision import export_dataset, load_release


def run(dataset_root: Path, output_root: Path, *, max_rows: int = 1500000, verify_only: bool = False):
    dataset_root = Path(dataset_root).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()
    canonical = (dataset_root / 'canonical').resolve()
    if output_root == dataset_root or output_root == canonical or canonical in output_root.parents:
        raise ValueError('OUTPUT_MUST_NOT_OVERWRITE_CANONICAL_OR_DATASET_ROOT')
    if max_rows < 1 or max_rows > 1500000:
        raise ValueError('ROW_LIMIT_OUT_OF_RANGE')
    if not (dataset_root / 'canonical' / 'CURRENT.json').is_file():
        raise FileNotFoundError('Dataset CURRENT.json 尚未在 ChatGPT 工作目錄就緒；不可假裝已可直接讀取 Drive')
    if verify_only:
        _, receipt = load_release(dataset_root, max_rows=max_rows)
        return {'state':'INPUT_VERIFIED_ONLY','input':receipt,'publication_allowed':False}
    out, manifest = export_dataset(dataset_root,max_rows=max_rows,output_root=output_root)
    return {'state':manifest['state'],'output':str(out),'input_release':manifest['input'].get('release'),
            'version':manifest['version'],'files':manifest['files'],'publication_allowed':False}


def main(argv=None):
    parser = argparse.ArgumentParser(description='Janus 四模型 ChatGPT 端研究貼標 / 因子工廠（不連網）')
    parser.add_argument('--dataset-root',type=Path,required=True,help='包含 canonical/CURRENT.json 的本地資料根')
    parser.add_argument('--output-root',type=Path,required=True,help='研究輸出根目錄，不可指向 canonical')
    parser.add_argument('--max-rows',type=int,default=1500000)
    parser.add_argument('--verify-only',action='store_true',help='驗來源、不可變分區 SHA/列數/鍵，不寫研究產物')
    args=parser.parse_args(argv)
    result=run(args.dataset_root,args.output_root,max_rows=args.max_rows,verify_only=args.verify_only)
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
