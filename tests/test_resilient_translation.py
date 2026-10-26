"""Offline failure-injection tests; no actual CLI, model or network calls."""
import contextlib
import copy
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from semantic_gate import digest, read_json, write_json, CHECKS, LITERARY_CHECKS
from native_test_helpers import native_runtime, bind_artifact
from native_oauth.resilient_translation import Runner,translation_view,context_view
from native_oauth.resilient_gate import validate_batch_evidence, validate_compact_review, ProtocolFailure
from native_oauth.resilient_publication import manifest, progress, validate_manifest, read_approval
from native_oauth.book_publication import load_approved_chapters
from native_oauth.recovery_sources import preflight, source_context, reacquire, fetch_alternate, import_replacements

ROOT=Path(__file__).resolve().parents[1]


class ResilientTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.book=self.root/'book_fixture';self.job=self.root/'job'
        self.calls=[];self.mode='normal';self.fail_chapter=1;self.review_inputs=[];self.requests_seen=[];self.reviewer_barrier=None
        self.sources={}
        for ch in range(1,6):self.add_source(ch,4)
        write_json(self.book/'toc.json',[{'href':f'https://czbooks.net/n/fixture/c{ch}','title':f'第{ch}章 測試'} for ch in range(1,6)])
        write_json(self.book/'lore.json',{'book_id':'fixture','genre':'hien_dai'})
        stack=contextlib.ExitStack();self.addCleanup(stack.close)
        stack.enter_context(patch('native_oauth.resilient_translation.get_session_monitor',return_value=Mock()))
        stack.enter_context(patch('native_oauth.pipeline_native.run_stage',side_effect=self.stage))
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def add_source(self,ch,count):
        source={'version':'bns-source-v1','book_id':'fixture','chapter':ch,'title':f'第{ch}章 測試',
            'source_ref':'fixture','paragraph_count':count,'segments':[
                {'id':f'c{ch:04d}p{i:04d}','source':f'第{ch}章 測試' if i==1 else '他不甘心。'} for i in range(1,count+1)]}
        source['package_hash']=digest(source)
        write_json(self.book/'sources'/f'source_chapter_{ch:04d}.json',source);self.sources[ch]=source

    def runner(self,through=5,**kwargs):
        return Runner(self.book,self.job,through,workers=2,model='fixture',review_model='fixture',fallback='fixture-high',**kwargs)

    def stage(self,data,work,role,model,protocol,output,timeout):
        packet=read_json(Path(data)/'source.json');self.calls.append((role,packet['chapter'],model))
        self.requests_seen.append({'role':role,'model':model,'packet':copy.deepcopy(packet),'workspace':str(work)})
        if role=='translator':
            if self.mode=='native-block':
                write_json(Path(data)/(role+'.runtime/runtime.json'),{'status':'SUCCESS','result':{'finish_reason':'safety'}})
                raise ValueError('Native response blocked or truncated')
            if self.mode=='quota' and packet['chapter']==self.fail_chapter:raise ValueError('429 quota exhausted')
            if self.mode=='access' and packet['chapter']==self.fail_chapter:raise ValueError('403 permission denied')
            if self.mode=='all-timeout':raise TimeoutError('Native output timeout')
            if self.mode=='network' and packet['chapter']==self.fail_chapter:raise ConnectionError('Connection reset by peer')
            if self.mode=='timeout' and len(packet['segments'])>35:raise TimeoutError('Native output timeout')
            rows=[];script_quotes=[]
            for row in packet['segments']:
                text=f"Chương {packet['chapter']}: Thử nghiệm" if row['id'].endswith('p0001') else 'Anh ấy không cam lòng.'
                if self.mode=='semantic' and packet['chapter']==1 and row['id'].endswith('p0002') and 'SOURCE_BOUND_FINDINGS_TO_RECHECK' not in protocol:
                    text='Anh ấy cam chịu.'
                if self.mode=='persistent' and packet['chapter']==1 and row['id'].endswith('p0002'):text='Anh ấy cam chịu.'
                if self.mode=='residual' and row['id'].endswith('p0002') and 'SOURCE_BOUND_FINDINGS_TO_RECHECK' not in protocol:
                    text='Anh ấy 普遍 không cam lòng.'
                if self.mode=='bad-id' and len(packet['segments'])>1 and row['id']==packet['segments'][-1]['id']:
                    row={**row,'id':'c9999p9999'}
                if row['source']=='林御摇头。':
                    text='Hắn lắc đầu.'
                    if self.mode=='wrong-entity' and 'SOURCE_BOUND_FINDINGS_TO_RECHECK' not in protocol:text='Trương Vũ lắc đầu.'
                if row['source']=='他指着“人”字。':
                    text='Hắn chỉ vào chữ “人”.'
                    script_quotes.append({'id':row['id'],'quote':'人','reason':'The source discusses this written character'})
                rows.append({'id':row['id'],'text':text})
            value={'package_hash':packet['package_hash'],'segments':rows}
            if script_quotes:value['source_script_quotes']=script_quotes
            if packet.get('metadata_title_source'):
                value['title_vi']='Chương 1: Tỏ tình'
        else:
            if self.reviewer_barrier:self.reviewer_barrier.wait(timeout=10)
            if self.mode=='review-network' and role=='meaning-reviewer':raise ConnectionError('Connection reset by peer')
            self.review_inputs.append((role,copy.deepcopy(packet)))
            if self.mode=='format' and len(packet['scope_slots'])>60:
                rows=[['c0100p0100','PASS']]
            else:
                rows=[[slot,'PASS'] for slot in packet['scope_slots']]
            issues=[]
            for row in rows:
                if type(row[0]) is int and packet['catalog'][row[0]-1]['target']=='Anh ấy cam chịu.':
                    row[1]='FAIL';issues.append({'slot':row[0],'source_ref':0,'target_ref':0,'kind':'negation_modality',
                        'reason':'不甘 is unwillingness to accept, not acceptance'})
                if type(row[0]) is int and packet['catalog'][row[0]-1]['target']=='Trương Vũ lắc đầu.':
                    row[1]='FAIL';issues.append({'slot':row[0],'source_ref':0,'target_ref':0,'kind':'entities',
                        'reason':'林御 is Lâm Ngự, not Trương Vũ'})
            value={'package_hash':packet['package_hash'],'verdict':'FAIL' if issues else 'PASS',
                   'checks':dict.fromkeys(CHECKS,True),'literary_checks':dict.fromkeys(LITERARY_CHECKS,True),
                   'rows':rows,'issues':issues}
            if packet.get('review_policy'):
                value['semantic_obligations_checked']=[slot for slot in packet['scope_slots'] if packet['catalog'][slot-1].get('review_obligations')]
            if self.mode=='style-suggestion':
                value['suggestions']=[{'slot':packet['scope_slots'][0],'source_ref':0,'target_ref':0,'kind':'style','reason':'Optional shorter wording'}]
        response=json.dumps(value,ensure_ascii=False)
        record=native_runtime(Path(work)/'proof',model=model)
        runtime_path=Path(record['file']);runtime=read_json(runtime_path);runtime['result']['response']=response
        write_json(runtime_path,runtime)
        events=[{'event':'init','conversation_id':runtime['conversation_id'],'init':{'model':model}},
                {'event':'result','result':runtime['result']}]
        runtime_path.with_name('events.jsonl').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf8')
        from native_oauth.native_evidence import runtime_record,artifact_record
        value.update(model='native/'+model,identity_basis='native_cli_init',native_response_binding='json',
                     native_runtimes=[runtime_record(runtime_path,model)])
        original=Path(data)/'response.native-original.json';original.write_text(response,encoding='utf8')
        value['native_artifact']=artifact_record(original,value)
        write_json(Path(data)/output,value)
        return value

    def test_five_chapters_need_seven_native_calls_and_export_is_source_bound(self):
        result=self.runner().run(repair_sources=False)
        self.assertTrue(result['export_ready']);self.assertEqual(len(self.calls),7)
        self.assertEqual(len(load_approved_chapters(self.book,range(1,6))),5)
        self.assertEqual(len(manifest(self.book)['batches']),1)
        for source in self.sources.values():
            self.assertEqual(read_json(self.book/'sources'/f"source_chapter_{source['chapter']:04d}.json"),source)

    def test_resume_completed_batch_makes_no_model_calls(self):
        self.runner().run(repair_sources=False);before=len(self.calls)
        self.assertTrue(self.runner().run(repair_sources=False)['export_ready'])
        self.assertEqual(len(self.calls),before)

    def test_two_reviewers_overlap_but_keep_independent_workspaces_and_fixed_role_order(self):
        self.reviewer_barrier=threading.Barrier(2)
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        evidence=read_approval(self.book,1)['evidence']
        self.assertEqual([row['role'] for row in evidence['reviews']],['meaning-reviewer','literary-reviewer'])
        requests=[row for row in self.requests_seen if row['role']!='translator']
        self.assertEqual(len(set(row['workspace'] for row in requests)),2)
        self.assertTrue(all('reviews' not in row['packet'] for row in requests))

    def test_serial_review_is_an_explicit_option_and_still_needs_two_native_reviews(self):
        self.assertTrue(self.runner(1,review_workers=1).run(repair_sources=False)['export_ready'])
        self.assertEqual(sum(role!='translator' for role,_,_ in self.calls),2)

    def test_one_bad_row_reuses_exact_good_native_rows_and_high_sees_only_bad_id(self):
        self.mode='residual'
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        requests=[r for r in self.requests_seen if r['role']=='translator']
        self.assertEqual(len(requests),2)
        self.assertEqual([r['id'] for r in requests[1]['packet']['segments']],['c0001p0002'])
        self.assertEqual(requests[1]['model'],'fixture-high')
        item=read_approval(self.book,1)['evidence']['package']['chapters'][0];candidate=read_json(item['candidate_file'])
        self.assertEqual(len(candidate['components']),2)
        retained=candidate['components'][0];original=read_json(retained['file'])
        self.assertIn('普遍',original['segments'][1]['text'])
        self.assertNotIn('c0001p0002',retained['ids'])
        for row in candidate['segments']:
            if row['id'] in retained['ids']:
                self.assertEqual(row['text'],next(r['text'] for r in original['segments'] if r['id']==row['id']))
        self.assertNotIn('普遍',candidate['segments'][1]['text'])
        self.assertEqual(len(self.calls),4)

    def test_content_repair_replays_after_interruption_without_regenerating_whole_chapter(self):
        self.mode='residual';runner=self.runner(1);preflight(self.book,self.job,1)
        from native_oauth.resilient_translation import atomic_json as original_write
        def interrupted_write(path,value):
            if Path(path).parent.name=='drafts':raise RuntimeError('Simulated interruption before draft pointer')
            return original_write(path,value)
        with patch('native_oauth.resilient_translation.atomic_json',side_effect=interrupted_write):
            with self.assertRaisesRegex(RuntimeError,'Simulated interruption'):runner.generate(1)
        before=sum(role=='translator' for role,_,_ in self.calls)
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        self.assertEqual(sum(role=='translator' for role,_,_ in self.calls),before)

    def test_invalid_ids_cannot_be_retained_as_source_owned_content(self):
        self.mode='bad-id';self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        self.assertTrue(all('content_artifact' not in read_json(path) for path in (self.job/'recovery').glob('*.json')))
        self.assertEqual([r['para_id'] for r in read_approval(self.book,1)['aligned']['bilingual_alignment']],
            [r['id'] for r in self.sources[1]['segments']])

    def test_tampered_retained_native_response_blocks_resume_without_new_model_calls(self):
        self.mode='residual';runner=self.runner(1);preflight(self.book,self.job,1)
        from native_oauth.resilient_translation import atomic_json as original_write
        def interrupted_write(path,value):
            if Path(path).parent.name=='drafts':raise RuntimeError('Simulated interruption')
            return original_write(path,value)
        with patch('native_oauth.resilient_translation.atomic_json',side_effect=interrupted_write):
            with self.assertRaises(RuntimeError):runner.generate(1)
        state=next(read_json(path) for path in (self.job/'recovery').glob('*.json') if read_json(path).get('content_artifact'))
        value=read_json(state['content_artifact']);value['segments'][0]['text']='Host altered native output'
        write_json(state['content_artifact'],value);before=len(self.calls)
        self.assertFalse(self.runner(1).run(repair_sources=False)['export_ready'])
        self.assertEqual(len(self.calls),before)

    def test_failed_parallel_review_keeps_successful_peer_for_resume(self):
        self.mode='review-network';runner=self.runner(1)
        self.assertFalse(runner.run(repair_sources=False)['export_ready'])
        peer_before=sum(role=='literary-reviewer' for role,_,_ in self.calls)
        self.assertTrue(runner.native.release_after_action('Network restored in offline fixture'))
        self.mode='normal';self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        self.assertEqual(sum(role=='literary-reviewer' for role,_,_ in self.calls),peer_before)
        self.assertEqual(sum(role=='translator' for role,_,_ in self.calls),1)

    def test_checkpoints_bound_batches_without_another_native_review(self):
        self.assertTrue(self.runner(checkpoint_every=3).run(repair_sources=False)['export_ready'])
        self.assertEqual([r['chapters'] for r in manifest(self.book)['batches'].values()],[[1,2,3],[4,5]])
        self.assertEqual(len(self.calls),9)
        self.assertEqual(read_json(self.job/'checkpoints/chapter_0003.json')['next_chapter'],4)
        self.assertIsNone(read_json(self.job/'checkpoints/chapter_0005.json')['next_chapter'])

    def test_two_batches_bind_real_predecessor_context_without_recursive_approval(self):
        for ch in range(6,11):self.add_source(ch,4)
        write_json(self.book/'toc.json',[{}]*10)
        self.assertTrue(self.runner(10).run(repair_sources=False)['export_ready'])
        self.assertEqual(len(manifest(self.book)['batches']),2)
        evidence=read_approval(self.book,6)['evidence']
        self.assertEqual(evidence['package']['prefix']['through_chapter'],5)
        self.assertTrue(evidence['package']['approved_context'])
        self.assertTrue(all(r['chapter']==5 for r in evidence['package']['approved_context']))

    def test_semantic_fail_creates_focused_native_revision_and_two_fresh_reviews(self):
        self.mode='semantic';result=self.runner().run(repair_sources=False)
        self.assertTrue(result['export_ready'])
        item=read_approval(self.book,1)
        self.assertEqual(item['aligned']['bilingual_alignment'][1]['translated_vi'],'Anh ấy không cam lòng.')
        self.assertEqual(len(list((self.job/'candidate_revisions/0001').glob('*.json'))),2)
        self.assertEqual(sum(role!='translator' for role,_,_ in self.calls),4)
        self.assertEqual(len(item['evidence']['package']['chapters'][0]['source_packet']['segments']),4)
        self.assertEqual(len(item['evidence']['reviews']),2)

    def named_source(self):
        source=copy.deepcopy(self.sources[1]);source['segments'][1]['source']='林御摇头。'
        source.pop('package_hash');source['package_hash']=digest(source)
        write_json(self.book/'sources/source_chapter_0001.json',source)
        write_json(self.book/'lore.json',{'book_id':'fixture','characters':{'林御':'Lâm Ngự'}})

    def test_correct_pronoun_has_no_high_retry_and_both_reviewers_cover_entity(self):
        self.named_source();self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        self.assertEqual(len(self.calls),3)
        self.assertTrue(all(model=='fixture' for _,_,model in self.calls))
        for _,packet in self.review_inputs:
            self.assertTrue(packet['catalog'][1]['review_obligations'])
        self.assertEqual(read_approval(self.book,1)['aligned']['bilingual_alignment'][1]['translated_vi'],'Hắn lắc đầu.')

    def test_wrong_person_still_fails_then_requires_real_repair_and_two_fresh_reviews(self):
        self.named_source();self.mode='wrong-entity'
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        self.assertEqual(sum(role!='translator' for role,_,_ in self.calls),4)
        self.assertTrue(any(model=='fixture-high' for _,_,model in self.calls))
        self.assertEqual(len(list((self.job/'candidate_revisions/0001').glob('*.json'))),2)

    def test_source_script_quote_keeps_native_ownership_through_targeted_repair(self):
        source=copy.deepcopy(self.sources[1]);source['segments'][2]['source']='他指着“人”字。'
        source.pop('package_hash');source['package_hash']=digest(source)
        write_json(self.book/'sources/source_chapter_0001.json',source);self.mode='semantic'
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        item=read_approval(self.book,1);candidate=read_json(item['evidence']['package']['chapters'][0]['candidate_file'])
        self.assertEqual(candidate['source_script_quotes'][0]['quote'],'人')
        self.assertEqual(len(candidate['source_script_quotes']),1)
        self.assertEqual(candidate['segments'][2]['text'],'Hắn chỉ vào chữ “人”.')
        self.assertTrue(item['evidence']['package']['catalog'][2]['review_obligations'])

    def test_optional_style_suggestions_are_retained_without_regeneration(self):
        self.mode='style-suggestion'
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        self.assertEqual(len(self.calls),3)
        result=validate_batch_evidence(read_approval(self.book,1)['evidence'])
        self.assertEqual(result['status'],'PASS');self.assertEqual(len(result['suggestions']),2)

    def test_timeout_splits_output_keeps_all_ids_and_recovers(self):
        self.add_source(1,80);self.mode='timeout'
        result=self.runner(1).run(repair_sources=False)
        self.assertTrue(result['export_ready'])
        entry=read_json(read_approval(self.book,1)['evidence']['package']['chapters'][0]['candidate_file'])
        self.assertEqual(len(entry['components']),3)
        self.assertEqual([r['id'] for r in entry['segments']],[r['id'] for r in self.sources[1]['segments']])
        self.assertTrue(any(read_json(p).get('status')=='RECOVERED_BY_SUBTASKS' for p in (self.job/'recovery').glob('*.json')))

    def test_timeout_during_focused_repair_splits_repairs_and_still_requires_both_reviews(self):
        self.mode='semantic';runner=self.runner(1);preflight(self.book,self.job,1)
        item=runner.generate(1)
        findings=[{'id':f'c0001p{n:04d}','kind':'negation_modality','reason':'Recheck unwillingness against source'} for n in (2,3)]
        def repair_stage(data,work,role,model,protocol,output,timeout):
            packet=read_json(Path(data)/'source.json')
            if role=='translator' and 'SOURCE_BOUND_FINDINGS_TO_RECHECK' in protocol and len(packet['segments'])>1:
                raise TimeoutError('Repair output timeout')
            return self.stage(data,work,role,model,protocol,output,timeout)
        with patch('native_oauth.pipeline_native.run_stage',side_effect=repair_stage):
            fixed=runner.repair(item,findings,1)
        candidate=read_json(fixed['candidate_file'])
        self.assertEqual([r['id'] for r in candidate['segments']],[r['id'] for r in self.sources[1]['segments']])
        self.assertEqual(candidate['segments'][1]['text'],'Anh ấy không cam lòng.')
        self.assertFalse(manifest(self.book)['chapters'])
        self.assertTrue(runner.run(repair_sources=False)['export_ready'])
        self.assertEqual(sum(role!='translator' for role,_,_ in self.calls),2)
        self.assertTrue(any(read_json(p).get('status')=='RECOVERED_BY_SUBTASKS' for p in (self.job/'recovery').glob('*.json')))

    def test_bad_review_format_falls_back_to_smaller_coverage_without_editing_verdict(self):
        self.add_source(1,80);self.mode='format'
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        evidence=read_approval(self.book,1)['evidence']
        self.assertTrue(all(len(role['parts'])==2 for role in evidence['reviews']))
        self.assertEqual(validate_batch_evidence(evidence)['status'],'PASS')

    def test_quota_is_durable_stops_hammering_and_resume_reuses_completed_drafts(self):
        self.mode='quota';result=self.runner().run(repair_sources=False)
        self.assertFalse(result['export_ready']);cached=len(list((self.job/'drafts').glob('*.json')))
        state=read_json(self.job/'campaign.json')
        self.assertTrue(any('WAIT_FOR_QUOTA' in r.get('action','') for r in state['next_actions']))
        for p in (self.job/'recovery').glob('*.json'):
            value=read_json(p)
            if value.get('kind')=='QUOTA':value['retry_after_epoch']=0;write_json(p,value)
        health=read_json(self.job/'transport_health.json');health['open_until']=0;write_json(self.job/'transport_health.json',health)
        before=len(self.calls);self.mode='normal'
        self.assertTrue(self.runner().run(repair_sources=False)['export_ready'])
        self.assertEqual(len(self.calls)-before,5-cached+2)

    def test_local_network_failure_preserves_other_drafts(self):
        self.mode='network';result=self.runner().run(repair_sources=False)
        self.assertFalse(result['export_ready'])
        self.assertEqual(len(list((self.job/'drafts').glob('*.json'))),4)

    def test_repeated_transport_timeouts_open_circuit_and_reduce_workers(self):
        self.mode='all-timeout';result=self.runner().run(repair_sources=False)
        self.assertFalse(result['export_ready'])
        health=read_json(self.job/'transport_health.json')
        self.assertEqual(health['worker_limit'],1)
        self.assertGreater(health['open_until'],0)
        self.assertLessEqual(len(self.calls),6)

    def test_permission_never_becomes_empty_findings_or_fake_pass(self):
        self.mode='access';result=self.runner(1).run(repair_sources=False)
        self.assertFalse(result['export_ready'])
        self.assertEqual(len(self.calls),1)
        self.assertTrue(any(read_json(p).get('action')=='RESTORE_NATIVE_AUTH_OR_PERMISSION' for p in (self.job/'recovery').glob('*.json')))

    def test_native_block_is_not_misclassified_as_timeout_and_split_to_bypass(self):
        self.mode='native-block';result=self.runner(1).run(repair_sources=False)
        self.assertFalse(result['export_ready']);self.assertEqual(len(self.calls),1)
        self.assertTrue(any(read_json(p).get('kind')=='NATIVE_BLOCKED' for p in (self.job/'recovery').glob('*.json')))

    def test_restored_access_can_be_released_and_resumed_without_resetting_proofs(self):
        self.mode='access';runner=self.runner(1);runner.run(repair_sources=False)
        self.assertTrue(runner.native.release_after_action('Native authentication was restored'))
        self.mode='normal';self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        self.assertTrue(any(read_json(p).get('operator_actions') for p in (self.job/'recovery').glob('*.json')))

    def test_changed_native_output_or_source_revokes_approval(self):
        result=self.runner().run(repair_sources=False)
        self.assertTrue(result['export_ready'],read_json(self.job/'campaign.json'))
        entry=read_approval(self.book,1);candidate_path=Path(entry['evidence']['package']['chapters'][0]['candidate_file'])
        saved=candidate_path.read_bytes();candidate=read_json(candidate_path);candidate['segments'][1]['text']='Changed'
        write_json(candidate_path,candidate)
        self.assertFalse(progress(self.book,5)['export_ready']);candidate_path.write_bytes(saved)
        source=self.sources[1];source['segments'][1]['source']='他甘心。';source.pop('package_hash');source['package_hash']=digest(source)
        write_json(self.book/'sources/source_chapter_0001.json',source)
        self.assertFalse(progress(self.book,5)['export_ready'])

    def test_persistent_content_failure_is_queued_without_publishing(self):
        self.mode='persistent';result=self.runner(1,max_repairs=1).run(repair_sources=False)
        self.assertFalse(result['export_ready']);self.assertEqual(len(manifest(self.book)['chapters']),0)
        self.assertTrue(read_json(self.job/'campaign.json')['next_actions'])
        self.assertEqual(sum(role!='translator' for role,_,_ in self.calls),2)

    def test_missing_source_gets_explicit_recovery_and_does_not_lose_other_chapters(self):
        path=self.book/'sources/source_chapter_0001.json';path.unlink()
        result=self.runner().run(repair_sources=False)
        self.assertFalse(result['export_ready'])
        self.assertEqual(len(list((self.job/'drafts').glob('*.json'))),4,read_json(self.job/'campaign.json'))
        report=read_json(self.job/'source_preflight.json')
        self.assertEqual(report['pending'][0]['action'],'REACQUIRE_FROM_TOC_OR_VERIFIED_ALTERNATE')

    def test_source_index_is_never_a_trusted_approval(self):
        preflight(self.book,self.job,5)
        import sqlite3
        db=sqlite3.connect(self.job/'source_index.sqlite');db.execute("UPDATE paragraphs SET source='Fake' WHERE chapter=1");db.commit();db.close()
        with self.assertRaisesRegex(ValueError,'index'):source_context(self.job,2)

    def test_model_view_keeps_all_assigned_source_and_literal_context_without_host_paths(self):
        preflight(self.book,self.job,5);runner=self.runner();packet=runner.packet(3)
        view=translation_view(packet)
        self.assertEqual(view['segments'],packet['segments'])
        expected={(r['id'],r['source']) for r in packet['earlier_original_read_only']}
        actual={(r['id'],r['source']) for group in view['earlier_original_read_only'] for r in group['segments']}
        self.assertEqual(actual,expected)
        self.assertNotIn(str(self.job),json.dumps(view,ensure_ascii=False))
        self.assertNotIn('native_bound_files',view)
        self.assertEqual(view['package_hash'],packet['package_hash'])

    def test_compact_context_preserves_source_revision_and_chapter_scope(self):
        rows=[{'chapter':1,'source_hash':'h','id':'c0001p0001','source':'她走了。','for_chapter':2},
              {'chapter':1,'source_hash':'h','id':'c0001p0001','source':'她走了。','for_chapter':3}]
        view=context_view(rows)
        self.assertEqual(len(view),1);self.assertEqual(view[0]['for_chapters'],[2,3])
        self.assertEqual(view[0]['segments'],[{'id':'c0001p0001','source':'她走了。'}])

    def test_compact_review_rejects_missing_coverage_and_false_pass(self):
        self.runner(1).run(repair_sources=False)
        packet=self.review_inputs[0][1]
        value={'package_hash':packet['package_hash'],'verdict':'PASS','checks':dict.fromkeys(CHECKS,True),
            'literary_checks':dict.fromkeys(LITERARY_CHECKS,True),'rows':[[s,'PASS'] for s in packet['scope_slots']], 'issues':[],
            'semantic_obligations_checked':[s for s in packet['scope_slots'] if packet['catalog'][s-1].get('review_obligations')]}
        validate_compact_review(packet,value)
        value['rows'].pop()
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet,value)

    def test_verified_refetch_preserves_original_and_creates_replayable_source_revision(self):
        (ROOT/'source_archive').mkdir(exist_ok=True)
        archive=tempfile.TemporaryDirectory(prefix='book_recoverytest_',dir=ROOT/'source_archive');self.addCleanup(archive.cleanup)
        book_id=Path(archive.name).name.removeprefix('book_')
        old=copy.deepcopy(self.sources[1]);old['book_id']=book_id;old.pop('package_hash');old['package_hash']=digest(old)
        write_json(self.book/'lore.json',{'book_id':book_id})
        original=self.book/'sources/source_chapter_0001.json';write_json(original,old);before=original.read_bytes()
        html='<div class="name">《測試》第1章 測試</div><div class="content"><p>他走了。</p><p>她沒有來。</p></div>'
        from native_oauth.source_adapters import extract_paragraphs
        with patch('native_oauth.recovery_sources.fetch_czbooks',return_value=(extract_paragraphs(html),html.encode('utf8'))):
            reacquire(self.book,self.job,1)
        replacement=read_json(self.job/'effective_sources/source_chapter_0001.json')
        from native_oauth.chapter_integrity import validate_source,validate_source_archive
        validate_source(replacement);validate_source_archive(replacement)
        self.assertEqual(original.read_bytes(),before)
        self.assertEqual(replacement['recovery_lineage']['previous_package_hash'],old['package_hash'])
        other=self.root/'other_job'
        self.assertEqual(import_replacements(self.book,other,self.job/'effective_sources'),[1])
        self.assertEqual((other/'effective_sources/source_chapter_0001.json').read_bytes(),(self.job/'effective_sources/source_chapter_0001.json').read_bytes())
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        from native_oauth.resilient_reporting import seal
        import zipfile
        unused=copy.deepcopy(self.sources[2]);unused['book_id']=book_id;unused.pop('package_hash');unused['package_hash']=digest(unused)
        original_unused=self.book/'sources/source_chapter_0002.json';write_json(original_unused,unused)
        html2=html.replace('第1章','第2章')
        with patch('native_oauth.recovery_sources.fetch_czbooks',return_value=(extract_paragraphs(html2),html2.encode('utf8'))):
            reacquire(self.book,self.job,2)
        unused_replacement=read_json(self.job/'effective_sources/source_chapter_0002.json')
        unused_raw=ROOT/'source_archive'/('book_'+book_id)/unused_replacement['raw_archive']
        out=self.root/'source_lineage.zip';seal(self.book,self.job,1,out)
        with zipfile.ZipFile(out) as bundle:
            sealed=json.loads(bundle.read('manifest.json'))
            originals=[entry for entry in sealed.values() if entry['original_path']==str(original.resolve())]
            self.assertTrue(originals)
            paths={entry['original_path'] for entry in sealed.values()}
            self.assertIn(str(original_unused.resolve()),paths)
            self.assertIn(str(unused_raw.resolve()),paths)

    def test_separate_archived_title_is_reviewed_without_inserting_body_ids(self):
        from test_final_translation_pilot import SeparateTitleTests
        fixture=SeparateTitleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        write_json(self.book/'sources/source_chapter_0001.json',fixture.source)
        write_json(self.book/'lore.json',{'book_id':fixture.source['book_id']})
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        item=read_approval(self.book,1)
        self.assertEqual(item['rendered']['title'],'Chương 1: Tỏ tình')
        self.assertEqual(len(item['rendered']['paragraphs']),len(fixture.source['segments']))
        self.assertEqual(item['evidence']['package']['catalog'][0]['id'],'c0001title')

    def test_completed_native_artifact_is_replayed_after_journal_interruption(self):
        self.runner(1).run(repair_sources=False);before=len(self.calls)
        for path in (self.job/'recovery').glob('*.json'):
            state=read_json(path)
            if state.get('status')=='DONE':state['status']='RUNNING';write_json(path,state)
        # Remove publication and the draft pointer, preserving native evidence.
        (self.book/'approved/resilient_manifest.json').unlink();(self.job/'drafts/0001.json').unlink()
        self.assertTrue(self.runner(1).run(repair_sources=False)['export_ready'])
        self.assertEqual(len(self.calls),before)

    def test_metrics_and_seal_preserve_missing_usage_and_every_hash(self):
        result=self.runner().run(repair_sources=False)
        self.assertTrue(result['export_ready'],read_json(self.job/'campaign.json'))
        from native_oauth.resilient_reporting import report,seal
        import zipfile,hashlib
        metrics=report(self.book,self.job,5)
        self.assertTrue(metrics['progress']['export_ready']);self.assertIsNone(metrics['token_totals']['total_tokens'])
        self.assertGreater(metrics['active_wall_seconds'],0)
        import csv
        with (self.job/'chapter_metrics.csv').open(encoding='utf-8-sig',newline='') as handle:
            chapter_rows=list(csv.DictReader(handle))
        self.assertEqual(len(chapter_rows),5)
        self.assertTrue(all(row['status']=='APPROVED' and float(row['elapsed_until_approval_seconds'])>=0 for row in chapter_rows))
        self.assertTrue(all(abs(float(row['draft_elapsed_seconds'])+float(row['post_draft_elapsed_seconds'])
            -float(row['elapsed_until_approval_seconds']))<0.000001 for row in chapter_rows))
        self.assertEqual(int(chapter_rows[0]['source_characters']),sum(len(r['source']) for r in self.sources[1]['segments']))
        out=self.root/'bundle.zip';sealed=seal(self.book,self.job,5,out)
        self.assertEqual(sealed['sha256'],hashlib.sha256(out.read_bytes()).hexdigest())
        with zipfile.ZipFile(out) as archive:
            checks=json.loads(archive.read('manifest.json'))
            self.assertTrue(all(hashlib.sha256(archive.read(name)).hexdigest()==entry['sha256'] for name,entry in checks.items()))
        with self.assertRaises(ValueError):seal(self.book,self.job,5,out)

    def test_new_job_bundle_keeps_native_dependencies_of_previously_approved_prefix(self):
        self.assertTrue(self.runner().run(repair_sources=False)['export_ready'])
        old=read_approval(self.book,1)['evidence']['package']['chapters'][0]
        old_runtime=read_json(read_json(old['candidate_file'])['components'][0]['file'])['native_runtimes'][0]['file']
        for ch in range(6,11):self.add_source(ch,4)
        write_json(self.book/'toc.json',[{}]*10)
        new_job=self.root/'next_job'
        runner=Runner(self.book,new_job,10,workers=2,model='fixture',review_model='fixture',fallback='fixture-high')
        self.assertTrue(runner.run(repair_sources=False)['export_ready'])
        from native_oauth.resilient_reporting import seal,report
        metrics=report(self.book,new_job,10)
        self.assertEqual(metrics['job_approved_chapters'],list(range(6,11)))
        expected=sum(len(row['source']) for ch in range(6,11) for row in self.sources[ch]['segments'])
        self.assertEqual(metrics['job_approved_source_characters'],expected)
        self.assertAlmostEqual(metrics['approved_source_chars_per_hour'],expected*3600/metrics['active_wall_seconds'])
        import zipfile
        out=self.root/'continued_prefix.zip';seal(self.book,new_job,10,out)
        with zipfile.ZipFile(out) as archive:
            checks=json.loads(archive.read('manifest.json'))
            self.assertIn(str(Path(old_runtime).resolve()),[r['original_path'] for r in checks.values()])

    def test_server_supplied_browser_redirect_stays_same_origin(self):
        url='https://ixdzs8.com/read/644367/p350.html'
        challenge=b'<title>\xe6\xad\xa3\xe5\x9c\xa8\xe9\xaa\x8c\xe8\xaf\x81\xe6\xb5\x8f\xe8\xa7\x88\xe5\x99\xa8</title><script>let token = "server_signed_token"; window.location.href = location.pathname + "?challenge=" + encodeURIComponent(token);</script>'
        raw='<h1 class="page-d-name">第350章 測試</h1>'.encode('utf8')
        first=Mock();first.__enter__=Mock(return_value=first);first.__exit__=Mock(return_value=False)
        first.geturl.return_value=url;first.read.return_value=challenge
        second=Mock();second.__enter__=Mock(return_value=second);second.__exit__=Mock(return_value=False)
        second.geturl.return_value=url+'?challenge=server_signed_token';second.read.return_value=raw
        opener=Mock();opener.open.side_effect=[first,second]
        with patch('native_oauth.recovery_sources.urllib.request.build_opener',return_value=opener):
            self.assertEqual(fetch_alternate(url),raw)
        self.assertEqual(opener.open.call_args_list[1].args[0].full_url,url+'?challenge=server_signed_token')
        opener.open.side_effect=[first];first.geturl.return_value='https://another.example/read/1'
        with patch('native_oauth.recovery_sources.urllib.request.build_opener',return_value=opener):
            with self.assertRaisesRegex(ValueError,'redirected away'):fetch_alternate(url)

    def test_source_only_diagnostic_repairs_but_never_publishes_even_chapter_one(self):
        self.mode='semantic';result=self.runner().diagnose([1,3],repair_sources=False)
        self.assertEqual(result['status'],'DIAGNOSTIC_PASS_NOT_APPROVAL')
        self.assertFalse(result['approval_eligible']);self.assertEqual(manifest(self.book)['chapters'],{})
        from native_oauth.resilient_publication import commit
        with self.assertRaisesRegex(ValueError,'Diagnostic'):commit(self.book,result['chapters'][0]['evidence'])

    def test_archive_cache_still_detects_changed_raw_bytes_and_parser(self):
        from test_final_translation_pilot import SeparateTitleTests
        from native_oauth.chapter_integrity import validate_source_archive
        fixture=SeparateTitleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        validate_source_archive(fixture.source)
        with patch('native_oauth.source_adapters.normalize_paragraphs',return_value=([],{})):
            with self.assertRaisesRegex(ValueError,'reproduced'):validate_source_archive(fixture.source)
        path=fixture.archive/'chapter.html';saved=path.read_bytes();path.write_bytes(saved+b'changed')
        with self.assertRaisesRegex(ValueError,'archive hash mismatch'):validate_source_archive(fixture.source)

    def test_printed_number_mismatch_requires_verifiable_toc_ordinal_without_changing_ids(self):
        from test_final_translation_pilot import SeparateTitleTests
        from native_oauth.title_selection import metadata_title_source
        from native_oauth.chapter_integrity import source_content_hash
        import hashlib
        fixture=SeparateTitleTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        raw=fixture.html.replace('第1章 告白','第2章 告白').encode('utf8')
        (fixture.archive/'chapter.html').write_bytes(raw)
        source=copy.deepcopy(fixture.source);source.update(title='第2章 告白',raw_sha256=hashlib.sha256(raw).hexdigest(),
            source_ref='https://czbooks.net/n/fixture/chapter?chapterNumber=0',toc_index=1)
        source['content_hash']=source_content_hash(source);source.pop('package_hash');source['package_hash']=digest(source)
        title=metadata_title_source(source)
        self.assertEqual(title['catalog_chapter'],1);self.assertEqual(title['declared_chapter'],2)
        self.assertEqual(title['source'],'第2章 告白')
        self.assertEqual(source['segments'],fixture.source['segments'])
        source.pop('toc_index');source.pop('package_hash');source['package_hash']=digest(source)
        with self.assertRaisesRegex(ValueError,'archived metadata'):metadata_title_source(source)
