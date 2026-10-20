"""Fetch bounded original-source batches; never fabricate approved VN context."""
import argparse
import re
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from source_integrity import fetch_chapter_raw
from semantic_gate import read_json,write_json,flatten_lore,digest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--toc',default='toc_cache.json');parser.add_argument('--lore',default='novel_lore.json')
    parser.add_argument('--base-url',default='https://www.piaotia.com/html/16/16014/');parser.add_argument('--article-id',default='16014')
    parser.add_argument('--from-chapter',required=True,type=int);parser.add_argument('--to-chapter',required=True,type=int)
    parser.add_argument('--out',required=True)
    args=parser.parse_args();toc=read_json(args.toc)
    if not 1<=args.from_chapter<=args.to_chapter<=len(toc) or args.to_chapter-args.from_chapter>=20:
        parser.error('One crawl block must be1–20 valid consecutive chapters')
    for chapter in range(args.from_chapter,args.to_chapter+1):
        href,title=toc[chapter-1];paragraphs=fetch_chapter_raw(href,base_url=args.base_url,article_id=args.article_id)
        if re.sub(r'\s+','',paragraphs[0])!=re.sub(r'\s+','',title):raise ValueError('Source title mismatch')
        package={'version':'batch-original-source-1','chapter':chapter,'title':title,'source_ref':args.base_url+href,
                 'glossary':flatten_lore(read_json(args.lore)),
                 'segments':[{'id':f'c{chapter:04d}p{i:04d}','source':s} for i,s in enumerate(paragraphs,1)],
                 'scope':'Original-source prepass; not approved Vietnamese continuity'}
        package['package_hash']=digest(package);path=Path(args.out)/f'source_chapter_{chapter:04d}.json'
        write_json(path,package);print(path,flush=True)
