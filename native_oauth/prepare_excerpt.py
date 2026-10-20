"""Create an explicitly labelled subset from already fetched and parsed source."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from semantic_gate import read_json,write_json,digest


def main():
    sources=list((ROOT/'native_oauth/pilot_workspace/prepared_input_v2').glob('*.source.json'))
    source=read_json(sources[0])
    analysis=read_json(ROOT/'native_oauth/research/chapter1_ltp_analysis.json')
    if source['package_hash']!=analysis['source_package_hash']:
        raise ValueError('Different source')
    original_hash=source['package_hash']
    total=len(source['segments'])
    source['segments']=source['segments'][:40]
    source['scope']={'kind':'EXCERPT','paragraphs':[1,40],'full_chapter_paragraphs':total,
                     'full_source_package_hash':original_hash,'full_source_file':str(sources[0].resolve())}
    source['package_hash']=digest({k:v for k,v in source.items() if k!='package_hash'})
    analysis['segments']=analysis['segments'][:40]
    analysis['subset_from_package_hash']=original_hash
    analysis['source_package_hash']=source['package_hash']
    write_json(ROOT/'native_oauth/research/chapter1_excerpt40.source.json',source)
    write_json(ROOT/'native_oauth/research/chapter1_excerpt40.analysis.json',analysis)
    work=ROOT/'native_oauth/pilot_excerpt'
    (work/'.agents/agents').mkdir(parents=True,exist_ok=True)
    import shutil
    for p in (ROOT/'.agents/agents').glob('novel-*.md'):
        shutil.copy2(p,work/'.agents/agents'/p.name)


if __name__=='__main__':
    main()
