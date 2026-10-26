"""Versioned batch evidence. No projected/fabricated per-chapter model reviews."""
from pathlib import Path
from semantic_gate import digest, read_json, mechanical_findings, CHECKS, LITERARY_CHECKS
from native_oauth.native_evidence import validate_provenance, validate_bound_files
from native_oauth.recovery_native import ProtocolFailure, ContentFailure
from native_oauth.resilient_policy import POLICY,REVIEW_POLICY,policy_v2,content_findings,review_hints,quote_claims

BATCH_VERSION='antigravity-resilient-batch-1'
MODE='antigravity-resilient-publication-1'


def native_json_sessions(value):
    if value.get('identity_basis')!='native_cli_init' or value.get('native_response_binding')!='json':
        raise ValueError('New batch protocol requires the exact native JSON response, not a host-authored artifact')
    return validate_provenance(value)


def freeze(value):
    value={k:v for k,v in value.items() if k!='package_hash'}
    return {**value,'package_hash':digest(value)}


def check_hash(value):
    if value.get('package_hash')!=digest({k:v for k,v in value.items() if k!='package_hash'}):
        raise ValueError('Source changed: invalid immutable package hash')
    validate_bound_files(value)
    if value.get('version')=='resilient-source-draft-1':
        from native_oauth.chapter_integrity import validate_source,validate_source_archive
        source=read_json(value['source_file']);validate_source(source);validate_source_archive(source)
        from native_oauth.resilient_continuity import validate_contract
        validate_contract(value,source)
        if read_json(value['source_input_file'])!=source:raise ValueError('Source changed after its immutable snapshot')
        if any(value.get(key)!=source.get(key) for key in ('book_id','chapter','source_ref','title')):
            raise ValueError('Source book/chapter identity differs from the packet')
        full={r['id']:r['source'] for r in source['segments']}
        if value['origin_source_hash']!=source['package_hash'] or any(full.get(r['id'])!=r['source'] for r in value['segments']):
            raise ValueError('Source changed: packet does not own literal source')
        if 'parent_package_hash' not in value and value['segments']!=[{'id':r['id'],'source':r['source']} for r in source['segments']]:
            raise ValueError('Source packet dropped or reordered source paragraphs')
        if 'parent_package_hash' not in value:
            from native_oauth.book_publication import title_ids
            if not title_ids(source):
                from native_oauth.title_selection import metadata_title_source
                if value.get('metadata_title_source')!=metadata_title_source(source):
                    raise ValueError('Metadata title is not owned by the archived source')
        verified_context={}
        for row in value.get('earlier_original_read_only',[]):
            context_key=(row['source_file'],row['source_input_file'])
            if context_key not in verified_context:
                prior=read_json(row['source_file']);validate_source(prior);validate_source_archive(prior)
                if read_json(row['source_input_file'])!=prior:raise ValueError('Source context changed after its immutable snapshot')
                verified_context[context_key]=(prior,{r['id']:r['source'] for r in prior['segments']})
            prior,by_id=verified_context[context_key]
            if (row['chapter']>=source['chapter'] or prior['chapter']!=row['chapter'] or prior['book_id']!=source['book_id'] or prior['package_hash']!=row['source_hash']
                    or by_id.get(row['id'])!=row['source']):
                raise ValueError('Source context includes future or ungrounded facts')


def response_shape(package,value):
    if not isinstance(value,dict) or value.get('package_hash')!=package['package_hash']:
        raise ProtocolFailure('Return the supplied package_hash, not an inferred hash')
    rows=value.get('segments')
    if (not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows)
            or [r.get('id') for r in rows]!=[r['id'] for r in package['segments']]):
        raise ProtocolFailure('Return every assigned source ID exactly in order; never renumber')


def validate_translation(package,value):
    response_shape(package,value)
    findings=content_findings(package,value)
    if findings:
        bad={r.get('id') for r in findings}
        texts=[r for r in value['segments'] if r['id'] in bad]
        raise ContentFailure('Correct these source-owned defects; do not strip arbitrary letters: '+str(findings)+' CURRENT_BAD_ROWS='+str(texts),findings=findings)


