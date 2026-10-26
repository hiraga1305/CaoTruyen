"""Offline concurrent native workflow regressions; never calls a real model."""
import contextlib
import copy
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from semantic_gate import digest, read_json, write_json, mechanical_findings, validate_review
from native_test_helpers import native_runtime, bind_artifact, native_reviews
from native_oauth.revise_book import create_campaign, prepare_revision, run_campaign
from native_oauth.wave_drafts import generate_draft, validate_generation_package
from native_oauth.wave_review import CHECKS, validate_wave_gates
from native_oauth.book_publication import read_manifest, read_approval, load_approved_chapters
from native_oauth.book_progress import book_progress
from native_oauth.review_quotes import resolve_quote, evidence_catalog


class WaveRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.book=self.root/'book_fixture';self.job=self.root/'job'
        self.originals={}
        for chapter in range(1,6):
            source={'version':'bns-source-v1','book_id':'fixture','chapter':chapter,'source_ref':'fixture',
                    'title':f'第{chapter}章 測試','paragraph_count':2,
                    'segments':[{'id':f'c{chapter:04d}p0001','source':f'第{chapter}章 測試'},
                                {'id':f'c{chapter:04d}p0002','source':'他走了。'}]}
            source['package_hash']=digest(source)
            write_json(self.book/'sources'/f'source_chapter_{chapter:04d}.json',source)
            file=self.book/'output_dich'/f'chuong_{chapter:04d}.dich.json'
            write_json(file,{'bilingual_alignment':[
                {'para_id':r['id'],'raw_zh':r['source'],'translated_vi':'Old unverified text'} for r in source['segments']]})
            self.originals[file]=file.read_bytes()
        write_json(self.book/'toc.json',[{}]*5)
        create_campaign(self.book,self.job)
        self.options={'mode':'wave','translator_model':'fixture','reviewer_model':'fixture','auditor_model':'fixture','max_repairs':0}
        self.calls=[];self.reviewed=[];self.counter=0;self.guard=threading.Lock()
        self.active=0;self.peak=0;self.overlap=False
        self.parallel_probe=False;self.fail_wave=False;self.fail_chapter=None;self.bad_source=False
        self.first_two=threading.Barrier(2);self.third_started=threading.Event();self.review_started=threading.Event()
        stack=contextlib.ExitStack();self.addCleanup(stack.close)
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        for module in ('native_oauth.native_review','native_oauth.revise_book','native_oauth.wave_revision'):
            stack.enter_context(patch(module+'.get_session_monitor',return_value=Mock()))
        stack.enter_context(patch('native_oauth.pipeline_native.run_stage',side_effect=self.stage))
        stack.enter_context(patch('native_oauth.revise_book.run_stage',side_effect=self.stage))
        stack.enter_context(patch('native_oauth.revise_book.run_independent_reviews',side_effect=self.reviews))

    def bind(self,target,model,payload):
        payload.update(model='native/'+model,native_runtimes=[native_runtime(Path(target)/'runtime',model=model)])
        return bind_artifact(Path(target)/'response.json',payload)

    def stage(self,data,work,role,model,protocol,output,timeout):
        package=read_json(Path(data)/'source.json');chapter=package['chapter']
        with self.guard:
            self.calls.append((role,chapter));self.counter+=1
        if role=='wave-auditor':
            rows=[]
            for ch in package['chapters']:
                rows.append({'chapter':ch['chapter'],'verdict':'PASS','source_id':ch['source'][-1]['id'],
                    'source_quote':ch['source'][-1]['source'],'target_quote':ch['target'][-1]['text'],
                    'reason':'Offline fixture cross-chapter comparison'})
            issues=[]
            if self.fail_wave:
                row=rows[1];row['verdict']='FAIL'
                issues=[{'id':row['source_id'],'source_quote':row['source_quote'],
                         'target_quote':row['target_quote'],'reason':'Fixture chronology inconsistency'}]
            return self.bind(Path(data)/'proof',model,{'package_hash':package['package_hash'],
                'verdict':'FAIL' if self.fail_wave else 'PASS','checks':dict.fromkeys(CHECKS,True),
                'chapters':rows,'issues':issues})
        self.assertEqual(role,'translator')
        with self.guard:
            self.active+=1;self.peak=max(self.peak,self.active)
        try:
            if self.parallel_probe:
                if chapter in (1,2):self.first_two.wait(timeout=5)
                if chapter==3:
                    self.third_started.set()
                    if not self.review_started.wait(5):raise AssertionError('Review did not overlap drafts')
            if self.bad_source:
                path=self.book/'sources'/f'source_chapter_{chapter:04d}.json'
                raw=read_json(path);raw['title']='Changed during generation';write_json(path,raw)
            return self.bind(Path(data)/'proof',model,{'package_hash':package['package_hash'],
                'segments':[{'id':r['id'],'text':f'Chương {chapter}: Thử nghiệm' if i==0 else 'Anh ấy đi rồi.'}
                            for i,r in enumerate(package['segments'])]})
        finally:
            with self.guard:self.active-=1

    def reviews(self,package,candidate,data,work,*args):
        chapter=package['chapter']
        self.assertEqual(self.reviewed,list(range(1,chapter)))
        if chapter>1:read_approval(self.book,chapter-1)
        if self.parallel_probe and chapter==1:
            self.assertTrue(self.third_started.wait(5))
            with self.guard:self.overlap=self.active>0
            self.review_started.set()
        reviews=native_reviews(package,candidate,Path(work)/'fixture-review')
        for i,review in enumerate(reviews):
            if candidate.get('native_generation_package'):review['generation_context_checked']=True
            if chapter==self.fail_chapter:
                review['verdict']='FAIL';review['segments'][0]['verdict']='FAIL'
                review['issues']=[{'id':package['segments'][0]['id'],'reason':'Fixture semantic error'}]
            bind_artifact(Path(work)/f'bound-review-{i}.json',review)
        if chapter!=self.fail_chapter:self.reviewed.append(chapter)
        return reviews

    def run_job(self):
        return run_campaign(self.book,self.job,5,max_workers=3,**self.options)

    def test_parallel_drafts_overlap_ordered_reviews_and_wave_pass_is_required_for_export(self):
        self.parallel_probe=True
        state=self.run_job()
        self.assertEqual(state['status'],'APPROVED_RANGE_COMPLETE')
        self.assertEqual(self.peak,2);self.assertTrue(self.overlap)
        self.assertEqual(len(load_approved_chapters(self.book,range(1,6))),5)
        self.assertEqual(self.calls.count(('wave-auditor',1)),1)
        for chapter in range(1,6):
            ev=read_approval(self.book,chapter)['evidence']
            self.assertNotEqual(ev['package']['package_hash'],ev['candidate']['package_hash'])
            self.assertTrue(all(r['generation_context_checked'] for r in ev['reviews']))
        for path,original in self.originals.items():self.assertEqual(path.read_bytes(),original)

    def test_wave_fail_blocks_export_and_records_grounded_feedback_for_changed_resume(self):
        self.fail_wave=True
        with self.assertRaisesRegex(ValueError,'wave review failed'):self.run_job()
        self.assertEqual(list(read_manifest(self.book)['chapters']),['1','2','3','4','5'])
        with self.assertRaisesRegex(ValueError,'pending or blocked'):load_approved_chapters(self.book,range(1,6))
        self.assertFalse(book_progress(self.book,5)['export_ready'])
        self.assertTrue((self.job/'wave_diagnostics/chapter_0002.json').exists())
        self.fail_wave=False;self.reviewed=[1]
        self.run_job()
        self.assertTrue(book_progress(self.book,5)['export_ready'])
        self.assertEqual([ch for role,ch in self.calls if role=='translator'].count(2),2)

    def test_semantic_failure_stops_later_approvals_and_rejected_draft_is_not_reused(self):
        self.fail_chapter=2
        with self.assertRaisesRegex(ValueError,'blocked after'):self.run_job()
        self.assertEqual(list(read_manifest(self.book)['chapters']),['1'])
        self.assertTrue((self.job/'rejected_wave_drafts/chapter_0002.json').exists())
        self.fail_chapter=None
        self.run_job()
        self.assertEqual([ch for role,ch in self.calls if role=='translator'].count(2),2)
        self.assertTrue(book_progress(self.book,5)['export_ready'])

    def test_completed_wave_resume_performs_no_native_calls(self):
        self.run_job();before=list(self.calls)
        self.assertEqual(self.run_job()['status'],'APPROVED_RANGE_COMPLETE')
        self.assertEqual(self.calls,before)

    def test_schema_interruption_keeps_original_draft_for_resume(self):
        from native_oauth.pipeline_native import NativeJSONSchemaError
        original=self.reviews
        def interrupted(package,*args):
            if package['chapter']==2:raise NativeJSONSchemaError('Fixture schema-only interruption')
            return original(package,*args)
        with patch('native_oauth.revise_book.run_independent_reviews',side_effect=interrupted):
            with self.assertRaises(NativeJSONSchemaError):self.run_job()
        before=[ch for role,ch in self.calls if role=='translator'].count(2)
        self.run_job()
        self.assertEqual([ch for role,ch in self.calls if role=='translator'].count(2),before)
        self.assertTrue(book_progress(self.book,5)['export_ready'])

    def test_old_sequential_approvals_are_kept_without_running_new_models(self):
        self.run_job()
        m=read_manifest(self.book);m.pop('wave_gates');write_json(self.book/'approved/manifest.json',m)
        before=list(self.calls)
        self.run_job()
        self.assertEqual(self.calls,before)

    def test_source_change_during_generation_cannot_be_approved(self):
        self.bad_source=True
        with self.assertRaises(ValueError):self.run_job()
        self.assertEqual(read_manifest(self.book)['chapters'],{})

    def test_generation_input_or_canon_cannot_be_swapped_during_final_context_binding(self):
        seed=generate_draft(self.book,self.job,1,{'through_chapter':0,'approved_context':{}},
                            model='fixture',timeout=30,max_repairs=0)
        package=prepare_revision(self.book,self.job,1)[2]
        validate_generation_package(package,seed)
        altered=copy.deepcopy(package);altered['segments'][1]['source']='別的內容'
        with self.assertRaises(ValueError):validate_generation_package(altered,seed)
        file=Path(seed['native_generation_package']['file']);raw=read_json(file);raw['glossary']={'a':'b'}
        write_json(file,raw)
        with self.assertRaises(ValueError):validate_generation_package(package,seed)

    def test_final_review_must_explicitly_check_new_context(self):
        seed=generate_draft(self.book,self.job,1,{'through_chapter':0,'approved_context':{}},
                            model='fixture',timeout=30,max_repairs=0)
        package=prepare_revision(self.book,self.job,1)[2]
        review=native_reviews(package,seed,self.root/'review')[0]
        with self.assertRaisesRegex(ValueError,'final approved context'):validate_review(package,seed,review)

    def test_wave_receipt_mutation_is_detected_on_read_and_export(self):
        self.run_job()
        gate=read_manifest(self.book)['wave_gates']['1'];file=self.book/gate['evidence']
        ev=read_json(file);ev['review']['chapters'][0]['reason']='Modified after review';write_json(file,ev)
        with self.assertRaises(ValueError):validate_wave_gates(self.book)
        with self.assertRaises(ValueError):load_approved_chapters(self.book,range(1,6))

    def test_restart_request_does_not_start_native_work(self):
        write_json(self.job/'restart_requested.json',{'reason':'Fixture boundary stop'})
        self.assertEqual(self.run_job()['status'],'STOPPED_AT_WAVE_BOUNDARY')
        self.assertEqual(self.calls,[])

    def test_next_wave_uses_frozen_approved_prefix_and_supports_partial_final_wave(self):
        source=copy.deepcopy(read_json(self.book/'sources/source_chapter_0005.json'))
        source.update(chapter=6,title='第6章 測試')
        source['segments']=[{'id':'c0006p0001','source':'第6章 測試'},
                            {'id':'c0006p0002','source':'他走了。'}]
        source['package_hash']=digest({k:v for k,v in source.items() if k!='package_hash'})
        write_json(self.book/'sources/source_chapter_0006.json',source)
        file=self.job/'baseline/sources/source_chapter_0006.json';write_json(file,source)
        baseline=read_json(self.job/'baseline_manifest.json')
        import hashlib
        baseline['sources/source_chapter_0006.json']={'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
        write_json(self.job/'baseline_manifest.json',baseline);write_json(self.book/'toc.json',[{}]*6)
        self.run_job()
        state=run_campaign(self.book,self.job,6,max_workers=3,**self.options)
        self.assertEqual(state['approved_chapters'],list(range(1,7)))
        self.assertTrue(book_progress(self.book,6)['export_ready'])
        ev=read_approval(self.book,6)['evidence']
        generation=read_json(ev['candidate']['native_generation_package']['file'])
        self.assertEqual(generation['draft_anchor']['through_chapter'],5)
        self.assertEqual(generation['draft_anchor']['prefix_entry'],read_manifest(self.book)['chapters']['5'])
        manifest=read_manifest(self.book);manifest['chapters']['5']['receipt_hash']='changed'
        write_json(self.book/'approved/manifest.json',manifest)
        with self.assertRaisesRegex(ValueError,'anchor revision'):validate_generation_package(ev['package'],ev['candidate'])

    def test_source_only_book_without_legacy_output_uses_same_wave_pipeline(self):
        for chapter in range(1,6):
            file=self.job/'baseline/output_dich'/f'chuong_{chapter:04d}.dich.json'
            file.unlink()
            (self.book/'output_dich'/f'chuong_{chapter:04d}.dich.json').unlink()
        baseline=read_json(self.job/'baseline_manifest.json')
        write_json(self.job/'baseline_manifest.json',{k:v for k,v in baseline.items() if not k.startswith('output_dich/')})
        self.run_job()
        self.assertEqual(len(load_approved_chapters(self.book,range(1,6))),5)


class VerbatimEvidenceTests(unittest.TestCase):
    def test_reference_reviews_still_require_semantic_flags_and_valid_native_evidence(self):
        from native_test_helpers import native_fixture
        from semantic_gate import evaluate
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);package,candidate,reviews=native_fixture(root)
            for i,review in enumerate(reviews):
                for row in review['segments']:
                    row.pop('source_quote');row.pop('target_quote')
                    row.update(source_quote_ref='0',target_quote_ref='0')
                bind_artifact(root/f'ref-review-{i}.json',review)
            self.assertEqual(evaluate(package,candidate,reviews,review_policy={'mode':'antigravity_sessions'})['status'],'PASS')
            reviews[0]['checks']['meaning']=False
            self.assertEqual(evaluate(package,candidate,reviews,review_policy={'mode':'antigravity_sessions'})['status'],'BLOCKED')

    def test_references_resolve_exact_spans_without_rewriting_native_review(self):
        body='他說：每個月轉三萬元，持續幾百年。'
        row={'source_quote_ref':'1'};original=copy.deepcopy(row)
        self.assertIn(resolve_quote(row,'source_quote',body),body)
        self.assertEqual(row,original)
        with self.assertRaises(ValueError):resolve_quote({'source_quote_ref':'99'},'source_quote',body)
        with self.assertRaises(ValueError):resolve_quote({'source_quote_ref':'0','source_quote':'fabricated'},'source_quote',body)

    def test_catalog_is_bounded_and_ellipses_are_not_inserted_into_evidence(self):
        p={'segments':[{'id':'c0001p0001','source':'原文。'*50}]}
        c={'segments':[{'id':'c0001p0001','text':'Bản dịch. '*50}]}
        self.assertEqual(evidence_catalog(p,c,budget=10),'')
        catalog=evidence_catalog(p,c)
        self.assertIn('source_quote_ref',catalog)
        self.assertNotIn('…',catalog)

    def test_native_json_binding_is_preserved_when_host_attaches_generation_receipt(self):
        from native_oauth.native_evidence import runtime_record, validate_provenance
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            record=native_runtime(root/'runtime')
            file=Path(record['file']);runtime=read_json(file)
            original={'package_hash':'original-generation-hash','segments':[{'id':'c0001p0001','text':'Bản gốc.'}]}
            runtime['result']['response']=json.dumps(original,ensure_ascii=False)
            write_json(file,runtime)
            events=[{'event':'init','conversation_id':runtime['conversation_id'],'init':{'model':'fixture'}},
                    {'event':'result','result':runtime['result']}]
            file.with_name('events.jsonl').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
            payload={**original,'model':'native/fixture','native_runtimes':[runtime_record(file,'fixture')],
                     'native_response_binding':'json'}
            bind_artifact(root/'native-output.json',payload)
            payload['native_generation_package']={'file':'recorded input','hash':'input-hash'}
            self.assertTrue(validate_provenance(payload))
            payload['package_hash']='pretending-to-have-final-context'
            with self.assertRaises(ValueError):validate_provenance(payload)
