"""Recover only genuinely absent legacy IDs into unreviewed proposals.

This never changes legacy text, source hashes or the approved manifest. Complete
chapter revision and two independent reviews remain mandatory for publication.
"""
import argparse
import json
import re
import uuid
import hashlib
from pathlib import Path
from semantic_gate import digest, read_json, write_json
from native_oauth.chapter_integrity import validate_source
from native_oauth.native_evidence import validate_provenance
from native_oauth.pipeline_native import run_stage
from native_oauth.workflow_io import atomic_json, file_lock
from native_oauth.semantic_context import normalize_profile


ROOT = Path(__file__).resolve().parents[1]


def recovery_findings(source_hash, owned, result, model):
    if result.get('source_hash') != source_hash or result.get('model') != 'native/'+model:
        return [{'kind':'source_or_model_mismatch'}]
    rows=result.get('segments',[])
    if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):
        return [{'kind':'invalid_segments'}]
    if [r.get('id') for r in rows] != [r['id'] for r in owned]:
        return [{'kind':'coverage_or_order','expected':[r['id'] for r in owned]}]
    issues=[]
    for row in rows:
        text=row.get('text')
        if not isinstance(text,str) or not text.strip():
            issues.append({'id':row['id'],'kind':'empty_translation'})
        elif re.search(r'[\u3400-\u9fff\ufffd]',text):
            issues.append({'id':row['id'],'kind':'residual_chinese_or_replacement'})
    return issues


def missing_segments(source, legacy, chapter=None):
    validate_source(source)
    rows=legacy.get('bilingual_alignment',[])
    mapped={row['para_id']:row for row in rows}
    expected={row['id']:row for row in source['segments']}
    if len(mapped)!=len(rows) or any(sid not in expected for sid in mapped):
        raise ValueError('Legacy duplicate/foreign IDs require explicit source mapping')
    if any(row.get('raw_zh')!=expected[sid]['source'] for sid,row in mapped.items()):
        raise ValueError('Legacy source mismatch; never rewrite hashes to pass')
    truncation_file = ROOT / 'audit/legacy_exports_20261024/truncations.json'
    ch_num = chapter if chapter is not None else source.get('chapter')
    truncated_ids = set()
    if truncation_file.exists():
        for item in read_json(truncation_file):
            if ch_num is None or item.get('chapter') == ch_num:
                truncated_ids.add(item.get('source_id'))
    return [row for row in source['segments']
            if row['id'] in truncated_ids or not mapped.get(row['id'],{}).get('translated_vi','').strip()]