def fragment(package,ids,with_title=False):
    own=set(ids)
    if len(own)!=len(ids) or not own.issubset(r['id'] for r in package['segments']):
        raise ValueError('Invalid fragment ownership')
    result={**package,'parent_package_hash':package['package_hash'],
            'segments':[r for r in package['segments'] if r['id'] in own]}
    positions=[i for i,r in enumerate(package['segments']) if r['id'] in own]
    result['neighbor_source_read_only']=[r for r in package['segments'][max(0,min(positions)-8):max(positions)+9] if r['id'] not in own]
    if not with_title:result.pop('metadata_title_source',None)
    return freeze(result)


def component(package,value,proof,ids=None,title=False):
    return {**proof,'ids':ids if ids is not None else [r['id'] for r in package['segments']],
            'owns_title':title}


def assemble(package,components):
    check_hash(package);targets={};title=None;sessions=set();script_quotes=[]
    full={r['id']:r['source'] for r in package['segments']}
    for part in components:
        packet=read_json(part['package_file']);value=read_json(part['file'])
        check_hash(packet)
        if digest(value)!=part['hash'] or packet.get('parent_package_hash')!=package['package_hash']:
            raise ValueError('Native artifact changed or fragment belongs to another source/canon/context')
        # Only assigned source rows and optional title ownership may differ.
        ignored={'package_hash','parent_package_hash','segments','metadata_title_source','neighbor_source_read_only'}
        if {k:v for k,v in packet.items() if k not in ignored}!={k:v for k,v in package.items() if k not in ignored}:
            raise ValueError('Fragment source/context differs from immutable parent')
        if any(full.get(r['id'])!=r['source'] for r in packet['segments']):
            raise ValueError('Fragment modified its original source')
        if any(full.get(r['id'])!=r['source'] for r in packet.get('neighbor_source_read_only',[])):
            raise ValueError('Fragment inserted invented neighbor context')
        response_shape(packet,value);sessions.update(native_json_sessions(value))
        policy=package.get('model_policy',{})
        if policy and value.get('model') not in {'native/'+policy['translator'],'native/'+policy['fallback']}:
            raise ValueError('Native translation model differs from the frozen policy')
        rows={r['id']:r['text'] for r in value['segments']}
        if ((not part['ids'] and not part['owns_title']) or len(set(part['ids']))!=len(part['ids']) or not set(part['ids']).issubset(rows)):
            raise ValueError('Invalid selected native ownership')
        for sid in part['ids']:
            if sid in targets:raise ValueError('Overlapping native paragraph ownership')
            targets[sid]=rows[sid]
        if policy_v2(package):
            owned=set(part['ids'])
            if part['owns_title']:owned.add(package['metadata_title_source']['id'])
            script_quotes += [claim for claim in quote_claims(packet,value) if claim['id'] in owned]
        if part['owns_title']:
            if title is not None or packet.get('metadata_title_source')!=package.get('metadata_title_source'):
                raise ValueError('Ambiguous native title ownership')
            title=value.get('title_vi')
    if set(targets)!=set(full):raise ValueError('Missing native paragraph ownership')
    result={'version':'resilient-composite-candidate-1','package_hash':package['package_hash'],
            'segments':[{'id':r['id'],'text':targets[r['id']]} for r in package['segments']],
            'components':components}
    if package.get('metadata_title_source'):result['title_vi']=title
    if script_quotes:result['source_script_quotes']=script_quotes
    validate_translation(package,result)
    return result,sessions


def replay_candidate(package,candidate):
    actual,sessions=assemble(package,candidate['components'])
    if actual!=candidate:raise ValueError('Candidate differs from exact native component output')
    return sessions


