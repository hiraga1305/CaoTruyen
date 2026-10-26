"""Resumable source-grounded translation: parallel drafts, two compact batch reviews.

Only launch/run/watch/diagnose invoke native models. Doctor verifies upstream without models.
Preflight is offline unless --repair-sources.
"""
import argparse
import hashlib
import json
import time
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path

from semantic_gate import read_json, digest, mechanical_findings, CHECKS, LITERARY_CHECKS
from native_oauth.workflow_io import atomic_json, atomic_text, file_lock
from native_oauth.chapter_integrity import validate_source, validate_source_archive
from native_oauth.native_evidence import validate_provenance
from native_oauth.session_monitor import get_session_monitor
from native_oauth.semantic_context import normalize_profile
from native_oauth.meaning_anchors import semantic_guidance
from native_oauth.recovery_native import NativeRecovery, RecoveryPending, ProtocolFailure,NativeContentReady
from native_oauth.recovery_sources import preflight, source_context, source_path, sha, import_replacements
from native_oauth.resilient_gate import (freeze, fragment, component, assemble, replay_candidate, response_shape,
    validate_translation, batch_package, review_packet, validate_compact_review, validate_batch_evidence)
from native_oauth.resilient_publication import manifest, prefix, commit, progress
from native_oauth.resilient_policy import POLICY,REVIEW_POLICY
from native_oauth.resilient_continuity import (VERSION as CONTINUITY, CHECKS as CONTINUITY_CHECKS,
    declared_entries, selected_entries, evidence_chapter, scoped_canon)
from native_oauth.workflow_guard import (local_release, release_identity, authorized_invocation,
    check_boundary, doctor, WorkflowGateError)

ROOT=Path(__file__).resolve().parents[1]


def context_view(rows):
    """Group literal context without repeating host paths/hashes per paragraph."""
    groups={}
    for row in rows:
        key=(row['chapter'],row['source_hash'])
        group=groups.setdefault(key,{'chapter':row['chapter'],'source_hash':row['source_hash'],'segments':{},'for_chapters':set()})
        group['segments'][row['id']]={'id':row['id'],'source':row['source']}
        if row.get('for_chapter') is not None:group['for_chapters'].add(row['for_chapter'])
    return [{'chapter':value['chapter'],'source_hash':value['source_hash'],
             'segments':[value['segments'][sid] for sid in sorted(value['segments'])],
             **({'for_chapters':sorted(value['for_chapters'])} if value['for_chapters'] else {})}
            for _,value in sorted(groups.items())]


def translation_view(packet):
    fields=('package_hash','chapter','book_title','genre','title','segments','glossary','canon','context_authority')
    view={key:packet[key] for key in fields}
    view['canon']=scoped_canon(packet['canon'],packet['chapter'])
    if packet.get('continuity_contract'):
        view['canon']['continuity_entries']=packet['continuity_contract']['entries']
        view['continuity_contract']={'version':CONTINUITY,'entries':[
            entry for entry in packet['continuity_contract']['entries'] if any(
                zh in '\n'.join(r['source'] for r in packet['segments'])
                +packet.get('metadata_title_source',{}).get('source','')
                for zh in (entry['zh'],*entry.get('aliases_zh',[])))]}
    if packet.get('validation_policy'):view['validation_policy']=packet['validation_policy']
    assigned={r['id'] for r in packet['segments']}
    guidance=packet['semantic_guidance']
    view['semantic_guidance']={**guidance,'source_anchors':[cue for cue in guidance['source_anchors'] if cue['source_id'] in assigned]}
    view['earlier_original_read_only']=context_view(packet['earlier_original_read_only'])
    if packet.get('neighbor_source_read_only'):view['neighbor_source_read_only']=packet['neighbor_source_read_only']
    if packet.get('metadata_title_source'):
        view['metadata_title_source']={key:packet['metadata_title_source'][key] for key in
            ('id','source','origin','catalog_chapter','declared_chapter','numbering_note') if key in packet['metadata_title_source']}
    return view