def recover_chapter(book,job,chapter,model='gemini-3.8-flash-medium',timeout=360):
    book,job=Path(book).resolve(),Path(job).resolve()
    with file_lock(job/f'recover_{chapter:04d}.lock',timeout=1):
        source=read_json(job/'baseline/sources'/f'source_chapter_{chapter:04d}.json')
        if source!=read_json(book/'sources'/f'source_chapter_{chapter:04d}.json'):
            raise ValueError('Source changed from the campaign baseline')
        legacy=read_json(job/'baseline/output_dich'/f'chuong_{chapter:04d}.dich.json')
        snapshot=read_json(job/'baseline_manifest.json')
        for relative in (f'sources/source_chapter_{chapter:04d}.json',f'output_dich/chuong_{chapter:04d}.dich.json'):
            if hashlib.sha256((job/'baseline'/relative).read_bytes()).hexdigest()!=snapshot[relative]['sha256']:
                raise ValueError('Recovery baseline was modified')
        missing=missing_segments(source,legacy,chapter)
        lore=read_json(book/'lore.json') if (book/'lore.json').exists() else {}
        _,_,terms=normalize_profile(source['book_id'],[],[],lore)
        recovered=[];proofs=[]
        truncation_file = ROOT / 'audit/legacy_exports_20261024/truncations.json'
        truncated_ids = {item['source_id'] for item in read_json(truncation_file)} if truncation_file.exists() else set()
        groups=[];current=[];size=0
        for row in missing:
            if len(row['source'])>3200:raise ValueError('Overlong paragraph needs an explicit source split')
            adjacent = not current or next(i for i,s in enumerate(source['segments']) if s['id']==row['id']) == next(i for i,s in enumerate(source['segments']) if s['id']==current[-1]['id'])+1
            max_chunk_len = 21 if (current and current[0]['id'] in truncated_ids) else 20
            if current and (not adjacent or len(current)>=max_chunk_len or size+len(row['source'])>3200):
                groups.append(current);current=[];size=0
            current.append(row);size+=len(row['source'])
        if current:groups.append(current)
        for index,owned in enumerate(groups,1):
            cached=job/'recovery_chunks'/f'chapter_{chapter:04d}_chunk_{index:03d}.json'
            result=None
            if cached.exists():
                candidate_cached=read_json(cached)
                if not recovery_findings(source['package_hash'],owned,candidate_cached,model):
                    validate_provenance(candidate_cached)
                    result=candidate_cached
            if result is None:
                workspace=job/'recovery_sessions'/f'chapter_{chapter:04d}'/(f'chunk_{index}_'+uuid.uuid4().hex)
                data=workspace/'native_oauth/runs/chapter1';data.mkdir(parents=True)
                first=next(i for i,row in enumerate(source['segments']) if row['id']==owned[0]['id'])
                last=next(i for i,row in enumerate(source['segments']) if row['id']==owned[-1]['id'])
                packet={'chapter':chapter,'book_id':source['book_id'],'book_title':lore.get('book_title_vi',book.name),
                        'total_chapters':len(read_json(book/'toc.json')) if (book/'toc.json').exists() else chapter,
                        'genre':lore.get('genre','SOURCE_CONTEXT'),'source_hash':source['package_hash'],
                        'editorial_names':{key:value[0] for key,value in terms.items() if value[1]=='character_name'},
                        'segments':owned,'source_before_read_only':source['segments'][max(0,first-4):first],
                        'source_after_read_only':source['segments'][last+1:last+5]}
                write_json(data/'source.json',packet)
                system=(Path(__file__).parent/'prompts/bns_system_cache_v1.md').read_text(encoding='utf-8').split('## Đầu ra')[0]
                prompt=system+'\nTranslate exactly the owned source IDs into complete Vietnamese paragraphs. '
                prompt+='Do not translate context rows or guess new facts. Return JSON {source_hash,segments:[{id,text}]}; no § markers. '
                prompt+='This is recovery of a draft, never semantic approval.\n'+json.dumps(packet,ensure_ascii=False)
                prompt+='\nReturn Vietnamese with Latin-script names/handles, transliterating Chinese handles consistently. Preserve every donor, number and author note; never discard a difficult row. No remaining Chinese characters.'
                for attempt in range(2):
                    if attempt:
                        workspace=job/'recovery_sessions'/f'chapter_{chapter:04d}'/(f'chunk_{index}_repair_'+uuid.uuid4().hex)
                        data=workspace/'native_oauth/runs/chapter1';data.mkdir(parents=True)
                        write_json(data/'source.json',packet)
                    result=run_stage(data,workspace,'translator',model,prompt,'recovery.json',timeout)
                    issues=recovery_findings(source['package_hash'],owned,result,model)
                    if not issues:
                        break
                    write_json(workspace/'qa.json',{'status':'BLOCKED','findings':issues})
                    prompt+='\nMECHANICAL_FAILURE_TO_FIX_AGAINST_SOURCE:\n'+json.dumps(issues,ensure_ascii=False)
            issues=recovery_findings(source['package_hash'],owned,result,model)
            if issues:
                raise ValueError('Recovery response incomplete/mismatched; no proposal committed: '+json.dumps(issues))
            rows=result['segments']
            atomic_json(cached,result)
            recovered.extend(rows);proofs.append(result)
        output={'status':'RECOVERY_PROPOSAL_UNREVIEWED','chapter':chapter,'source_hash':source['package_hash'],
                'missing_before':len(missing),'segments':recovered,'native_results':proofs,
                'rule':'Only comparison material for full-chapter revision; no publication approval'}
        if source!=read_json(book/'sources'/f'source_chapter_{chapter:04d}.json'):
            raise ValueError('Source changed while recovering')
        target=job/'recovery_proposals'/f'chapter_{chapter:04d}.json'
        atomic_json(target,output)
        return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book-dir',required=True,type=Path)
    parser.add_argument('--job',required=True,type=Path)
    parser.add_argument('--chapters',nargs='+',required=True,type=int)
    parser.add_argument('--model',default='gemini-3.8-flash-medium')
    args=parser.parse_args()
    for chapter in args.chapters:
        result=recover_chapter(args.book_dir,args.job,chapter,args.model)
        print(json.dumps({'chapter':chapter,'recovered':len(result['segments']),'status':result['status']}),flush=True)


if __name__=='__main__':
    main()