def batch_package(chapters,prefix,canon,book,approved_context=None,approval_eligible=True):
    if not chapters:raise ValueError('Empty batch')
    first_packet=chapters[0]['source_packet']
    if any(item['source_packet']['book_id']!=first_packet['book_id'] or item['source_packet']['canon']!=canon
           or item['source_packet'].get('model_policy')!=first_packet.get('model_policy')
           or item['source_packet'].get('continuity_contract',{}).get('version')!=first_packet.get('continuity_contract',{}).get('version')
           or item['source_packet'].get('validation_policy')!=first_packet.get('validation_policy') for item in chapters):
        raise ValueError('A batch cannot mix books, canon or model policies')
    numbers=[r['source_packet']['chapter'] for r in chapters]
    if numbers!=sorted(set(numbers)):raise ValueError('Batch chapter order is not unique and increasing')
    if approval_eligible and (numbers!=list(range(numbers[0],numbers[-1]+1)) or prefix['through_chapter']!=numbers[0]-1):
        raise ValueError('Approval requires consecutive chapters and their real predecessor boundary')
    if approved_context is None:
        from native_oauth.resilient_publication import prefix_context
        approved_context=prefix_context(book,prefix)
    catalog=[]
    for item in chapters:
        package,candidate=item['source_packet'],read_json(item['candidate_file'])
        if digest(candidate)!=item['candidate_hash']:raise ValueError('Candidate changed before review')
        replay_candidate(package,candidate)
        hints=review_hints(package,candidate)
        pairs=[]
        if package.get('metadata_title_source'):
            pairs.append((package['metadata_title_source']['id'],package['metadata_title_source']['source'],candidate['title_vi']))
        pairs += [(r['id'],r['source'],t['text']) for r,t in zip(package['segments'],candidate['segments'])]
        for sid,source,target in pairs:
            row={'slot':len(catalog)+1,'chapter':package['chapter'],'id':sid,'source':source,'target':target}
            if hints.get(sid):row['review_obligations']=hints[sid]
            title_source=package.get('metadata_title_source',{})
            if sid==title_source.get('id') and title_source.get('numbering_note'):
                row['title_numbering']={k:title_source[k] for k in ('catalog_chapter','declared_chapter','numbering_note')}
            catalog.append(row)
    first=chapters[0]['source_packet']
    owned={r['id'] for r in catalog};context=[];cues=[]
    for item in chapters:
        source_packet=item['source_packet']
        context += [{'for_chapter':source_packet['chapter'],**row} for row in source_packet.get('earlier_original_read_only',[]) if row['id'] not in owned]
        cues += [{k:cue[k] for k in ('source_id','kind','source_quote','review_instruction')}
                 for cue in source_packet.get('semantic_guidance',{}).get('source_anchors',[])]
    return freeze({'version':BATCH_VERSION,**({'review_policy':REVIEW_POLICY} if policy_v2(first) else {}),
        **({'continuity_policy':first['continuity_contract']['version']} if first.get('continuity_contract') else {}),
        'chapter':first['chapter'],'book_id':first['book_id'],
        'book_title':first['book_title'],'genre':first['genre'],'total_chapters':first['total_chapters'],
        'chapter_range':f"{first['chapter']}–{chapters[-1]['source_packet']['chapter']}",
        'book':str(Path(book).resolve()),'prefix':prefix,'canon':canon,'chapters':chapters,'catalog':catalog,'approved_context':approved_context,
        'source_context':context,'source_risk_cues':cues,'approval_eligible':approval_eligible,
        'session_monitor_state_file':first.get('session_monitor_state_file')})


def review_packet(batch,scope):
    return freeze({**batch,'parent_package_hash':batch['package_hash'],'scope_slots':list(scope)})


