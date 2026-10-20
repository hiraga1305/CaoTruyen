"""Original-source index for bounded context retrieval; no translated facts."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from semantic_gate import read_json,write_json,digest
from native_oauth.batch_contract import _sources,build_story_state

RELATION_CUES=('母亲','父亲','妈妈','姐姐','妹妹','哥哥','弟弟','朋友','老师','学生','同学','拒绝','答应','名字','称呼','借款','贷款','转账','原身')


def extract_ledger(packages, analyses):
    index,_,_=_sources(packages)
    if len(packages)!=len(analyses):raise ValueError('Missing parser package')
    glossary={}
    for package in packages:
        for source,target in package.get('glossary',{}).items():
            if source in glossary and glossary[source]!=target:
                raise ValueError('Conflicting canonical term across source packages: '+source)
            glossary[source]=target
    predictions={}
    for package,analysis in zip(packages,analyses):
        if analysis['source_package_hash']!=package['package_hash']:
            raise ValueError('Parser source package mismatch')
        if [s['id'] for s in analysis['segments']]!=[s['id'] for s in package['segments']]:
            raise ValueError('Parser coverage mismatch')
        predictions.update({s['id']:s for s in analysis['segments']})
    ledger=[]
    for identifier,row in index.items():
        parsed=predictions[identifier]
        if parsed['source_hash']!=digest(row['source']):raise ValueError('Parser quote mismatch')
        keys=[k for k in glossary if k in row['source']]
        # NER is only a retrieval candidate. The quote remains the evidence.
        for entity in parsed.get('ner',[]):
            if len(entity)>1 and isinstance(entity[1],str) and entity[1] in row['source']:
                keys.append(entity[1])
        keys.extend(k for k in RELATION_CUES if k in row['source'])
        keys=sorted(set(keys))
        if keys:
            ledger.append({'ledger_id':identifier,'kind':'event','keys':keys,
                           'required':False,'references':[{'source_id':identifier,'source_quote':row['source']}],
                           'valid_from':identifier})
    return ledger


def parse_raw_packages(paths,out):
    """Research raw sources deliberately do not fabricate a prior PASS chain."""
    from native_oauth.parse_source import load_parser
    parser,provenance=load_parser()
    outputs=[]
    for path in paths:
        package=read_json(path);_sources([package]);records=[]
        for start in range(0,len(package['segments']),8):
            batch=package['segments'][start:start+8]
            if any(len(parser.tokenizer.encode(s['source'],truncation=False))>512 for s in batch):
                raise ValueError('Parser window exceeded; never silently truncate')
            result=parser.pipeline([s['source'] for s in batch],tasks=['cws','pos','ner','srl','dep','sdp'])
            for i,s in enumerate(batch):
                records.append({'id':s['id'],'source_hash':digest(s['source']),
                                'cws':result.cws[i],'pos':result.pos[i],
                                'idiom_candidates':[w for w,p in zip(result.cws[i],result.pos[i]) if p=='i'],
                                'ner':result.ner[i],'srl':result.srl[i],
                                'dep':result.dep[i],'sdp':result.sdp[i]})
        target=Path(out)/f"chapter_{package['chapter']:04d}.analysis.json"
        write_json(target,{'source_package_hash':package['package_hash'],'provenance':provenance,
                           'limits':'Predicted syntax, not coreference or story truth; raw-source research only',
                           'segments':records})
        outputs.append(str(target));print(str(target),flush=True)
    return outputs


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',action='append',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    parse_raw_packages(args.source,args.out)
