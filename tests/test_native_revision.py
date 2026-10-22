"""Offline regressions from the live Antigravity trial; models are mocked here."""
import json
import hashlib
import os
import copy
import threading
import itertools
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import test_antigravity_workflow as fixture_module
from native_test_helpers import native_runtime, bind_artifact, native_reviews, native_fixture
from semantic_gate import write_json, digest
from native_oauth.run_agy import bind_native_session, run
from native_oauth.meaning_anchors import source_anchors
from native_oauth.pipeline_native import run_json_stage, NativeJSONSchemaError
from native_oauth.run_agy import (IncompleteNativeOutput, completed_json_proof, classify_completion,
                                  require_complete_runtime)
from native_oauth.native_evidence import runtime_record
from native_oauth.native_evidence import validate_provenance
from native_oauth.revise_book import prepare_revision, revise_chapter, run_campaign, revision_protocol, diagnostic_notes
from native_oauth.native_review import run_independent_reviews
from native_oauth.recover_missing import missing_segments, recovery_findings
from native_oauth.diagnostic_grounding import ground_diagnosis
from native_oauth.revision_status import campaign_status


class SourceMeaningAnchorsTests(unittest.TestCase):
    def test_source_cues_flag_domain_and_count_without_inferring_replacements(self):
        rows=[{'id':'s','source':'他看前沿物理讀本，吸了兩口煙。'}]
        anchors=source_anchors(rows)
        self.assertEqual({a['kind'] for a in anchors},{'domain_frontier','explicit_quantity'})
        self.assertTrue(all(a['source_quote'] in rows[0]['source'] for a in anchors))
        self.assertEqual(recovery_findings('h',rows,{'source_hash':'h','model':'native/m',
            'segments':[{'id':'s','text':'Cảm ơn bạn 林八八八.'}]},'m'),
            [{'id':'s','kind':'residual_chinese_or_replacement'}])
        self.assertEqual(recovery_findings('h',rows,{'source_hash':'h','model':'native/m',
            'segments':[{'id':'s','text':'Cảm ơn bạn Lâm Bát Bát Bát.'}]},'m'),[])
    def test_diagnostic_ids_can_be_resolved_only_by_both_exact_quotes(self):
        package={'segments':[{'id':'p1','source':'他說了好幾年。'}]}
        candidate={'segments':[{'id':'p1','text':'Anh ấy bảo mấy năm nữa.'}]}
        diagnosis={'coverage_ids':['p1'],'findings':[{'id':'F01','source_quote':'說了好幾年','target_quote':'mấy năm nữa',
                                                    'proposed_vi':'An unverified suggestion'}]}
        result=ground_diagnosis(package,candidate,diagnosis)
        self.assertEqual(result['accepted'][0]['source_id'],'p1')
        self.assertEqual(result['status'],'GROUNDED_DIAGNOSTIC_NOT_APPROVAL')
        self.assertEqual(diagnosis['findings'][0]['id'],'F01')
        diagnosis['findings'][0]['target_quote']='Not in the candidate'
        self.assertEqual(len(ground_diagnosis(package,candidate,diagnosis)['rejected']),1)
        diagnosis['coverage_ids']=[]
        with self.assertRaises(ValueError):ground_diagnosis(package,candidate,diagnosis)
    def test_recovery_finds_real_missing_ids_and_refuses_hash_or_id_repair(self):
        source={'chapter':1,'segments':[{'id':'a','source':'第一段'},{'id':'b','source':'第二段'}]}
        source['package_hash']=digest(source)
        legacy={'bilingual_alignment':[{'para_id':'a','raw_zh':'第一段','translated_vi':'Đoạn một.'}]}
        self.assertEqual(missing_segments(source,legacy),[source['segments'][1]])
        legacy['bilingual_alignment'][0]['raw_zh']='別的原文'
        with self.assertRaises(ValueError):missing_segments(source,legacy)
        legacy['bilingual_alignment'][0]['raw_zh']='第一段'
        legacy['bilingual_alignment']*=2
        with self.assertRaises(ValueError):missing_segments(source,legacy)

    def test_real_temporal_relation_and_speech_cues_keep_exact_offsets(self):
        rows=[{'id':'c0003p0043','source':'說了好幾年給我生個侄女抱'},
              {'id':'c0003p0055','source':'薑柔甲記憶裡的準嫂子秦疏影'},
              {'id':'c0003p0089','source':'他低聲道：'}]
        anchors=source_anchors(rows)
        self.assertEqual({a['kind'] for a in anchors},{'elapsed_duration','viewpoint_qualifier','prospective_relation','speech_volume'})
        for anchor in anchors:
            raw=next(r['source'] for r in rows if r['id']==anchor['source_id'])
            self.assertEqual(raw[anchor['start']:anchor['end']],anchor['source_quote'])
        self.assertNotIn('prospective_relation',{a['kind'] for a in source_anchors([{'id':'x','source':'他準時到了。'}])})


class NativeResponseTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def test_windows_length_prompt_uses_finite_utf8_stdin_without_a_pipe_writer(self):
        prompt=self.root/'prompt.txt';body='Nguyên tác và bản dịch. '*2500
        prompt.write_text(body,encoding='utf-8')
        child=Mock();child.poll.return_value=0;child.stdin=None
        def popen(argv,**kwargs):
            self.assertNotIn(body,argv)
            stream=kwargs['stdin'];payload=json.loads(stream.read())
            self.assertEqual(stream.read(),b'')
            self.assertEqual(payload,{'event':'user','message':{'content':body}})
            self.assertNotIn('--dangerously-skip-permissions',argv)
            kwargs['stdout'].write(json.dumps({'event':'init','init':{'model':'fixture'}})+'\n')
            kwargs['stdout'].write(json.dumps({'event':'result','result':{'status':'SUCCESS','response':'complete'}})+'\n')
            return child
        with patch('native_oauth.run_agy.subprocess.Popen',side_effect=popen):
            runtime=run(prompt,self.root/'runtime',model='fixture',stdin_prompt=True)
        self.assertEqual(runtime['status'],'SUCCESS');self.assertEqual(runtime['exit_code'],0)
        self.assertTrue((self.root/'runtime/input.jsonl').exists())
        child.terminate.assert_not_called()

    def test_dashboard_binds_only_observed_session_without_overriding_explicit_dir(self):
        path=self.root/'events.jsonl'
        path.write_text(json.dumps({'event':'init','conversation_id':'actual-session'}),encoding='utf-8')
        monitor=Mock();monitor.native_artifact_dirs=set();monitor.native_session_order=[]
        with patch('native_oauth.session_monitor.SessionMonitor._instance',monitor), \
                patch.dict(os.environ,{'ANTIGRAVITY_ARTIFACT_DIR':''}),patch('pathlib.Path.home',return_value=self.root):
            self.assertTrue(bind_native_session(path))
            self.assertEqual(monitor.artifact_dir,self.root/'.gemini/antigravity/brain/actual-session')
            with patch.dict(os.environ,{'ANTIGRAVITY_ARTIFACT_DIR':'explicit'}):
                self.assertFalse(bind_native_session(path))
            path.write_text('{incomplete',encoding='utf-8')
            self.assertFalse(bind_native_session(path))

    def test_json_stage_response_and_runtime_are_bound_and_no_tool_permission_override(self):
        data=self.root/'data';data.mkdir()
        write_json(data/'source.json',{'chapter':1,'segments':[{'id':'x','source':'他走了。'}]})
        payload={'segments':[{'id':'x','text':'Anh ấy đi rồi.'}]}
        def transport(prompt,folder,*args,**kwargs):
            record=native_runtime(Path(folder).parent,session='native-fixture')
            source=Path(record['file']); folder=Path(folder);folder.mkdir(parents=True)
            runtime=json.loads(source.read_text(encoding='utf-8'))
            runtime['result']['response']=json.dumps(payload,ensure_ascii=False)
            write_json(folder/'runtime.json',runtime)
            events=[{'event':'init','conversation_id':runtime['conversation_id'],'init':{'model':'fixture'}},
                    {'event':'result','result':runtime['result']}]
            (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
            self.assertTrue(kwargs['stdin_prompt']);self.assertFalse(args[-1])
            return runtime
        with patch('native_oauth.pipeline_native.run',side_effect=transport):
            result=run_json_stage(data,self.root,'reviewer','fixture','Return the supplied schema','review.json',30)
        self.assertTrue(validate_provenance(result))
        result['segments'][0]['text']='Tự sửa sau khi gọi model.'
        with self.assertRaises(ValueError):validate_provenance(result)

    def test_explicit_native_blocked_reason_is_retained_and_never_becomes_a_candidate(self):
        data=self.root/'blocked';data.mkdir()
        write_json(data/'source.json',{'chapter':1,'segments':[{'id':'p1','source':'他走了。'}]})
        def transport(prompt,folder,*args,**kwargs):
            folder=Path(folder);response=json.dumps({'status':'BLOCKED','reason':'Missing authorized source context'})
            runtime={'status':'SUCCESS','exit_code':0,'actual_model':'fixture','conversation_id':'blocked-fixture',
                'result':{'status':'SUCCESS','conversation_id':'blocked-fixture','response':response}}
            write_json(folder/'runtime.json',runtime)
            events=[{'event':'init','conversation_id':'blocked-fixture','init':{'model':'fixture'}},
                    {'event':'result','result':runtime['result']}]
            (folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
            return runtime
        with patch('native_oauth.pipeline_native.run',side_effect=transport):
            with self.assertRaisesRegex(ValueError,'Missing authorized source context'):
                run_json_stage(data,self.root,'reviewer','fixture','Fixture protocol','review.json',30)
        self.assertFalse((data/'review.json').exists())
        self.assertTrue((data/'review.native-original.json').exists())

    def test_only_invalid_evidence_is_retried_without_regenerating_candidate(self):
        package,candidate,reports=native_fixture(self.root)
        counts={'reviewer':0,'auditor':0}; lock=threading.Lock()
        data=self.root/'inputs';data.mkdir()
        def stage(target,workspace,role,*args):
            with lock:
                counts[role]+=1; attempt=counts[role]
            result=copy.deepcopy(reports[0 if role=='reviewer' else 1])
            if role=='reviewer' and attempt==1:
                result['segments'][0]['target_quote']='Added quotation marks absent from the paragraph'
            return result
        with patch('native_oauth.pipeline_native.run_stage',side_effect=stage):
            result=run_independent_reviews(package,candidate,data,self.root/'review','fixture','fixture')
        self.assertEqual(counts,{'reviewer':2,'auditor':1})
        self.assertEqual(len(result),2)
        self.assertEqual(result[0]['candidate_hash'],digest(candidate))

    def test_a_valid_semantic_fail_is_returned_without_retry_until_pass(self):
        package,candidate,reports=native_fixture(self.root)
        reports[0]['verdict']='FAIL';reports[0]['segments'][0]['verdict']='FAIL'
        reports[0]['issues']=[{'id':package['segments'][0]['id'],'reason':'A source-grounded semantic defect'}]
        data=self.root/'inputs';data.mkdir();calls=[]
        def stage(target,workspace,role,*args):
            calls.append(role);return reports[0 if role=='reviewer' else 1]
        with patch('native_oauth.pipeline_native.run_stage',side_effect=stage):
            result=run_independent_reviews(package,candidate,data,self.root/'review','fixture','fixture')
        self.assertEqual(sorted(calls),['auditor','reviewer'])
        self.assertEqual(result[0]['verdict'],'FAIL')

    def test_malformed_complete_json_can_retry_but_native_timeout_cannot(self):
        package,candidate,reports=native_fixture(self.root)
        data=self.root/'inputs';data.mkdir();counts={'reviewer':0,'auditor':0}
        def stage(target,workspace,role,*args):
            counts[role]+=1
            if role=='reviewer' and counts[role]==1:
                raise NativeJSONSchemaError('An unescaped quote in a completed response')
            return reports[0 if role=='reviewer' else 1]
        with patch('native_oauth.pipeline_native.run_stage',side_effect=stage):
            self.assertEqual(len(run_independent_reviews(package,candidate,data,self.root/'review','fixture','fixture')),2)
        self.assertEqual(counts,{'reviewer':2,'auditor':1})
        counts={'reviewer':0,'auditor':0}
        def timeout(target,workspace,role,*args):
            counts[role]+=1
            if role=='reviewer':raise IncompleteNativeOutput('Native output incomplete: TIMEOUT')
            return reports[1]
        with patch('native_oauth.pipeline_native.run_stage',side_effect=timeout):
            with self.assertRaises(IncompleteNativeOutput):
                run_independent_reviews(package,candidate,data,self.root/'timeout','fixture','fixture')
        self.assertEqual(counts['reviewer'],1)

    def test_missing_literary_checks_retry_only_the_auditor(self):
        package,candidate,reports=native_fixture(self.root)
        data=self.root/'inputs';data.mkdir();counts={'reviewer':0,'auditor':0}
        def stage(target,workspace,role,*args):
            counts[role]+=1
            result=copy.deepcopy(reports[0 if role=='reviewer' else 1])
            if role=='auditor' and counts[role]==1:result.pop('literary_checks')
            return result
        with patch('native_oauth.pipeline_native.run_stage',side_effect=stage):
            run_independent_reviews(package,candidate,data,self.root/'review','fixture','fixture')
        self.assertEqual(counts,{'reviewer':1,'auditor':2})


class CompletedNativeCleanupTests(unittest.TestCase):
    def events(self):
        return [{'event':'init','conversation_id':'actual-native','init':{'model':'fixture'}},
                {'event':'step_update','step_update':{'step_type':'agent_response','state':'DONE'}},
                {'event':'result','result':{'status':'SUCCESS','conversation_id':'actual-native',
                                         'response':'{"segments":[]}'}}]

    def test_partial_tool_invalid_json_or_inconsistent_session_cannot_qualify(self):
        events=self.events()
        self.assertIsNotNone(completed_json_proof(events,''))
        variants=[]
        active=copy.deepcopy(events);active[1]['step_update']['state']='ACTIVE';variants.append(active)
        invalid=copy.deepcopy(events);invalid[-1]['result']['response']='{"unfinished';variants.append(invalid)
        tool=copy.deepcopy(events);tool.insert(1,{'event':'step_update','step_update':{'step_type':'tool','state':'DONE'}});variants.append(tool)
        different=copy.deepcopy(events);different[-1]['result']['conversation_id']='different';variants.append(different)
        length=copy.deepcopy(events);length[-1]['result']['finish_reason']='max_tokens';variants.append(length)
        variants.append(events+[events[-1]])
        for variant in variants:self.assertIsNone(completed_json_proof(variant,''))
        self.assertIsNone(completed_json_proof(events,'print timeout; returning partial output'))

    def test_nonzero_exit_requires_matching_host_cleanup_and_never_converts_a_timeout(self):
        events=self.events();proof=completed_json_proof(events,'')
        cleanup={**proof,'action':'terminate_after_verified_done','grace_seconds':10.5,
                 'transport':'finite_stdin_json_no_tools','input_sha256':'1'*64}
        classified=classify_completion(events,'',47,completed_cleanup=cleanup)
        self.assertEqual(classified['status'],'COMPLETED_CLI_CLEANUP')
        self.assertFalse(classified['partial_output'])
        runtime={**classified,'exit_code':47,'completed_cleanup':cleanup}
        self.assertEqual(require_complete_runtime(runtime,'fixture'),'{"segments":[]}')
        self.assertEqual(classify_completion(events,'',47)['status'],'ERROR')
        forged={**cleanup,'events_sha256':'0'*64}
        self.assertEqual(classify_completion(events,'',47,completed_cleanup=forged)['status'],'ERROR')
        self.assertEqual(classify_completion(events,'',47,timed_out=True,completed_cleanup=cleanup)['status'],'TIMEOUT')
        with self.assertRaises(IncompleteNativeOutput):
            require_complete_runtime({**runtime,'status':'TIMEOUT'},'fixture')

    def test_runtime_rechecks_cleanup_against_immutable_native_events(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'runtime.json';events=self.events()
            request=path.with_name('input.jsonl')
            request.write_text(json.dumps({'event':'user','message':{'content':'Fixture protocol'}}),encoding='utf-8')
            cleanup={**completed_json_proof(events,''),'action':'terminate_after_verified_done','grace_seconds':11,
                     'transport':'finite_stdin_json_no_tools','input_sha256':hashlib.sha256(request.read_bytes()).hexdigest()}
            runtime={**classify_completion(events,'',23,completed_cleanup=cleanup),'exit_code':23,
                     'conversation_id':'actual-native','completed_cleanup':cleanup,'duration_seconds':15}
            write_json(path,runtime)
            path.with_name('events.jsonl').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
            self.assertEqual(runtime_record(path,'fixture')['conversation_id'],'actual-native')
            original=request.read_bytes();request.write_bytes(b'altered')
            with self.assertRaises(ValueError):runtime_record(path,'fixture')
            request.write_bytes(original)
            events[1]['step_update']['state']='ACTIVE'
            path.with_name('events.jsonl').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
            with self.assertRaises(ValueError):runtime_record(path,'fixture')

    def test_driver_waits_for_done_then_preserves_actual_termination_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);prompt=root/'prompt.txt';prompt.write_text('Native fixture',encoding='utf-8')
            child=Mock();child.poll.return_value=None;child.wait.return_value=47;child.returncode=47
            def popen(argv,**kwargs):
                kwargs['stdout'].write('\n'.join(json.dumps(e) for e in self.events())+'\n')
                kwargs['stdout'].flush();return child
            with patch('native_oauth.run_agy.subprocess.Popen',side_effect=popen), \
                    patch('native_oauth.run_agy.bind_native_session',return_value=True), \
                    patch('native_oauth.run_agy.time.time',side_effect=itertools.count()), \
                    patch('native_oauth.run_agy.time.sleep'):
                runtime=run(prompt,root/'runtime',model='fixture',timeout=30,stdin_prompt=True)
            self.assertEqual(runtime['status'],'COMPLETED_CLI_CLEANUP')
            self.assertEqual(runtime['exit_code'],47)
            self.assertGreaterEqual(runtime['completed_cleanup']['grace_seconds'],10)
            child.terminate.assert_called_once()
            self.assertEqual(runtime_record(root/'runtime/runtime.json','fixture')['conversation_id'],'actual-native')


class NativeBookRevisionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.AntigravityWorkflowTests('test_complete_book_draft_review_promote_and_revalidate')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.book,source=self.fixture.draft_book()
        source['source_ref']='fixture';source['package_hash']=digest({k:v for k,v in source.items() if k!='package_hash'})
        write_json(self.book/'sources/source_chapter_0001.json',source)
        self.job=self.fixture.root/'campaign';self.job.mkdir()
        self.original=(self.book/'drafts/chuong_0001.dich.json').read_bytes()
        manifest={}
        for relative,content in [('sources/source_chapter_0001.json',(self.book/'sources/source_chapter_0001.json').read_bytes()),
                                 ('output_dich/chuong_0001.dich.json',self.original)]:
            target=self.job/'baseline'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
            manifest[relative]={'sha256':hashlib.sha256(content).hexdigest()}
        write_json(self.job/'baseline_manifest.json',manifest)

    def generation(self,data,workspace,role,model,protocol,output,timeout):
        package=json.loads((Path(data)/'source.json').read_text(encoding='utf-8'))
        self.assertIn('UNTRUSTED_LEGACY_ALIGNMENT',protocol)
        result={'package_hash':package['package_hash'],'model':'native/fixture',
                'native_runtimes':[native_runtime(self.fixture.root/'gen')],
                'segments':[{'id':row['id'],'text':text} for row,text in zip(package['segments'],['Chương 1','Anh ấy đã đi rồi.'])]}
        return bind_artifact(self.fixture.root/'generation.json',result)

    def test_repair_receives_latest_candidate_so_good_corrections_are_not_discarded(self):
        package=prepare_revision(self.book,self.job,1)[2]
        draft={'segments':[{'id':package['segments'][0]['id'],'text':'Latest corrected candidate'}]}
        legacy={'bilingual_alignment':[{'para_id':row['id'],'raw_zh':row['source'],
            'translated_vi':'DISCARDED_OLD_REFERENCE'} for row in package['segments']],
            'recovery_proposal':[{'id':package['segments'][0]['id'],'text':'OLD_RECOVERY_REFERENCE'}]}
        text=revision_protocol(package,legacy,[{'reason':'Confirm against source'}],draft)
        self.assertIn('CURRENT_CANDIDATE_TO_POSTEDIT',text)
        self.assertIn('Latest corrected candidate',text)
        self.assertIn('do not revert good previous corrections',text)
        self.assertNotIn('DISCARDED_OLD_REFERENCE',text)
        self.assertNotIn('OLD_RECOVERY_REFERENCE',text)

    def test_campaign_report_does_not_count_legacy_as_approved_and_checks_originals(self):
        write_json(self.job/'campaign.json',{'range':[1,1],'status':'RUNNING'})
        original=self.book/'output_dich/chuong_0001.dich.json'
        original.parent.mkdir(exist_ok=True);original.write_bytes(self.original)
        report=campaign_status(self.book,self.job)
        self.assertEqual(report['approved_count'],0)
        self.assertFalse(report['full_range_approved'])
        self.assertEqual(report['baseline_changes'],[])
        original.write_bytes(b'changed legacy')
        self.assertEqual(campaign_status(self.book,self.job)['baseline_changes'],
                         [{'scope':'original','path':'output_dich/chuong_0001.dich.json'}])

    def test_editorial_diagnostics_require_both_exact_quotes_and_bind_the_archive(self):
        source=prepare_revision(self.book,self.job,1)[0]
        comparison=self.job/'baseline/output_dich/chuong_0001.dich.json'
        row=json.loads(comparison.read_text(encoding='utf-8'))['bilingual_alignment'][0]
        note={'source_hash':source['package_hash'],'comparison_file':str(comparison),
              'comparison_sha256':hashlib.sha256(comparison.read_bytes()).hexdigest(),
              'findings':[{'id':row['para_id'],'source_quote':row['raw_zh'],
                           'target_quote':row['translated_vi'],'reason':'Independently recheck the source meaning.'}]}
        file=self.job/'diagnostics/chapter_0001.json';write_json(file,note)
        findings,bound=diagnostic_notes(self.book,self.job,1,source)
        self.assertEqual(findings,note['findings']);self.assertIn(str(file.resolve()),bound)
        self.assertEqual(prepare_revision(self.book,self.job,1)[2]['editorial_diagnostics']['status'],
                         'SOURCE_BOUND_DIAGNOSTIC_NOT_APPROVAL')
        note['findings'][0]['target_quote']='not in the comparison';write_json(file,note)
        with self.assertRaises(ValueError):diagnostic_notes(self.book,self.job,1,source)

    def test_revision_promotes_only_after_two_reviews_and_preserves_frozen_baseline(self):
        with patch('native_oauth.revise_book.run_stage',side_effect=self.generation), \
                patch('native_oauth.revise_book.run_independent_reviews',side_effect=lambda p,c,*args:native_reviews(p,c,self.fixture.root/'review')):
            path=revise_chapter(self.book,self.job,1,translator_model='fixture')
        self.assertTrue(path.exists())
        self.assertEqual((self.job/'baseline/output_dich/chuong_0001.dich.json').read_bytes(),self.original)
        self.assertEqual(json.loads((self.job/'results/chapter_0001.json').read_text(encoding='utf-8'))['status'],'APPROVED')

    def test_frozen_source_tamper_or_review_failure_cannot_publish(self):
        source=self.book/'sources/source_chapter_0001.json'
        original=source.read_bytes();source.write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):prepare_revision(self.book,self.job,1)
        source.write_bytes(original)
        def reject(package,candidate,*args):
            reports=native_reviews(package,candidate,self.fixture.root/'rejected')
            reports[0]['verdict']='FAIL';return reports
        with patch('native_oauth.revise_book.run_stage',side_effect=self.generation), \
                patch('native_oauth.revise_book.run_independent_reviews',side_effect=reject):
            with self.assertRaises(ValueError):revise_chapter(self.book,self.job,1,translator_model='fixture',max_repairs=0)
        self.assertFalse((self.book/'approved/manifest.json').exists())