def validate_compact_review(packet,value):
    """A slot references its complete source and target, without model retyping."""
    if not isinstance(value,dict) or value.get('package_hash')!=packet['package_hash']:raise ProtocolFailure('Wrong review package_hash')
    v2=packet.get('review_policy')==REVIEW_POLICY
    if packet.get('review_policy') not in (None,REVIEW_POLICY):raise ProtocolFailure('Unsupported review policy')
    scope=packet['scope_slots'];rows=value.get('rows')
    if (not isinstance(rows,list) or any(not isinstance(r,list) or len(r)!=2 or type(r[0]) is not int or r[1] not in ('PASS','FAIL') for r in rows)
            or [r[0] for r in rows]!=scope):
        raise ProtocolFailure('rows must cover every selected integer slot exactly once in the supplied order')
    for field,dimensions in (('checks',CHECKS),('literary_checks',LITERARY_CHECKS)):
        checks=value.get(field)
        if not isinstance(checks,dict) or set(checks)!=set(dimensions) or any(v is not True for v in checks.values()):
            raise ProtocolFailure('Every required dimension must be marked inspected; failures go in issues')
    issues=value.get('issues');verdict=value.get('verdict')
    if not isinstance(issues,list) or verdict not in ('PASS','FAIL'):raise ProtocolFailure('Missing verdict/issues')
    failed={r[0] for r in rows if r[1]=='FAIL'}
    issue_slots=set()
    for issue in issues:
        if (not isinstance(issue,dict) or type(issue.get('slot')) is not int or issue['slot'] not in failed
                or type(issue.get('source_ref')) is not int or issue['source_ref']!=0
                or type(issue.get('target_ref')) is not int or issue['target_ref']!=0
                or not isinstance(issue.get('reason'),str) or not issue['reason'].strip()
                or issue.get('kind') not in ('meaning','completeness','entities','speaker_pronouns','numbers_units',
                    'negation_modality','time_causality','continuity','style','title','needs_context')):
            raise ProtocolFailure('FAIL needs an owned slot, source_ref:0,target_ref:0,kind and reason')
        issue_slots.add(issue['slot'])
        query=issue.get('context_query')
        if v2 and issue['kind']=='needs_context' and query is None:
            raise ProtocolFailure('needs_context must supply a grounded context_query, not an unactionable FAIL')
        query_sources=[packet['catalog'][issue['slot']-1]['source']]
        if v2:
            chapter=packet['catalog'][issue['slot']-1].get('chapter')
            query_sources += [row['source'] for row in packet['catalog'][:issue['slot']]]
            query_sources += [row['source'] for row in packet.get('source_context',[]) if chapter is not None
                and row.get('chapter',chapter)<chapter and row.get('for_chapter',chapter)==chapter]
            query_sources += [row['source'] for row in packet.get('approved_context',[])]
        if query is not None and (not isinstance(query,str) or not query.strip() or len(query)>24
                or not any(query in text for text in query_sources)):
            raise ProtocolFailure('context_query must be a short exact name/term in the failed or earlier source context')
    if issue_slots!=failed or (verdict=='PASS')!=(not bool(failed)):
        raise ProtocolFailure('Contradictory verdict, coverage or failure evidence')
    if v2:
        required=[slot for slot in scope if packet['catalog'][slot-1].get('review_obligations')]
        checked=value.get('semantic_obligations_checked')
        if (not isinstance(checked,list) or any(type(slot) is not int for slot in checked) or checked!=required):
            raise ProtocolFailure('semantic_obligations_checked must cover every flagged assigned slot exactly in order')
        suggestions=value.get('suggestions',[])
        if not isinstance(suggestions,list):raise ProtocolFailure('suggestions must be an array')
        for suggestion in suggestions:
            if (not isinstance(suggestion,dict) or type(suggestion.get('slot')) is not int or suggestion['slot'] not in scope
                    or suggestion.get('kind')!='style' or type(suggestion.get('source_ref')) is not int or suggestion['source_ref']!=0
                    or type(suggestion.get('target_ref')) is not int or suggestion['target_ref']!=0
                    or not isinstance(suggestion.get('reason'),str) or not suggestion['reason'].strip()):
                raise ProtocolFailure('Optional style suggestions require owned slots and exact paragraph refs; meaning errors belong in issues')
    from native_oauth.resilient_continuity import validate_review
    validate_review(packet,value)