class Runner:
    def __init__(self,book,job,through,*,workers=4,model='gemini-3.8-flash-medium',review_model='gemini-3.8-flash-medium',
                 fallback='gemini-3.8-flash-high',timeout=300,max_repairs=2,review_model2=None,checkpoint_every=100,review_workers=2):
        self.book,self.job=Path(book).resolve(),Path(job).resolve();self.through=through
        self.job.mkdir(parents=True,exist_ok=True)
        legacy=self.book/'approved/manifest.json'
        if legacy.exists() and read_json(legacy).get('chapters'):
            raise ValueError('Existing legacy approvals: use an isolated book/job, never overwrite or mix approval modes')
        if not 1<=workers<=5 or not 30<=timeout<=600 or not 0<=max_repairs<=3 or through<1 or type(checkpoint_every) is not int or checkpoint_every<1:raise ValueError('Invalid recovery policy')
        self.checkpoint_every=checkpoint_every
        if type(review_workers) is not int or review_workers not in (1,2):raise ValueError('Use one or two independent reviewer workers')
        self.review_workers=review_workers
        if (self.book/'toc.json').exists() and through>len(read_json(self.book/'toc.json')):
            raise ValueError('Requested range exceeds the actual book TOC')
        self.workers,self.model,self.review_model,self.max_repairs=workers,model,review_model,max_repairs
        self.review_model2=review_model2 or review_model
        self.lore=read_json(self.book/'lore.json') if (self.book/'lore.json').exists() else {}
        self.canon_file=self.book/'translation_canon.json'
        if not self.canon_file.exists() and self.lore.get('book_id',self.book.name.removeprefix('book_'))=='siwangyouxi':
            self.canon_file=ROOT/'native_oauth/siwangyouxi_translation_canon_v2.json'
        self.canon=read_json(self.canon_file) if self.canon_file.exists() else {}
        declared_entries(self.canon)
        release=local_release()
        config={'version':'resilient-runner-2','validation_policy':POLICY,'review_policy':REVIEW_POLICY,'book':str(self.book),'through':through,'workers':workers,
                'workflow_release':release_identity(release),
                'checkpoint_every':checkpoint_every,
                'review_workers':review_workers,'content_repair':'owned-native-rows-1','continuity_policy':CONTINUITY,
                'translator':model,'reviewer':review_model,'reviewer2':self.review_model2,'fallback':fallback,'timeout':timeout,'max_repairs':max_repairs,
                'lore_hash':sha(self.book/'lore.json') if (self.book/'lore.json').exists() else None,
                'canon_hash':sha(self.canon_file) if self.canon_file.exists() else None}
        release_files=read_json(ROOT/'workflow_release.json')['files']
        config['workflow_files']={str(Path(name)):sha(ROOT/name) for name in [*release_files,'workflow_release.json']}
        self.configuration=config
        self.profile_terms=normalize_profile(self.lore.get('book_id',self.book.name.removeprefix('book_')),[],[],self.lore)[2]
        target=self.job/'configuration.json'
        if target.exists() and read_json(target)!=config:raise ValueError('Recovery configuration/canon changed; create a new revision job')
        atomic_json(target,config)
        for name,expected in config['workflow_files'].items():
            snapshot=self.job/'workflow_snapshot'/name
            if snapshot.exists() and sha(snapshot)!=expected:raise ValueError('Workflow snapshot changed')
            if not snapshot.exists():
                snapshot.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,snapshot)
        self.native=NativeRecovery(self.job,timeout,fallback,max_workers=workers)
        self.monitor=get_session_monitor(self.lore.get('book_id',self.book.name.removeprefix('book_')),
            self.lore.get('book_title_vi',self.book.name),through,state_file=self.job/'session_monitor_state.json')
        self.monitor.genre=self.lore.get('genre','Theo nguồn');self.monitor.chapter_range=f'1–{through}'
        self.states={};self.requests=[]

    def badge(self,stage,status,chapter=1):
        self.monitor.record_worker_active(stage,chapter,(chapter-1)//5+1,message=status)
        print(self.monitor.render_markdown_badge(),flush=True)

    def state(self,chapter,status,**extra):
        self.states[str(chapter)]={'chapter':chapter,'status':status,**extra}

    def snapshot(self,path):
        path=Path(path);data=path.read_bytes();expected=hashlib.sha256(data).hexdigest()
        target=self.job/'input_snapshots'/(expected+'_'+path.name)
        with file_lock(self.job/'input_snapshot.lock',timeout=15):
            if target.exists() and sha(target)!=expected:raise ValueError('Immutable input snapshot changed')
            if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        return target

    def checkpoint(self,status):
        atomic_json(self.job/'campaign.json',{'status':status,'through_chapter':self.through,
            'chapters':self.states,'next_actions':self.requests,'updated_epoch':time.time()})

    def approved_checkpoint(self,chapter):
        """Record a verified publication boundary; no extra native audit or stop."""
        current=manifest(self.book)
        if sorted(map(int,current['chapters']))!=list(range(1,chapter+1)):
            raise ValueError('Checkpoint must own the complete approved prefix')
        atomic_json(self.job/'checkpoints'/f'chapter_{chapter:04d}.json',{
            'status':'APPROVED_CHECKPOINT','through_chapter':chapter,'next_chapter':chapter+1 if chapter<self.through else None,
            'approved_entry_hash':digest(current['chapters'][str(chapter)]),'configuration_hash':digest(self.configuration),
            'created_epoch':time.time(),'scope':'Already committed batches; no additional native review'})
        self.badge('checkpoint',f'APPROVED_CHECKPOINT {chapter}/{self.through}',chapter)
        self.monitor.record_stage_result(chapter,'checkpoint','checkpoint','APPROVED_CHECKPOINT')

    @contextmanager
    def invocation(self):
        path=self.job/'invocations.json';rows=read_json(path) if path.exists() else []
        row={'started_epoch':time.time(),'status':'RUNNING'};rows.append(row);atomic_json(path,rows);started=time.monotonic()
        try:
            with authorized_invocation(self.job,self.configuration):yield
        except BaseException as error:
            self.requests.append({'reason':str(error),'action':getattr(error,'action','INSPECT_INTERRUPTION_AND_RESUME_SAME_JOB')})
            self.checkpoint('RECOVERY_PENDING');raise
        finally:
            row.update(ended_epoch=time.time(),active_wall_seconds=time.monotonic()-started,
                status=read_json(self.job/'campaign.json').get('status','RECOVERY_PENDING') if (self.job/'campaign.json').exists() else 'RECOVERY_PENDING')
            atomic_json(path,rows)
            for name in ('translation_live_dashboard.html','translation_session_dashboard.md'):
                source=self.monitor.artifact_dir/name if isinstance(self.monitor.artifact_dir,Path) else None
                if source and source.exists():atomic_text(self.job/name,source.read_text(encoding='utf8'))

    def packet(self,chapter,queries=()):
        path=source_path(self.book,self.job,chapter);source=read_json(path)
        validate_source(source);validate_source_archive(source)
        for name,expected in ((self.book/'lore.json',self.configuration['lore_hash']),(self.canon_file,self.configuration['canon_hash'])):
            if (sha(name) if name.exists() else None)!=expected:
                raise RecoveryPending('INTEGRITY','RESTORE_FROZEN_CANON_OR_CREATE_NEW_REVISION_JOB',self.job/'configuration.json','Canon/lore changed during campaign')
        snapshot=self.snapshot(path)
        terms=self.profile_terms
        names={key:val for key,(val,kind) in terms.items() if kind=='character_name' and ' / ' not in val}
        request_file=self.job/'context_requests.json'
        requested=read_json(request_file).get(str(chapter),[]) if request_file.exists() else []
        context=source_context(self.job,chapter,list(queries)+requested+[key for key in names if key in ''.join(r['source'] for r in source['segments'])])
        bindings={str(path):sha(path),str(snapshot):sha(snapshot)}
        original=self.book/'sources'/f'source_chapter_{chapter:04d}.json'
        if original.exists():bindings[str(original)]=sha(original)
        saved_context={}
        for extra in set([self.book/'lore.json',self.canon_file,*[Path(r['source_file']) for r in context]]):
            bindings[str(extra.resolve())]=sha(extra) if extra.exists() else None
            if extra.exists():
                saved=self.snapshot(extra);bindings[str(saved)]=sha(saved)
                saved_context[str(extra)]=str(saved)
        for row in context:
            row['source_input_file']=row['source_file'];row['source_file']=saved_context[row['source_file']]
        packet={'version':'resilient-source-draft-1','validation_policy':POLICY,'chapter':chapter,'book_id':source['book_id'],
            'book_title':self.lore.get('book_title_vi',self.book.name),'genre':self.lore.get('genre','Theo nguồn'),
            'total_chapters':self.through,'source_file':str(snapshot),'source_input_file':str(path),'source_ref':source['source_ref'],
            'session_monitor_state_file':str(self.job/'session_monitor_state.json'),
            'origin_source_hash':source['package_hash'],'title':source['title'],
            'segments':[{'id':r['id'],'source':r['source']} for r in source['segments']],
            'glossary':names,'canon':self.canon,'semantic_guidance':semantic_guidance(source['segments'],terms),
            'model_policy':{'translator':self.model,'reviewer':self.review_model,'reviewer2':self.review_model2,'fallback':self.native.fallback},
            'earlier_original_read_only':context,'native_bound_files':bindings,
            'context_authority':'Literal earlier Chinese; no unreviewed translation is approved canon'}
        from native_oauth.book_publication import title_ids
        if not title_ids(source):
            from native_oauth.title_selection import metadata_title_source
            packet['metadata_title_source']=metadata_title_source(source)
            bindings[packet['metadata_title_source']['archive']]=packet['metadata_title_source']['archive_sha256']
        for term in self.canon.get('source_bound_terms',[]):
            ch=int(term['source_id'][1:5]);raw=read_json(source_path(self.book,self.job,ch))
            if not any(r['id']==term['source_id'] and term['source_quote'] in r['source'] and term['zh'] in r['source'] for r in raw['segments']):
                raise ValueError('Canon source evidence changed')
            bindings[str(source_path(self.book,self.job,ch))]=sha(source_path(self.book,self.job,ch))
        entries=selected_entries(self.canon,source);evidence={}
        for entry in entries:
            evidence_path=source_path(self.book,self.job,evidence_chapter(entry))
            saved=self.snapshot(evidence_path)
            bindings[str(evidence_path)]=sha(evidence_path);bindings[str(saved)]=sha(saved)
            evidence[entry['key']]={'source_file':str(saved),'source_input_file':str(evidence_path)}
        packet['continuity_contract']={'version':CONTINUITY,'entries':entries,'evidence':evidence}
        from native_oauth.resilient_continuity import validate_contract
        validate_contract(packet,source)
        return freeze(packet)

    def translate_protocol(self,packet,current=None,findings=None):
        return ('Dịch đầy đủ tiểu thuyết Trung–Việt theo nguồn. Giữ nghĩa, phủ định, số, chủ thể, góc nhìn, '
            'mức chắc chắn, lời tác giả. Canon là quy ước có phạm vi; không biến lời nhân vật thành sự thật. '
            'Khi nguồn gọi tên riêng, ưu tiên tên Việt chuẩn; dùng đại từ có chủ thể rõ khi phù hợp ngữ cảnh. '
            'Quy ước ngôi kể chỉ áp dụng đúng thực thể và phạm vi nêu trong canon, không thay tất cả tên riêng hoặc lời thoại. '
            'Giữ nhất quán tên/biệt danh, nhãn nghề, vật phẩm, địa danh và tổ chức trên cả wave và biên chương. '
            'continuity_contract là quy ước cách viết có bằng chứng, không phải sự thật về thân phận hay quan hệ. '
            'Xác định người nói và người nghe trước khi chọn xưng hô; khi nguồn mơ hồ không tự thêm giới tính, tuổi hoặc quan hệ. '
            'Ngữ cảnh nguồn trước chỉ đọc để hiểu, không dịch nhầm thành đoạn được giao. '
            'Trả JSON {"package_hash":"'+packet['package_hash']+'","segments":[{"id":"ID đúng nguồn","text":"bản Việt đầy đủ"}],'
            '"title_vi":"dịch metadata_title_source nếu có"}. Bao phủ đúng segments trong SOURCE, không đổi ID. '
            'Không sót chữ Hán trong bản Việt; không tự xóa chữ hoặc bỏ nghĩa để qua kiểm. '
            'Chỉ khi nguyên tác cố ý bàn về chữ/chuỗi ký tự cần giữ nguyên, khai thêm source_script_quotes:[{id,quote,reason}], '
            'quote phải nguyên văn có ở nguồn và đích, tối đa 32 ký tự, để cả hai reviewer kiểm; không dùng để giữ phần chưa dịch. '
            'Khi sửa giữ những đoạn đúng, kiểm lại phản hồi trên nguồn. Không gọi tool, không tự duyệt.\nSOURCE:\n'
            +json.dumps(translation_view(packet),ensure_ascii=False,separators=(',',':'),sort_keys=True)
            +('\nUNREVIEWED_CURRENT_ROWS:\n'+json.dumps(current,ensure_ascii=False,sort_keys=True) if current else '')
            +('\nSOURCE_BOUND_FINDINGS_TO_RECHECK:\n'+json.dumps(findings,ensure_ascii=False,sort_keys=True) if findings else ''))

    def _native_translation(self,packet,ids,title,key,current=None,findings=None,model=None,retain_content=True):
        part=fragment(packet,ids,title)
        protocol=self.translate_protocol(part,current,findings)
        if len(protocol)>110000:raise RecoveryPending('CONTEXT','REDUCE_ASSIGNED_SOURCE_SCOPE',self.job/'campaign.json','Translation packet exceeds budget')
        try:
            value,proof=self.native.call(key,part,'translator',model or self.model,protocol,
                lambda v:validate_translation(part,v),retain_content=retain_content)
        except NativeContentReady as ready:
            affected={row['id'] for row in ready.findings}
            repair_ids=[sid for sid in ids if sid in affected]
            repair_title=title and part.get('metadata_title_source',{}).get('id') in affected
            if not repair_ids:repair_ids=[ids[0]]
            retained=[sid for sid in ids if sid not in repair_ids]
            keep_title=title and not repair_title
            parts=[component(part,ready.value,ready.proof,ids=retained,title=keep_title)] if retained or keep_title else []
            current=[row for row in ready.value['segments'] if row['id'] in repair_ids]
            parts+=self._repair_scope(packet,repair_ids,repair_title,[*key,'content-repair',ready.proof['hash']],current,ready.findings)
            self.native.resolved(key,parts)
            return parts
        return [component(part,value,proof,title=title)]

    def _translation_scope(self,packet,ids,title,key):
        try:return self._native_translation(packet,ids,title,key)
        except RecoveryPending as pending:
            if pending.kind not in ('FORMAT','TIMEOUT','CONTENT','CONTEXT') or len(ids)<=1:raise
            cut=len(ids)//2
            parts=[*self._translation_scope(packet,ids[:cut],title,[*key,'left']),
                   *self._translation_scope(packet,ids[cut:],False,[*key,'right'])]
            self.native.resolved(key,parts)
            return parts

    def generate(self,chapter):
        packet=self.packet(chapter);pointer=self.job/'drafts'/f'{chapter:04d}.json'
        atomic_json(self.job/'source_packets'/(packet['package_hash']+'.json'),packet)
        if pointer.exists():
            entry=read_json(pointer)
            if entry['package_hash']==packet['package_hash']:
                candidate=read_json(entry['file']);replay_candidate(packet,candidate)
                return {'source_packet':packet,'candidate_file':entry['file'],'candidate_hash':digest(candidate)}
        self.badge(f'draft-{chapter}','TRANSLATING',chapter)
        timing=self.job/'chapter_times'/f'{chapter:04d}.json'
        if not timing.exists():atomic_json(timing,{'started_epoch':time.time(),'definition':'Elapsed until approval, including queue and resume pauses'})
        ids=[r['id'] for r in packet['segments']];title=bool(packet.get('metadata_title_source'))
        key=['translate',chapter,packet['package_hash'],'whole']
        parts=[]
        try:parts=self._native_translation(packet,ids,title,key)
        except RecoveryPending as pending:
            if pending.kind not in ('FORMAT','TIMEOUT','CONTENT','CONTEXT'):raise
            # Smaller assigned output, original IDs, fresh real native attempts.
            for start in range(0,len(ids),35):
                selected=ids[start:start+35]
                parts+=self._translation_scope(packet,selected,title and start==0,
                    ['translate',chapter,packet['package_hash'],'part',start])
            self.native.resolved(key,parts)
        candidate,_=assemble(packet,parts)
        path=self.job/'candidate_revisions'/f'{chapter:04d}'/(digest(candidate)+'.json');atomic_json(path,candidate)
        atomic_json(pointer,{'package_hash':packet['package_hash'],'file':str(path)})
        times=read_json(timing)
        if 'draft_ready_epoch' not in times:
            ready_epoch=time.time()
            times.update(draft_ready_epoch=ready_epoch,draft_elapsed_seconds=max(0,ready_epoch-times['started_epoch']))
        atomic_json(timing,times)
        self.state(chapter,'DRAFT_READY',candidate=str(path))
        self.monitor.record_stage_result(chapter,'draft',f'draft-{chapter}','DRAFT_READY')
        return {'source_packet':packet,'candidate_file':str(path),'candidate_hash':digest(candidate)}

    def expand_context(self,item,findings):
        path=self.job/'context_requests.json';requests=read_json(path) if path.exists() else {}
        chapter=item['source_packet']['chapter'];before=requests.get(str(chapter),[])
        queries=list(dict.fromkeys(before+[f['context_query'] for f in findings if f.get('context_query')]))
        if queries==before:
            raise RecoveryPending('CONTENT','SUPPLY_LITERAL_SOURCE_ENTITY_QUERY',path,'Reviewer needs context but supplied no new grounded search term')
        requests[str(chapter)]=queries;atomic_json(path,requests)
        if self.packet(chapter)['package_hash']==item['source_packet']['package_hash']:
            raise RecoveryPending('CONTENT','VERIFY_MISSING_CONTEXT_IN_SOURCE',path,'Earlier source search yielded no additional grounded context')
        return self.generate(chapter)

    def repair(self,item,findings,round_num):
        packet=item['source_packet'];candidate=read_json(item['candidate_file'])
        affected={r['id'] for r in findings};body={r['id'] for r in packet['segments']}
        selected=[r['id'] for r in packet['segments'] if r['id'] in affected]
        title=packet.get('metadata_title_source',{}).get('id') in affected
        if not selected and not title:raise ValueError('Repair finding does not own any source ID')
        budget_file=self.job/'semantic_repair_budget'/f"{packet['chapter']:04d}.json"
        budget=read_json(budget_file) if budget_file.exists() else {'requests':[]}
        repair_key=digest([item['candidate_hash'],findings])
        if repair_key not in budget['requests']:
            if len(budget['requests'])>=max(1,self.max_repairs)*3:
                raise RecoveryPending('CONTENT','REVIEW_SOURCE_CONTEXT_OR_CANON_BEFORE_MORE_REVISIONS',budget_file,'Cumulative semantic repair budget reached')
            budget['requests'].append(repair_key);atomic_json(budget_file,budget)
        # Title repair also owns one body paragraph so every fragment has source context.
        if not selected:selected=[packet['segments'][0]['id']]
        affected.update(selected)
        retained=[]
        for old in candidate['components']:
            keep=[sid for sid in old['ids'] if sid not in affected]
            keep_title=old['owns_title'] and not title
            if keep or keep_title:
                retained.append({**old,'ids':keep,'owns_title':keep_title})
        current=[r for r in candidate['segments'] if r['id'] in affected]
        parts=self._repair_scope(packet,selected,title,
            ['repair',packet['chapter'],repair_key],current,findings)
        fixed,_=assemble(packet,[*retained,*parts])
        if fixed['segments']==candidate['segments'] and fixed.get('title_vi')==candidate.get('title_vi'):
            raise RecoveryPending('CONTENT','EXPAND_VERIFIED_CONTEXT_AND_REPAIR_AGAIN',self.job/'campaign.json',
                'Native repair did not change the failed text; do not retry review to fish for PASS')
        path=self.job/'candidate_revisions'/f"{packet['chapter']:04d}"/(digest(fixed)+'.json')
        atomic_json(path,fixed)
        atomic_json(self.job/'drafts'/f"{packet['chapter']:04d}.json",{'package_hash':packet['package_hash'],'file':str(path)})
        return {'source_packet':packet,'candidate_file':str(path),'candidate_hash':digest(fixed)}

    def _repair_scope(self,packet,ids,title,key,current,findings):
        """Repair failures get the same bounded source-owned splitting as drafts."""
        try:
            return self._native_translation(packet,ids,title,key,current,findings,model=self.native.fallback,retain_content=False)
        except RecoveryPending as pending:
            if pending.kind not in ('FORMAT','TIMEOUT','CONTENT','CONTEXT') or len(ids)<=1:raise
            cut=len(ids)//2;parts=[]
            title_id=packet.get('metadata_title_source',{}).get('id')
            for side,selected,owns_title in (('left',ids[:cut],title),('right',ids[cut:],False)):
                owned=set(selected)
                if owns_title:owned.add(title_id)
                parts+=self._repair_scope(packet,selected,owns_title,[*key,side],
                    [r for r in current if r['id'] in owned],[f for f in findings if f['id'] in owned])
            self.native.resolved(key,parts)
            return parts

    def review(self,batch):
        roles=('meaning-reviewer','literary-reviewer')
        workers=min(self.review_workers,self.native.health()['worker_limit'])
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(self._review_role,batch,role) for role in roles]
            reviews=[future.result() for future in futures]
        evidence={'package':batch,'reviews':reviews}
        report=validate_batch_evidence(evidence)
        atomic_json(self.job/'batch_reviews'/batch['package_hash']/'evidence.json',evidence)
        atomic_json(self.job/'batch_reviews'/batch['package_hash']/'report.json',report)
        return evidence,report

    def _review_role(self,batch,role):
        scope=list(range(1,len(batch['catalog'])+1));packet=review_packet(batch,scope)
        key=['review',batch['package_hash'],role,'whole']
        try:parts=[self._review_part(packet,role,key)]
        except RecoveryPending as pending:
            if pending.kind not in ('FORMAT','TIMEOUT','CONTEXT'):raise
            parts=[]
            for start in range(0,len(scope),60):
                selected=scope[start:start+60]
                parts+=self._review_scope(batch,role,selected,['review',batch['package_hash'],role,'part',start])
            self.native.resolved(key,parts)
        return {'role':role,'parts':parts}

    def _review_scope(self,batch,role,scope,key):
        packet=review_packet(batch,scope)
        try:return [self._review_part(packet,role,key)]
        except RecoveryPending as pending:
            if pending.kind not in ('FORMAT','TIMEOUT') or len(scope)<=15:raise
            cut=len(scope)//2
            parts=[*self._review_scope(batch,role,scope[:cut],[*key,'left']),
                   *self._review_scope(batch,role,scope[cut:],[*key,'right'])]
            self.native.resolved(key,parts)
            return parts

    def review_protocol(self,packet,role):
        # The whole wave is visible even when output coverage is partitioned.
        visible={k:packet[k] for k in ('package_hash','prefix','approved_context','source_context','source_risk_cues','canon','catalog','scope_slots','approval_eligible')}
        if packet.get('review_policy'):visible['review_policy']=packet['review_policy']
        if packet.get('continuity_policy'):visible['continuity_policy']=packet['continuity_policy']
        visible['canon']=scoped_canon(packet['canon'],max(row['chapter'] for row in packet['catalog']))
        if packet.get('continuity_policy'):
            keys={entry['key'] for item in packet['chapters']
                for entry in item['source_packet']['continuity_contract']['entries']}
            visible['canon']['continuity_entries']=[entry for entry in packet['canon'].get('continuity_entries',[])
                if entry['key'] in keys]
        visible['source_context']=context_view(visible['source_context'])
        protocol=('Review ALL supplied original Chinese and Vietnamese in chronological order. '
            'Inspect every assigned slot, including titles. source_ref=0 and target_ref=0 mean the COMPLETE '
            'source/target paragraph of that exact catalog slot; never retype quotes or IDs. '
            'Return JSON {package_hash,verdict:"PASS"|"FAIL",checks:'+json.dumps(dict.fromkeys(CHECKS,True))+
            ',literary_checks:'+json.dumps(dict.fromkeys(LITERARY_CHECKS,True))+
            ',rows:[[slot,"PASS"|"FAIL"],...],issues:[{slot,source_ref:0,target_ref:0,kind,reason}]}. '
            'true means inspected, not no errors. Cover scope_slots exactly in order. A FAIL row requires an issue; '
            'issues require FAIL overall. Valid kinds: meaning,completeness,entities,speaker_pronouns,numbers_units,'
            'negation_modality,time_causality,continuity,style,title,needs_context. '
            'If missing context, report needs_context with a grounded context_query (an exact source name/term, at most 24 characters); preserve deliberate ambiguity. '
            'source_context is earlier original Chinese for the specified for_chapter only; never turn later knowledge into earlier character knowledge. '
            'Source risk cues are literal reminders, not exhaustive facts; inspect complete paragraphs beyond the cues. '
            'Accept valid Vietnamese paraphrases; optional wording preferences are not blocking defects. '
            'A missing canonical name string is not automatically a lost entity: inspect who each pronoun or alias refers to. '
            'A misspelled name, wrong referent, lost identity, changed negation/number/rule is an error in issues. '
            'For review_policy resilient-review-2, also return semantic_obligations_checked:[slot,...] covering '
            'every assigned catalog slot with review_obligations, in order (or []). Inspect each obligation explicitly; '
            'a source_script_quote claim requires necessary original-script quotation, not untranslated residue. '
            'Optional style preferences go in suggestions:[{slot,source_ref:0,target_ref:0,kind:"style",reason}], '
            'without turning a correct row into FAIL. Required scoped canon violations remain errors. '
            'For continuity_policy '+CONTINUITY+', also return continuity_checks:'+json.dumps(dict.fromkeys(CONTINUITY_CHECKS,True))+
            ' and continuity_decisions:[{slot,key,status,reason}] for every assigned continuity_convention obligation, '
            'in catalog/obligation order. Status is consistent (declared spelling present), valid_variation '
            '(explain the actual referent and why pronoun/alias/title/quotation or out-of-scope use is valid), '
            'violation (blocking entities/continuity/speaker_pronouns issue), or needs_context (owned issue plus context_query). '
            'Inspect naming/label consistency and speaker/addressee even when no convention is declared; decisions is [] only when no assigned convention exists. '
            'Changing the same name or named profession/item/place/faction without source-supported reason is a continuity error, '
            'not an optional stylistic preference. Capitalisation and valid contextual address can vary. '
            'Separate a forum nickname from an address, a named profession from ordinary description, and impersonation/belief from fact. '
            'Never infer gender, age, relation, alias identity or dialogue recipient from the Vietnamese name or protagonist status. '
            'For needs_context, supply context_query: an exact term in the failed slot or its supplied earlier source context, '
            'at most 24 characters; never invent a name or use future source. '
            'Do not force dialogue ta–ngươi; obey scoped narrator convention. Role '+role+
            '. Both roles inspect meaning; literary role also reads fluent Vietnamese and continuity. '
            'Do not inspect another reviewer conclusion; no tools or approval claims.\n'
            +json.dumps(visible,ensure_ascii=False,separators=(',',':'),sort_keys=True))
        return protocol

    def _review_part(self,packet,role,key):
        protocol=self.review_protocol(packet,role)
        if len(protocol)>110000:raise RecoveryPending('CONTEXT','SPLIT_BATCH',self.job/'campaign.json','Review wave exceeds full-context budget')
        model=self.review_model if role=='meaning-reviewer' else self.review_model2
        value,proof=self.native.call(key,packet,role,model,protocol,lambda v:validate_compact_review(packet,v))
        return proof

    def run(self,*,repair_sources=True):
        with file_lock(self.job/'campaign.lock',timeout=1),self.invocation():
            self.states={str(ch):{'chapter':ch,'status':'QUEUED','dependency':'Previous approved prefix required'} for ch in range(1,self.through+1)}
            self.requests=[]
            self.badge('source-preflight','CHECKING_SOURCES')
            sources=preflight(self.book,self.job,self.through,repair_sources=repair_sources,
                progress_callback=lambda done,total:self.badge('source-preflight',f'SOURCE {done}/{total}'))
            self.monitor.record_stage_result(1,'source-preflight','source-preflight',sources['status'])
            ready={r['chapter'] for r in sources['sources'] if r['status']=='SOURCE_READY'}
            for row in sources['pending']:
                self.state(row['chapter'],'WAITING_SOURCE',reason=row['reason'],action=row['action']);self.requests.append(row)
            value=manifest(self.book);approved=sorted(map(int,value['chapters']))
            if approved:
                from native_oauth.resilient_publication import validate_manifest,read_approval
                validated=validate_manifest(self.book,value)
            if approved and approved[-1]>self.through:raise ValueError('Requested range is smaller than the committed approved range')
            inherited=[]
            for ch in approved:
                item=read_approval(self.book,ch,value,validated[value['chapters'][str(ch)]['batch']])
                inherited.append({'chapter_num':ch,'title':item['rendered']['title'],
                    'paragraphs':len(item['rendered']['paragraphs']),
                    'words':sum(len(p.split()) for p in item['rendered']['paragraphs']),
                    'evidence_path':str(item['evidence_path'])})
            self.monitor.sync_approved_prefix(inherited)
            for ch in approved:self.state(ch,'APPROVED')
            cursor=len(approved)+1;lookahead_end=min(self.through,cursor+14)
            while cursor<=self.through:
                check_boundary(self.job)
                boundary=((cursor-1)//self.checkpoint_every+1)*self.checkpoint_every
                chapters=list(range(cursor,min(cursor+5,self.through+1,boundary+1)));items={}
                self.badge('wave',f'WAVE {chapters[0]}–{chapters[-1]}',cursor)
                effective_workers=min(self.workers,self.native.health()['worker_limit'])
                with ThreadPoolExecutor(max_workers=effective_workers) as pool:
                    futures={pool.submit(self.generate,ch):ch for ch in chapters if ch in ready}
                    for future in as_completed(futures):
                        ch=futures[future]
                        try:items[ch]=future.result()
                        except Exception as error:
                            self.monitor.record_stage_result(ch,'draft',f'draft-{ch}','RECOVERY_PENDING')
                            self.state(ch,'RECOVERY_PENDING',reason=str(error),action=getattr(error,'action','INSPECT_AND_RESUME'))
                            self.requests.append({'chapter':ch,'reason':str(error),'action':getattr(error,'action','INSPECT_AND_RESUME')})
                if len(items)!=len(chapters) or cursor!=len(manifest(self.book)['chapters'])+1:
                    for ch in items:self.state(ch,'DRAFT_READY_AWAITING_PREFIX',candidate=items[ch]['candidate_file'])
                    cursor=chapters[-1]+1;self.checkpoint('RECOVERY_PENDING')
                    if cursor>lookahead_end:break
                    continue
                ordered=[items[ch] for ch in chapters]
                while True:
                    batch=batch_package(ordered,prefix(manifest(self.book),cursor),self.canon,self.book)
                    # Reserve room for instructions. Adapt the wave, never truncate source.
                    if len(self.review_protocol(review_packet(batch,list(range(1,len(batch['catalog'])+1))),'meaning-reviewer'))<=110000 or len(ordered)==1:break
                    ordered.pop();chapters.pop()
                try:
                    for attempt in range(self.max_repairs+1):
                        batch=batch_package(ordered,prefix(manifest(self.book),cursor),self.canon,self.book)
                        evidence,report=self.review(batch)
                        if report['status']=='PASS':break
                        if attempt==self.max_repairs:raise RecoveryPending('CONTENT','EXPAND_SOURCE_CONTEXT_AND_RESUME',self.job/'campaign.json','Batch still fails after focused HIGH repairs')
                        fixed=[]
                        for item in ordered:
                            findings=[f for f in report['findings'] if f['chapter']==item['source_packet']['chapter']]
                            if any(f['kind']=='needs_context' for f in findings):fixed.append(self.expand_context(item,findings))
                            else:fixed.append(self.repair(item,findings,attempt+1) if findings else item)
                        ordered=fixed
                    commit(self.book,evidence)
                    for item in ordered:
                        ch=item['source_packet']['chapter'];candidate=read_json(item['candidate_file'])
                        self.state(ch,'APPROVED',candidate=item['candidate_file'])
                        timing_file=self.job/'chapter_times'/f'{ch:04d}.json';timing=read_json(timing_file)
                        approved_epoch=time.time()
                        timing.update(approved_epoch=approved_epoch,elapsed_until_approval_seconds=max(0,approved_epoch-timing['started_epoch']))
                        draft_ready=timing.get('draft_ready_epoch')
                        if isinstance(draft_ready,(int,float)) and timing['started_epoch']<=draft_ready<=approved_epoch:
                            timing['post_draft_elapsed_seconds']=approved_epoch-draft_ready
                        atomic_json(timing_file,timing)
                        self.monitor.record_chapter_done(ch,candidate.get('title_vi',item['source_packet']['title']),
                            (cursor-1)//5+1,'batch-approved',len(candidate['segments']),
                            sum(len(r['text'].split()) for r in candidate['segments']),
                            timing['elapsed_until_approval_seconds'],True,
                            draft_seconds=timing.get('draft_elapsed_seconds'),post_draft_seconds=timing.get('post_draft_elapsed_seconds'),
                            approval_mode='native_batch')
                    if chapters[-1]%self.checkpoint_every==0 or chapters[-1]==self.through:
                        self.approved_checkpoint(chapters[-1])
                    cursor=chapters[-1]+1;lookahead_end=min(self.through,cursor+14)
                except Exception as error:
                    self.requests.append({'range':chapters,'reason':str(error),'action':getattr(error,'action','INSPECT_EVIDENCE_AND_RESUME')})
                    for ch in chapters:self.state(ch,'REVIEW_RECOVERY_PENDING',reason=str(error),
                        action=getattr(error,'action','INSPECT_EVIDENCE_AND_RESUME'))
                    cursor=chapters[-1]+1
                self.checkpoint('RUNNING')
                self.monitor.record_stage_result(chapters[0],'wave','wave','WAVE_BOUNDARY')
                print(self.monitor.render_markdown_badge(),flush=True)
                if self.requests and cursor>lookahead_end:break
            final=progress(self.book,self.through)
            status='COMPLETE' if final['export_ready'] else 'RECOVERY_PENDING'
            self.checkpoint(status);atomic_json(self.job/'progress.json',final)
            return final

    def diagnose(self,chapters,*,repair_sources=True):
        """Real source-only stress tests, with focused repairs, never publication."""
        if not chapters or any(ch<1 or ch>self.through for ch in chapters):raise ValueError('Specify real diagnostic chapter IDs')
        with file_lock(self.job/'campaign.lock',timeout=1),self.invocation():
            self.badge('diagnostic','SOURCE_ONLY_DIAGNOSTIC')
            preflight(self.book,self.job,self.through,repair_sources=repair_sources)
            result={'approval_eligible':False,'status':'RUNNING','chapters':[]}
            for chapter in sorted(set(chapters)):
                check_boundary(self.job)
                try:
                    item=self.generate(chapter)
                    for attempt in range(self.max_repairs+1):
                        batch=batch_package([item],{'through_chapter':0,'entry_hash':None},self.canon,self.book,approval_eligible=False)
                        evidence,report=self.review(batch)
                        if report['status']=='PASS':break
                        if attempt==self.max_repairs:
                            raise RecoveryPending('CONTENT','INSPECT_SOURCE_BOUND_DIAGNOSTIC',self.job/'diagnostic_result.json','Diagnostic repair budget reached')
                        if any(f['kind']=='needs_context' for f in report['findings']):item=self.expand_context(item,report['findings'])
                        else:item=self.repair(item,report['findings'],attempt+1)
                    row={'chapter':chapter,'status':'DIAGNOSTIC_PASS_NOT_APPROVAL','evidence':evidence}
                except Exception as error:
                    row={'chapter':chapter,'status':'RECOVERY_PENDING','reason':str(error),
                        'action':getattr(error,'action','INSPECT_AND_RESUME_DIAGNOSTIC')}
                    self.requests.append(row)
                result['chapters'].append(row);atomic_json(self.job/'diagnostic_result.json',result)
            result['status']='DIAGNOSTIC_PASS_NOT_APPROVAL' if all(r['status']=='DIAGNOSTIC_PASS_NOT_APPROVAL' for r in result['chapters']) else 'RECOVERY_PENDING'
            atomic_json(self.job/'diagnostic_result.json',result);self.checkpoint(result['status'])
            self.monitor.record_stage_result(chapters[-1],'diagnostic','diagnostic',result['status'])
            return result


def launch_runner(book,job,through,**options):
    """Verify upstream, then resume a compatible job or choose a fresh revision.

    Never copy old configuration over new code or change old candidate hashes.
    """
    current=doctor()
    original=Path(job).resolve() if job is not None else None
    if original is None:
        slug=''.join(c if c.isalnum() or c in '-_' else '_' for c in Path(book).name)[:48] or 'book'
        target=ROOT/'audit/campaigns'/slug/('wf_'+current['workflow_version'].replace('.','_')+'_'+uuid.uuid4().hex[:12])
    else:target=original
    try:runner=Runner(book,target,through,**options)
    except ValueError as error:
        if original is None or 'Recovery configuration/canon changed' not in str(error):raise
        target=original.with_name(original.name.split('__wf_',1)[0]+'__wf_'+current['workflow_version'].replace('.','_')+'_'+uuid.uuid4().hex[:12])
        runner=Runner(book,target,through,**options)
    if original is not None and original!=target and (original/'effective_sources').exists():
        import_replacements(Path(book),target,original/'effective_sources')
    atomic_json(target/'launch_selection.json',{'workflow':current,'selected_job':str(target),
        'previous_job':str(original) if original else None,'scope_through_chapter':through,
        'action':'NEW_REVISION_KEEP_APPROVED_PREFIX' if original!=target else 'RESUME_MATCHING_JOB',
        'note':'Old unapproved drafts/evidence preserved; no relabelling or blind cache import'})
    print(json.dumps(read_json(target/'launch_selection.json'),ensure_ascii=False),flush=True)
    return runner


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('doctor','launch','preflight','run','watch','diagnose','status','report','seal','export','retry-ready'))
    parser.add_argument('--book-dir',type=Path);parser.add_argument('--job',type=Path)
    parser.add_argument('--through-chapter',type=int);parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--model',default='gemini-3.8-flash-medium');parser.add_argument('--review-model',default='gemini-3.8-flash-medium')
    parser.add_argument('--auditor-model',help='Second independent reviewer; defaults to --review-model')
    parser.add_argument('--fallback-model',default='gemini-3.8-flash-high');parser.add_argument('--timeout',type=int,default=300)
    parser.add_argument('--repair-sources',action='store_true',help='Preflight only: allow verified source refetch')
    parser.add_argument('--no-source-refetch',action='store_true',help='Run/watch: keep network source repair queued')
    parser.add_argument('--watch-rounds',type=int,default=3);parser.add_argument('--out',type=Path)
    parser.add_argument('--checkpoint-every',type=int,default=100,help='Record approved checkpoints without another model call or external audit')
    parser.add_argument('--review-workers',type=int,choices=(1,2),default=2,help='Independent reviewer sessions; two run concurrently by default')
    parser.add_argument('--reason',help='retry-ready: describe the external fix; never overrides a semantic FAIL')
    parser.add_argument('--source-recovery-dir',type=Path,help='Import verified source revisions, preserving original source files')
    parser.add_argument('--chapters',type=int,nargs='+',help='diagnose only: source-only chapters, never publication approval')
    args=parser.parse_args()
    if args.action=='doctor':
        try:result=doctor(job=args.job)
        except WorkflowGateError as error:
            print(json.dumps({'status':'WORKFLOW_BLOCKED','reason':str(error),'next_action':error.action},ensure_ascii=False));raise SystemExit(2)
        print(json.dumps(result,ensure_ascii=False));return
    if args.book_dir is None or args.through_chapter is None:parser.error('Specify --book-dir and the user-authorized --through-chapter')
    if args.watch_rounds<1:parser.error('--watch-rounds must be positive')
    if args.job is None and args.action!='launch':parser.error('--job is required except for doctor/launch')
    if args.source_recovery_dir:
        if args.action not in ('launch','preflight','run','watch','diagnose'):parser.error('Source import is only valid before preflight/run/diagnose')
        if args.action!='launch':import_replacements(args.book_dir,args.job,args.source_recovery_dir)
    if args.action=='preflight':
        lore=read_json(args.book_dir/'lore.json') if (args.book_dir/'lore.json').exists() else {}
        mon=get_session_monitor(lore.get('book_id',args.book_dir.name.removeprefix('book_')),lore.get('book_title_vi',args.book_dir.name),
            args.through_chapter,state_file=args.job/'session_monitor_state.json')
        mon.record_worker_active('source-preflight',1,1,message='SOURCE PREFLIGHT')
        result=preflight(args.book_dir,args.job,args.through_chapter,repair_sources=args.repair_sources,
            progress_callback=lambda done,total:print(f'Source preflight {done}/{total}',flush=True))
        mon.record_stage_result(1,'source-preflight','source-preflight',result['status']);print(mon.render_markdown_badge(),flush=True)
        print(json.dumps(result,ensure_ascii=False));return
    if args.action=='retry-ready':
        print(json.dumps(NativeRecovery(args.job).release_after_action(args.reason),ensure_ascii=False));return
    if args.action in ('report','seal'):
        from native_oauth.resilient_reporting import report,seal
        if args.action=='seal':
            if not args.out:parser.error('seal requires --out ZIP path')
            result=seal(args.book_dir,args.job,args.through_chapter,args.out)
        else:result=report(args.book_dir,args.job,args.through_chapter)
        print(json.dumps(result,ensure_ascii=False));return
    if args.action in ('status','export'):
        result=progress(args.book_dir,args.through_chapter)
        if args.action=='export':
            if not args.out or not result['export_ready']:raise ValueError('Export requires complete verified approval range and --out')
            if (args.book_dir/'toc.json').exists() and args.through_chapter!=len(read_json(args.book_dir/'toc.json')):
                raise ValueError('Full-book export requires the entire TOC, not a completed pilot prefix')
            from native_oauth.resilient_publication import read_approval
            atomic_json(args.out,{'chapters':[read_approval(args.book_dir,ch)['rendered'] for ch in range(1,args.through_chapter+1)]})
        print(json.dumps(result,ensure_ascii=False));return
    import os
    if not (os.environ.get('ANTIGRAVITY_ARTIFACT_DIR') or os.environ.get('ANTIGRAVITY_CONVERSATION_ID')):
        raise ValueError('Bind the current real Antigravity session before native execution')
    options=dict(workers=args.workers,model=args.model,
        review_model=args.review_model,review_model2=args.auditor_model,fallback=args.fallback_model,timeout=args.timeout,
        checkpoint_every=args.checkpoint_every,review_workers=args.review_workers)
    runner=(launch_runner(args.book_dir,args.job,args.through_chapter,**options) if args.action=='launch'
            else Runner(args.book_dir,args.job,args.through_chapter,**options))
    if args.action=='launch' and args.source_recovery_dir:import_replacements(args.book_dir,runner.job,args.source_recovery_dir)
    if args.action=='diagnose':
        if not args.chapters or any(ch<1 or ch>args.through_chapter for ch in args.chapters):parser.error('diagnose requires --chapters within the source range')
        result=runner.diagnose(args.chapters,repair_sources=not args.no_source_refetch)
        print(json.dumps(result,ensure_ascii=False))
        if result['status']!='DIAGNOSTIC_PASS_NOT_APPROVAL':raise SystemExit(2)
        return
    for turn in range(args.watch_rounds if args.action in ('watch','launch') else 1):
        result=runner.run(repair_sources=not args.no_source_refetch)
        if result['export_ready'] or args.action not in ('watch','launch'):break
        if turn+1<args.watch_rounds:
            waits=[read_json(p).get('retry_after_epoch',time.time()) for p in (runner.job/'recovery').glob('*.json')
                   if read_json(p).get('kind') in ('QUOTA','NETWORK','TIMEOUT') and read_json(p).get('status')=='PENDING']
            wait_until=min(waits) if waits else time.time()+30
            while time.time()<wait_until:
                runner.badge('recovery-wait','WAITING_RETRY; checkpoint preserved')
                time.sleep(min(30,max(0.1,wait_until-time.time())))
    print(json.dumps(result,ensure_ascii=False))
    if not result['export_ready']:raise SystemExit(2)


def cli():
    try:main()
    except WorkflowGateError as error:
        print(json.dumps({'status':'WORKFLOW_BLOCKED','reason':str(error),'next_action':error.action},ensure_ascii=False))
        raise SystemExit(2)


if __name__=='__main__':cli()
