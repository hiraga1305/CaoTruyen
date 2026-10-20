"""Read at most eight paragraph analyses per lookup, never ingest whole-book AST."""
import argparse
import json
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file',default='native_oauth/runs/chapter1/analysis.full.json')
    parser.add_argument('--ids',required=True,nargs='+')
    args=parser.parse_args()
    if not 1<=len(args.ids)<=8:
        parser.error('Request at most eight ids per lookup')
    source=Path(args.file).resolve()
    if not source.is_relative_to(Path.cwd().resolve()):
        parser.error('Analysis must remain in the current workspace')
    analysis=json.loads(source.read_text(encoding='utf-8'))
    rows=[s for s in analysis['segments'] if s['id'] in args.ids]
    if {s['id'] for s in rows}!=set(args.ids):
        parser.error('Unknown id')
    print(json.dumps({'provenance':analysis['provenance'],'segments':rows},ensure_ascii=False,separators=(',',':')))


if __name__=='__main__':
    main()