def validate_batch_evidence(evidence):
    batch=evidence['package'];check_hash(batch)
    if batch.get('version')!=BATCH_VERSION:raise ValueError('Unsupported batch evidence')
    if type(batch.get('approval_eligible')) is not bool:raise ValueError('Missing explicit batch approval scope')
    translator_sessions=set()
    for item in batch['chapters']:
        candidate=read_json(item['candidate_file'])
        if digest(candidate)!=item['candidate_hash']:raise ValueError('Batch candidate changed after review')
        translator_sessions.update(replay_candidate(item['source_packet'],candidate))
    rebuilt=batch_package(batch['chapters'],batch['prefix'],batch['canon'],batch['book'],batch['approved_context'],batch['approval_eligible'])
    if rebuilt!=batch:raise ValueError('Batch source/target catalog changed')
    from native_oauth.resilient_publication import prefix_context
    if prefix_context(batch['book'],batch['prefix'])!=batch['approved_context']:
        raise ValueError('Batch did not use the real approved predecessor context')
    roles=evidence.get('reviews',[])
    if len(roles)!=2 or [r.get('role') for r in roles]!=['meaning-reviewer','literary-reviewer']:
        raise ValueError('Two independent native batch reviewers required')
    expected=list(range(1,len(batch['catalog'])+1));previous=set();findings=[];suggestions=[];decisions=[]
    for role in roles:
        covered=[];role_sessions=set()
        for part in role['parts']:
            packet=read_json(part['package_file']);value=read_json(part['file'])
            check_hash(packet)
            if (packet.get('parent_package_hash')!=batch['package_hash'] or digest(value)!=part['hash']
                    or {k:v for k,v in packet.items() if k not in ('package_hash','parent_package_hash','scope_slots')}
                       !={k:v for k,v in batch.items() if k!='package_hash'}):
                raise ValueError('Batch review belongs to different source/revision/context')
            validate_compact_review(packet,value)
            if batch.get('continuity_policy'):
                for decision in value['continuity_decisions']:
                    row=batch['catalog'][decision['slot']-1]
                    decisions.append({'chapter':row['chapter'],'id':row['id'],'reviewer':role['role'],**decision})
            sessions=set(native_json_sessions(value))
            policy=batch['chapters'][0]['source_packet'].get('model_policy',{})
            configured=policy.get('reviewer') if role['role']=='meaning-reviewer' else policy.get('reviewer2',policy.get('reviewer'))
            if policy and value.get('model') not in {'native/'+configured,'native/'+policy['fallback']}:
                raise ValueError('Native reviewer model differs from frozen policy')
            if role_sessions.intersection(sessions):raise ValueError('Review parts reused a native session')
            role_sessions.update(sessions);covered.extend(packet['scope_slots'])
            for issue in value['issues']:
                row=batch['catalog'][issue['slot']-1]
                findings.append({'chapter':row['chapter'],'id':row['id'],'kind':issue['kind'],
                    'source_quote':row['source'],'target_quote':row['target'],'reason':issue['reason'],
                    'reviewer':role['role'],**({'context_query':issue['context_query']} if issue.get('context_query') else {})})
            if batch.get('review_policy')==REVIEW_POLICY:
                for suggestion in value.get('suggestions',[]):
                    row=batch['catalog'][suggestion['slot']-1]
                    suggestions.append({'chapter':row['chapter'],'id':row['id'],'kind':'style',
                        'source_quote':row['source'],'target_quote':row['target'],'reason':suggestion['reason'],'reviewer':role['role']})
        if covered!=expected:raise ValueError('Batch reviewer skipped, duplicated or reordered assigned source')
        if previous.intersection(role_sessions) or translator_sessions.intersection(role_sessions):
            raise ValueError('Native batch reviewers and translators must be independent')
        previous.update(role_sessions)
    return {'status':'FAIL' if findings else 'PASS','findings':findings,'scope':'Two native full-source batch reviews',
            **({'continuity_policy':batch['continuity_policy'],'continuity_decisions':decisions} if batch.get('continuity_policy') else {}),
            **({'suggestions':suggestions} if batch.get('review_policy')==REVIEW_POLICY else {})}
