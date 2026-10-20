"""Prepare one public Piaotia source for any configured book and genre."""
import argparse
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from source_integrity import fetch_chapter_raw
from semantic_gate import build_package,read_json,write_json,flatten_lore


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--article-id',required=True)
    parser.add_argument('--href',required=True)
    parser.add_argument('--chapter',required=True,type=int)
    parser.add_argument('--title',required=True)
    parser.add_argument('--genre',required=True,choices=['tien_hiep','hien_dai','hybrid_cyberpunk_tu_tien'])
    parser.add_argument('--lore',required=True,help='A separate glossary for the requested book')
    parser.add_argument('--context')
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    if args.chapter>1 and not args.context:
        parser.error('Later chapters require approved continuity evidence')
    paragraphs=fetch_chapter_raw(args.href,base_url=args.base_url,article_id=args.article_id)
    if re.sub(r'\s+','',paragraphs[0])!=re.sub(r'\s+','',args.title):
        raise ValueError('Source title mismatch')
    package=build_package(args.chapter,args.title,paragraphs,flatten_lore(read_json(args.lore)),
                          args.base_url+args.href,read_json(args.context) if args.context else None)
    package['declared_genre']=args.genre
    from semantic_gate import digest
    package['package_hash']=digest({k:v for k,v in package.items() if k!='package_hash'})
    write_json(args.out,package)
    print(args.out)


if __name__=='__main__':
    main()
