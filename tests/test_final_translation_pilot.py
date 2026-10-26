"""Offline regressions for final approvals, title ownership and honest timing."""
import contextlib
import copy
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from semantic_gate import (build_package, digest, write_json, read_json,
                           mechanical_findings, validate_review, translation_prompt)
from native_test_helpers import native_runtime, bind_artifact, native_reviews
from native_oauth.chapter_integrity import source_content_hash, require_approved, render_text
from native_oauth.source_adapters import extract_paragraphs, normalize_paragraphs
from native_oauth.title_selection import metadata_title_source
from native_oauth.revise_book import create_campaign, prepare_revision, revise_chapter
from native_oauth.book_publication import read_approval
from native_oauth.meaning_anchors import source_anchors
from native_oauth.wave_review import chapter_wave_data, chapter_texts
from native_oauth.final_translation_pilot import prepare, assert_frozen, runtime_rows, report, run_stress, require_prior_arms, ARMS

ROOT=Path(__file__).resolve().parents[1]


class SeparateTitleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.book=self.root/'book';self.job=self.root/'job'
        (ROOT/'source_archive').mkdir(exist_ok=True)
        archive=tempfile.TemporaryDirectory(prefix='book_finaltest_',dir=ROOT/'source_archive')
        self.addCleanup(archive.cleanup);self.archive=Path(archive.name)
        self.book_id=self.archive.name.removeprefix('book_')
        self.html='<div class="name">《測試》第1章 告白</div><div class="content"><p>他不甘心。</p><p>她走了。</p></div>'
        raw=self.html.encode('utf-8');(self.archive/'chapter.html').write_bytes(raw)
        rows,mapping=normalize_paragraphs(extract_paragraphs(self.html),1)
        self.source={'version':'bns-source-v2','book_id':self.book_id,'chapter':1,
            'title':'第1章 告白','source_ref':'https://czbooks.net/n/fixture/chapter',
            'raw_archive':'chapter.html','raw_sha256':hashlib.sha256(raw).hexdigest(),
            'segments':rows,'paragraph_count':len(rows),'normalization':mapping}
        self.source['content_hash']=source_content_hash(self.source)
        self.source['package_hash']=digest(self.source)
        write_json(self.book/'sources/source_chapter_0001.json',self.source)
        write_json(self.book/'toc.json',[{}])
        create_campaign(self.book,self.job)
        self.package=prepare_revision(self.book,self.job,1)[2]
        self.candidate={'package_hash':self.package['package_hash'],'title_vi':'Chương 1: Tỏ tình',
            'segments':[{'id':r['id'],'text':t} for r,t in zip(rows,['Anh ấy không cam lòng.','Cô ấy đi rồi.'])]}

    def review(self):
        review={'package_hash':self.package['package_hash'],'candidate_hash':digest(self.candidate),
            'verdict':'PASS','checks':dict.fromkeys(__import__('semantic_gate').CHECKS,True),'issues':[],
            'segments':[{'id':r['id'],'verdict':'PASS','source_quote':r['source'],
                         'target_quote':t['text'],'reason':'Fixture'}
                        for r,t in zip(self.package['segments'],self.candidate['segments'])]}
        review['metadata_title_review']={'verdict':'PASS','source_quote':'告白','target_quote':'Tỏ tình','reason':'Fixture title check'}
        return review

    def test_title_is_archived_and_body_ids_do_not_change(self):
        self.assertEqual(self.package['segments'],[{k:r[k] for k in ('id','source')} for r in self.source['segments']])
        self.assertEqual(self.package['metadata_title_source']['source'],'第1章 告白')
        self.assertIn('title_vi',translation_prompt(self.package))
        wrong=copy.deepcopy(self.source);wrong['title']='第1章 假標題';wrong.pop('package_hash');wrong['package_hash']=digest(wrong)
        with self.assertRaisesRegex(ValueError,'archived metadata'):metadata_title_source(wrong)

    def test_missing_title_or_title_review_cannot_pass(self):
        self.assertEqual(mechanical_findings(self.package,self.candidate),[])
        missing={k:v for k,v in self.candidate.items() if k!='title_vi'}
        self.assertIn('invalid_metadata_title_translation',[r['kind'] for r in mechanical_findings(self.package,missing)])
        review=self.review();validate_review(self.package,self.candidate,review)
        del review['metadata_title_review']
        with self.assertRaisesRegex(ValueError,'title requires'):validate_review(self.package,self.candidate,review)
        review=self.review();review['metadata_title_review']['target_quote']='Unrelated'
        with self.assertRaises(ValueError):validate_review(self.package,self.candidate,review)

    def test_title_fail_and_wrong_quote_are_blocked(self):
        review=self.review();review['metadata_title_review']['verdict']='FAIL'
        with self.assertRaisesRegex(ValueError,'Contradictory'):validate_review(self.package,self.candidate,review)
        review['verdict']='FAIL';review['issues']=[{'id':'c0001title','reason':'Wrong title'}]
        validate_review(self.package,self.candidate,review)

    def test_native_revision_commits_reviewed_title_and_all_body_paragraphs(self):
        def stage(data,work,role,model,protocol,output,timeout):
            candidate=copy.deepcopy(self.candidate)
            candidate.update(model='native/fixture',native_runtimes=[native_runtime(Path(work)/'proof')])
            return bind_artifact(Path(data)/output,candidate)
        def reviews(package,candidate,data,work,*args):
            result=native_reviews(package,candidate,Path(work)/'reviews')
            for i,item in enumerate(result):
                item['metadata_title_review']=self.review()['metadata_title_review']
                bind_artifact(Path(work)/f'bound_{i}.json',item)
            return result
        with patch('native_oauth.revise_book.run_stage',side_effect=stage), \
             patch('native_oauth.revise_book.run_independent_reviews',side_effect=reviews), \
             patch('native_oauth.revise_book.get_session_monitor',return_value=Mock()), \
             contextlib.redirect_stdout(io.StringIO()):
            revise_chapter(self.book,self.job,1,translator_model='fixture',max_repairs=0)
        approved=read_approval(self.book,1)
        self.assertEqual(approved['rendered']['title'],'Chương 1: Tỏ tình')
        self.assertEqual(approved['rendered']['paragraphs'],['Anh ấy không cam lòng.','Cô ấy đi rồi.'])
        aligned=copy.deepcopy(approved['candidate']) if 'candidate' in approved else read_json(approved['path'])
        aligned['title_vi']='Chương 1: Tiêu đề bị sửa'
        with self.assertRaisesRegex(ValueError,'Separate title differs'):
            require_approved(self.source,aligned,render_text(aligned['bilingual_alignment']),self.book)

    def test_wave_preserves_existing_schema_and_exposes_separate_title(self):
        value={'evidence':{'package':{'segments':self.package['segments']},'candidate':self.candidate}}
        self.assertEqual(set(chapter_wave_data(1,value)),{'chapter','source','target'})
        value['evidence']['package']=self.package
        raw,target=chapter_texts(chapter_wave_data(1,value))
        self.assertEqual(raw['c0001title'],'第1章 告白')
        self.assertEqual(target['c0001title'],'Chương 1: Tỏ tình')


class FinalPilotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.book=self.root/'production';self.out=self.root/'pilot'
        for ch in range(1,11):
            source={'version':'bns-source-v1','book_id':'fixture','chapter':ch,'source_ref':'fixture',
                'title':f'第{ch}章 測試','paragraph_count':1,
                'segments':[{'id':f'c{ch:04d}p0001','source':f'第{ch}章 測試'}]}
            source['package_hash']=digest(source)
            write_json(self.book/'sources'/f'source_chapter_{ch:04d}.json',source)
        write_json(self.book/'lore.json',{'characters':{'林御':'Lâm Ngự'}})
        write_json(self.book/'toc.json',[{}]*2115)

    def test_prepare_has_identical_sources_no_legacy_or_production_approval(self):
        (self.book/'output_dich').mkdir();(self.book/'output_dich/old.txt').write_text('Old text')
        spec=prepare(self.book,self.out,10)
        self.assertEqual(spec['execution_order'],['B','A','C'])
        self.assertEqual(spec['models']['C'],'gemini-3.8-flash-high')
        self.assertEqual(spec['max_workers'],3)
        for ch in range(1,11):
            name=f'sources/source_chapter_{ch:04d}.json'
            self.assertEqual((self.out/'A/book'/name).read_bytes(),(self.out/'B/book'/name).read_bytes())
            self.assertEqual((self.out/'A/book'/name).read_bytes(),(self.out/'C/book'/name).read_bytes())
        self.assertFalse((self.out/'A/book/output_dich').exists())
        self.assertFalse((self.book/'approved').exists())
        with self.assertRaises(ValueError):prepare(self.book,self.out,10)

    def test_changed_isolated_or_production_canon_is_blocked(self):
        prepare(self.book,self.out,10)
        path=self.out/'A/book/lore.json';original=path.read_bytes()
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError,'canon'):assert_frozen(self.out)
        path.write_bytes(original)
        (self.book/'lore.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Production'):assert_frozen(self.out)

    def test_code_change_after_freeze_is_blocked(self):
        prepare(self.book,self.out,10)
        with patch('native_oauth.final_translation_pilot.code_snapshot',return_value={'changed':'x'}):
            with self.assertRaisesRegex(ValueError,'code changed'):assert_frozen(self.out)

    def test_metrics_include_failed_calls_and_do_not_invent_unknown_tokens(self):
        prepare(self.book,self.out,10)
        write_json(self.out/'A/job/translator.runtime/runtime.json',{'status':'TIMEOUT','duration_seconds':9,'partial_output':True,'result':None})
        rows=runtime_rows(self.out/'A/job')
        self.assertEqual(rows[0]['status'],'TIMEOUT');self.assertIsNone(rows[0]['total_tokens'])
        result=report(self.out)
        self.assertEqual(set(result['arms']),{'A','B','C'})
        self.assertEqual(result['arms']['A']['native_failed_or_partial'],1)
        self.assertIsNone(result['arms']['A']['approved_source_chars_per_hour'])
        self.assertIsNone(result['arms']['A']['projected_full_book_hours'])
        self.assertIsNone(result['arms']['A']['token_totals']['total_tokens'])

    def test_unapproved_prefix_cannot_become_complete_from_measurement_flag(self):
        prepare(self.book,self.out,10)
        write_json(self.out/'A/measurement.json',{'status':'COMPLETE','active_wall_seconds':1})
        result=report(self.out)
        self.assertNotEqual(result['arms']['A']['status'],'COMPLETE')

    def test_pilot_cannot_be_nested_inside_production_book(self):
        with self.assertRaisesRegex(ValueError,'separate'):prepare(self.book,self.book/'pilot',10)

    def test_changed_experiment_settings_are_blocked(self):
        prepare(self.book,self.out,10)
        spec=read_json(self.out/'experiment.json');spec['max_workers']=6
        write_json(self.out/'experiment.json',spec)
        with self.assertRaisesRegex(ValueError,'configuration changed'):assert_frozen(self.out)

    def test_stress_repairs_real_candidate_and_never_creates_approvals(self):
        with patch('native_oauth.final_translation_pilot.STRESS_CHAPTERS',(8,9)):
            prepare(self.book,self.out,10)
        for arm in ARMS:write_json(self.out/arm/'measurement.json',{'status':'COMPLETE'})
        attempts={}
        def stage(data,work,role,model,protocol,output,timeout):
            package=read_json(Path(data)/'source.json');ch=package['chapter']
            attempts[ch]=attempts.get(ch,0)+1
            payload={'package_hash':package['package_hash'],'segments':[
                {'id':r['id'],'text':'' if attempts[ch]==1 else 'Chương thử nghiệm'} for r in package['segments']],
                'model':'native/'+model,'native_runtimes':[native_runtime(Path(work)/'proof',model=model)]}
            return bind_artifact(Path(data)/output,payload)
        def reviews(package,candidate,data,work,*args):
            return native_reviews(package,candidate,Path(work)/'reviews')
        with patch.dict('os.environ',{'ANTIGRAVITY_CONVERSATION_ID':'offline-fixture'}), \
             patch('native_oauth.pipeline_native.run_stage',side_effect=stage), \
             patch('native_oauth.native_review.run_independent_reviews',side_effect=reviews):
            run_stress(self.out,'A')
        result=read_json(self.out/'A/stress_result.json')
        self.assertEqual(result['status'],'DIAGNOSTIC_PASS_NOT_APPROVAL')
        self.assertFalse(result['approval_eligible'])
        self.assertTrue(all(row['attempts']==2 for row in result['chapters']))
        self.assertEqual(read_json(result['chapters'][0]['candidate'])['segments'][0]['text'],'Chương thử nghiệm')
        self.assertFalse((self.out/'A/stress_book/approved').exists())
        self.assertFalse((self.book/'approved').exists())

    def test_negation_and_royal_reference_are_literal_cues_not_rewrites(self):
        rows=[{'id':'c0001p0001','source':'他不甘心，皇帝說：「孤不能不去。」'}]
        before=copy.deepcopy(rows);anchors=source_anchors(rows)
        self.assertEqual(rows,before)
        self.assertTrue({'negation_scope','royal_self_reference'} <= {r['kind'] for r in anchors})
        self.assertTrue(all(rows[0]['source'][r['start']:r['end']]==r['source_quote'] for r in anchors))

    def test_high_cannot_skip_unfinished_low(self):
        spec=prepare(self.book,self.out,10)
        write_json(self.out/'B/measurement.json',{'status':'COMPLETE'})
        with self.assertRaisesRegex(ValueError,'before continuing: A'):require_prior_arms(self.out,spec,'C')
        write_json(self.out/'A/measurement.json',{'status':'BLOCKED'})
        require_prior_arms(self.out,spec,'C')

    def test_blocked_high_does_not_hide_other_completed_arm_stress(self):
        spec=prepare(self.book,self.out,10)
        for arm in ARMS:write_json(self.out/arm/'measurement.json',{'status':'COMPLETE' if arm!='C' else 'BLOCKED'})
        require_prior_arms(self.out,spec,'A',stress=True)
        with self.assertRaisesRegex(ValueError,'this production-path arm'):require_prior_arms(self.out,spec,'C',stress=True)

    def test_blinded_output_contains_all_three_final_candidates(self):
        prepare(self.book,self.out,10)
        for arm in ARMS:write_json(self.out/arm/'measurement.json',{'status':'COMPLETE','active_wall_seconds':10})
        progress={'export_ready':True,'approved_chapters':list(range(1,11)),'approved_count':10}
        gates={'wave_gates':{'1':{'status':'PASS'},'6':{'status':'PASS'}}}
        def approval(book,ch):
            source=read_json(Path(book)/'sources'/f'source_chapter_{ch:04d}.json')
            return {'evidence':{'package':{'segments':source['segments']},
                    'candidate':{'segments':[{'id':r['id'],'text':'Chương thử nghiệm'} for r in source['segments']]}}}
        with patch('native_oauth.book_progress.book_progress',return_value=progress), \
             patch('native_oauth.wave_review.validate_wave_gates'), \
             patch('native_oauth.book_publication.read_manifest',return_value=gates), \
             patch('native_oauth.book_publication.read_approval',side_effect=approval):
            result=report(self.out)
        key=read_json(self.out/'comparison_key.json')
        self.assertEqual(set(key),{'X','Y','Z'});self.assertEqual(set(key.values()),{'A','B','C'})
        sample=read_json(self.out/'blinded_final/chapter_0001.json')
        self.assertEqual(set(sample['candidates']),{'X','Y','Z'})
        self.assertTrue(all(arm['status']=='COMPLETE' for arm in result['arms'].values()))
