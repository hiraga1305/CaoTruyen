"""Atomic batch publication with real native evidence and ordered ancestry."""
from pathlib import Path
from semantic_gate import digest, read_json
from native_oauth.workflow_io import atomic_json, atomic_text, file_lock
from native_oauth.resilient_gate import MODE, validate_batch_evidence
from native_oauth.chapter_integrity import validate_source, validate_source_archive, render_text


def manifest_path(book):return Path(book)/'approved/resilient_manifest.json'


def manifest(book):
    legacy=Path(book)/'approved/manifest.json'
    if legacy.exists() and read_json(legacy).get('chapters'):
        raise ValueError('Legacy approvals exist; do not mix legacy and resilient publication')
    path=manifest_path(book)
    value=read_json(path) if path.exists() else {'schema':MODE,'chapters':{},'batches':{}}
    if value.get('schema')!=MODE or not isinstance(value.get('chapters'),dict) or not isinstance(value.get('batches'),dict):
        raise ValueError('Invalid resilient publication manifest')
    return value


def prefix(value,start):
    numbers=sorted(map(int,value['chapters']))
    if numbers!=list(range(1,start)):raise ValueError('Publication must extend the continuous approved prefix')
    entry=value['chapters'].get(str(start-1))
    return {'through_chapter':start-1,'entry_hash':digest(entry) if entry else None}


def contained(book,name):
    book=Path(book).resolve();path=(book/name).resolve()
    if not path.is_relative_to(book):raise ValueError('Batch evidence escapes book')
    return path


def prefix_context(book,boundary):
    """Read verbatim rows from the committed predecessor, without recursive gates.

    Full ancestry is verified once by validate_manifest; each edge also binds
    its exact predecessor entry. This avoids exponential validation on long books.
    """
    through=boundary['through_chapter']
    if not through:return []
    value=manifest(book);entry=value['chapters'].get(str(through))
    if not entry or digest(entry)!=boundary['entry_hash']:raise ValueError('Approved prefix changed')
    record=value['batches'][entry['batch']];evidence=read_json(contained(book,record['evidence']))
    if digest(evidence)!=record['evidence_hash']:raise ValueError('Prefix evidence changed')
    item=next(r for r in evidence['package']['chapters'] if r['source_packet']['chapter']==through)
    candidate=read_json(item['candidate_file']);source=read_json(item['source_packet']['source_file'])
    validate_source(source);validate_source_archive(source)
    if digest(candidate)!=entry['candidate_hash'] or source['package_hash']!=entry['source_hash']:
        raise ValueError('Prefix source or candidate changed')
    aligned=read_json(contained(book,entry['aligned']))
    if digest(aligned)!=entry['aligned_hash']:raise ValueError('Prefix aligned text changed')
    return [{'id':r['id'],'source':r['source'],'target':t['text'],'chapter':through}
            for r,t in list(zip(source['segments'],candidate['segments']))[-8:]]


def verify_batch(book,record,value):
    evidence=read_json(contained(book,record['evidence']))
    if digest(evidence)!=record['evidence_hash']:raise ValueError('Batch evidence changed')
    report=validate_batch_evidence(evidence)
    if report['status']!='PASS':raise ValueError('Native batch review did not pass')
    batch=evidence['package'];chapters=[item['source_packet']['chapter'] for item in batch['chapters']]
    if batch['book_id']!=value.get('book_id'):raise ValueError('Batch belongs to a different publication book')
    if chapters!=record['chapters'] or chapters!=list(range(chapters[0],chapters[-1]+1)):
        raise ValueError('Batch ownership/order changed')
    previous=value['chapters'].get(str(chapters[0]-1))
    if batch['prefix']!={'through_chapter':chapters[0]-1,'entry_hash':digest(previous) if previous else None}:
        raise ValueError('Batch approved predecessor changed')
    for item in batch['chapters']:
        packet=item['source_packet'];source=read_json(packet['source_file'])
        validate_source(source);validate_source_archive(source)
        if (source['package_hash']!=packet['origin_source_hash'] or packet['segments']!=[
                {'id':r['id'],'source':r['source']} for r in source['segments']]):
            raise ValueError('Batch evidence does not own the complete source')
        entry=value['chapters'].get(str(source['chapter']))
        if (not entry or entry.get('source_hash')!=source['package_hash']
                or entry.get('candidate_hash')!=item['candidate_hash'] or entry.get('batch')!=str(chapters[0])):
            raise ValueError('Chapter manifest does not match final reviewed revision')
    return evidence


def validate_manifest(book,value=None):
    value=manifest(book) if value is None else value
    numbers=sorted(map(int,value['chapters']))
    if numbers!=list(range(1,len(numbers)+1)):raise ValueError('Batch manifest has a chapter gap')
    owned=[];verified={}
    for key,record in sorted(value['batches'].items(),key=lambda kv:int(kv[0])):
        if str(record['chapters'][0])!=key:raise ValueError('Wrong batch key')
        verified[key]=verify_batch(book,record,value);owned.extend(record['chapters'])
    if owned!=numbers:raise ValueError('Batch manifest ownership is incomplete or overlapping')
    return verified


def commit(book,evidence):
    book=Path(book).resolve();batch=evidence['package'];chapters=[r['source_packet']['chapter'] for r in batch['chapters']]
    if batch.get('approval_eligible') is not True:raise ValueError('Diagnostic evidence cannot publish')
    if validate_batch_evidence(evidence)['status']!='PASS':raise ValueError('Cannot approve failed batch')
    if chapters!=list(range(chapters[0],chapters[-1]+1)):raise ValueError('Nonconsecutive batch')
    with file_lock(book/'approved/manifest.lock'):
        old=book/'approved/manifest.json'
        if old.exists() and read_json(old).get('chapters'):raise ValueError('Use an isolated book; do not mix legacy and batch approval modes')
        value=manifest(book)
        if value.get('book_id',batch['book_id'])!=batch['book_id']:raise ValueError('Publication book identity changed')
        value['book_id']=batch['book_id']
        if prefix(value,chapters[0])!=batch['prefix']:raise ValueError('Approved prefix changed during batch review')
        target=book/'approved/batches'/digest(evidence)
        target.mkdir(parents=True,exist_ok=True)
        proof=target/'evidence.json'
        if proof.exists() and read_json(proof)!=evidence:raise ValueError('Immutable batch revision collision')
        atomic_json(proof,evidence)
        record={'chapters':chapters,'evidence':proof.relative_to(book).as_posix(),'evidence_hash':digest(evidence)}
        value['batches'][str(chapters[0])]=record
        for item in batch['chapters']:
            packet=item['source_packet'];source=read_json(packet['source_file']);candidate=read_json(item['candidate_file'])
            validate_source(source);validate_source_archive(source)
            if source['package_hash']!=packet['origin_source_hash']:raise ValueError('Source changed before batch commit')
            aligned={'chapter_num':source['chapter'],'status':'APPROVED','source_hash':source['package_hash'],
                'total_paragraphs':len(source['segments']),'translated_paragraphs':len(candidate['segments']),
                'title_vi':candidate.get('title_vi'),'review_evidence':str(proof),'approval_mode':MODE,
                'bilingual_alignment':[{'para_id':r['id'],'raw_zh':r['source'],'translated_vi':t['text']}
                    for r,t in zip(source['segments'],candidate['segments'])]}
            file=target/f"chapter_{source['chapter']:04d}.json";text=file.with_suffix('.txt')
            from native_oauth.book_publication import rendered_chapter
            rendered_chapter(source,aligned)
            atomic_json(file,aligned);atomic_text(text,render_text(aligned['bilingual_alignment']))
            value['chapters'][str(source['chapter'])]={'batch':str(chapters[0]),'source_hash':source['package_hash'],
                'candidate_hash':item['candidate_hash'],'aligned':file.relative_to(book).as_posix(),
                'aligned_hash':digest(aligned),'text_hash':digest(text.read_text(encoding='utf8'))}
        # Recheck after every file write, before the single manifest commit.
        verify_batch(book,record,value)
        atomic_json(manifest_path(book),value)
    return record


def read_approval(book,chapter,value=None,evidence=None):
    book=Path(book).resolve();value=manifest(book) if value is None else value
    entry=value['chapters'].get(str(chapter))
    if not entry:raise ValueError(f'Chapter {chapter} has no batch approval')
    record=value['batches'][entry['batch']]
    evidence=verify_batch(book,record,value) if evidence is None else evidence
    item=next(r for r in evidence['package']['chapters'] if r['source_packet']['chapter']==chapter)
    source=read_json(item['source_packet']['source_file']);candidate=read_json(item['candidate_file'])
    path=contained(book,entry['aligned']);aligned=read_json(path);text=path.with_suffix('.txt').read_text(encoding='utf8')
    expected=[{'para_id':r['id'],'raw_zh':r['source'],'translated_vi':t['text']}
              for r,t in zip(source['segments'],candidate['segments'])]
    if (digest(aligned)!=entry['aligned_hash'] or digest(text)!=entry['text_hash']
            or aligned['bilingual_alignment']!=expected or text!=render_text(expected)
            or aligned.get('title_vi')!=candidate.get('title_vi')):
        raise ValueError('Approved batch output changed')
    from native_oauth.book_publication import rendered_chapter
    return {'source':source,'aligned':aligned,'text':text,'evidence':evidence,
        'evidence_path':contained(book,record['evidence']),'path':path,'receipt':entry,
        'rendered':rendered_chapter(source,aligned),'approval_mode':MODE}


def progress(book,total):
    value=manifest(book);invalid=[];approved=[];words=paragraphs=0
    try:verified=validate_manifest(book,value)
    except Exception as error:
        return {'total_chapters':total,'approved_count':0,'approved_chapters':[],
            'invalid_approvals':[str(error)],'wave_review_errors':[str(error)],'export_ready':False}
    for ch in sorted(map(int,value['chapters'])):
        try:
            item=read_approval(book,ch,value,verified[value['chapters'][str(ch)]['batch']])
            approved.append(ch);paragraphs+=len(item['rendered']['paragraphs'])
            words+=sum(len(p.split()) for p in item['rendered']['paragraphs'])
        except Exception as error:invalid.append({'chapter':ch,'reason':str(error)})
    return {'total_chapters':total,'approved_chapters':approved,'approved_count':len(approved),
        'approved_percent':100*len(approved)/total,'invalid_approvals':invalid,'wave_review_errors':[],
        'approved_words':words,'approved_paragraphs':paragraphs,
        'export_ready':approved==list(range(1,total+1)) and not invalid}
