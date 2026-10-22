"""End-to-end offline approval tests, transport mocked; never real translation."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from semantic_gate import digest, evaluate, publish, write_json
from native_oauth.chapter_runner import run_chapter
from native_oauth.chapter_integrity import require_approved
from native_oauth.native_evidence import runtime_record
from native_oauth.native_review import run_independent_reviews
from native_oauth.pipeline_native import _run_stage, execute_pipeline
from native_oauth.review_book_chapter import prepare_review, review_and_promote
from native_oauth.urban_auditor import UrbanAuditor
from native_oauth.book_49736.style_and_entity_guard import StyleAndEntityGuard
from native_test_helpers import native_fixture, native_reviews, native_runtime


class AntigravityWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.monitor = Mock()
        for module in ('native_oauth.native_review', 'native_oauth.chapter_runner'):
            patcher = patch(module+'.get_session_monitor', return_value=self.monitor)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_runtime_mutation_invalidates_cached_native_approval(self):
        p,c,r = native_fixture(self.root)
        cache = {}
        policy = {'mode':'antigravity_sessions'}
        self.assertEqual(evaluate(p,c,r,cache,policy)['status'], 'PASS')
        runtime = Path(r[0]['native_runtimes'][0]['file'])
        raw = json.loads(runtime.read_text())
        raw['partial_output'] = True
        write_json(runtime, raw)
        self.assertEqual(evaluate(p,c,r,cache,policy)['status'], 'BLOCKED')

    def test_reviewer_cannot_reuse_translator_session(self):
        p,c,r = native_fixture(self.root)
        r[0]['native_runtimes'] = c['native_runtimes']
        r[0]['conversation_id'] = c['native_runtimes'][0]['conversation_id']
        self.assertEqual(evaluate(p,c,r,review_policy={'mode':'antigravity_sessions'})['status'], 'BLOCKED')

    def test_foreign_self_declared_identity_is_not_native_provenance(self):
        p,c,r = native_fixture(self.root)
        r[0]['identity_basis'] = 'self_report'
        self.assertEqual(evaluate(p,c,r,review_policy={'mode':'antigravity_sessions'})['status'], 'BLOCKED')

    def test_both_reviewers_have_physically_separate_workspaces(self):
        p,c,r = native_fixture(self.root)
        data = self.root/'inputs'
        data.mkdir()
        directories = []
        def stage(target, workspace, role, *args):
            directories.append(Path(workspace))
            self.assertTrue((Path(workspace)/'.agents/agents'/f'novel-{role}.md').exists())
            self.assertFalse(list(Path(workspace).rglob('peer.json')))
            write_json(Path(target)/'peer.json', {'finding':'must not leak to other reviewer'})
            return r[len(directories)-1]
        with patch('native_oauth.pipeline_native.run_stage', side_effect=stage):
            run_independent_reviews(p,c,data,self.root/'work','fixture','fixture')
        self.assertNotEqual(directories[0], directories[1])

    def test_native_worker_must_complete_before_artifact_is_accepted(self):
        p,c,_ = native_fixture(self.root)
        data = self.root/'data'
        data.mkdir()
        write_json(data/'source.json', p)
        def partial(*args):
            write_json(data/'draft.json', c)
            return {'status':'PARTIAL_TIMEOUT', 'partial_output':True, 'exit_code':0,
                    'actual_model':'fixture', 'result':{'response':'partial'}}
        with patch('native_oauth.pipeline_native.run', side_effect=partial):
            with self.assertRaises(ValueError):
                _run_stage(data,self.root,'translator','fixture','fixture','draft.json',5)

    def test_native_stage_rejects_source_mutation(self):
        p,c,_ = native_fixture(self.root)
        data = self.root/'data'
        data.mkdir()
        write_json(data/'source.json', p)
        def changed(*args):
            write_json(data/'source.json', {})
            write_json(data/'draft.json', c)
            return {'status':'SUCCESS','exit_code':0,'actual_model':'fixture',
                    'conversation_id':'fixture','result':{'response':'draft.json'}}
        with patch('native_oauth.pipeline_native.run', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'immutable source'):
                _run_stage(data,self.root,'translator','fixture','fixture','draft.json',5)

    def test_legacy_auditor_is_read_only_and_cannot_approve(self):
        folder = self.root/'book/output_dich'
        folder.mkdir(parents=True)
        path = folder/'chuong_0001.txt'
        original = 'CHƯƠNG 1\n\nChương 1\n\nAnh ấy 走 rồi.\n'
        path.write_text(original,encoding='utf-8')
        result = UrbanAuditor(folder.parent).audit_and_heal_chapter(1)
        self.assertEqual(path.read_text(encoding='utf-8'), original)
        self.assertFalse(result.is_gate_pass)
        self.assertEqual(result.cjk_cleared_count, 0)
        self.assertIn('untranslated_cjk', [f['kind'] for f in result.findings])

    def test_modern_ta_and_literal_archaic_phrases_are_advisory(self):
        guard = StyleAndEntityGuard()
        for text in ('“Chúng ta đi thôi.”', '“Cô ta nói vậy.”'):
            _, issues = guard.audit_paragraph('fixture', '普通對話。', text)
            self.assertNotIn('ERR_PRONOUN_MUTATION', [i['code'] for i in issues])
        passed, issues = guard.audit_paragraph('fixture', '普通對話。', '“Tại hạ xin cáo từ.”')
        self.assertTrue(passed)
        self.assertIn('ERR_PRONOUN_MUTATION', [i['code'] for i in issues])
        self.assertTrue(all(i['severity']=='WARNING' for i in issues))

    def draft_book(self, chapter=1, body='Anh ấy đi rồi.', raw_body='他走了。', force=False):
        book = self.root/'book'
        sources = book/'sources'
        sources.mkdir(parents=True, exist_ok=True)
        source = {'book_id':'fixture', 'chapter':chapter, 'title':'第一章',
                  'segments':[{'id':f'c{chapter:04d}p0001','source':'第一章'},
                              {'id':f'c{chapter:04d}p0002','source':raw_body}]}
        source['package_hash'] = digest(source)
        write_json(sources/f'source_chapter_{chapter:04d}.json', source)
        def callback(scene, paragraphs, context):
            import uuid
            path = runtime_root/f'chapter_{chapter:04d}'/f'scene_{scene}/runtime/runtime.json'
            write_json(path, {'status':'SUCCESS','exit_code':0,'actual_model':'fixture',
                             'conversation_id':f'translator-{chapter}', 'result':{'status':'SUCCESS','conversation_id':f'translator-{chapter}','response':f'§1 Chương {chapter}\n§2 {body}'}})
            runtime = json.loads(path.read_text(encoding='utf-8'))
            path.with_name('events.jsonl').write_text('\n'.join(json.dumps(e) for e in [
                {'event':'init','conversation_id':runtime['conversation_id'],'init':{'model':'fixture'}},
                {'event':'result','result':runtime['result']}]),encoding='utf-8')
            return {1:f'Chương {chapter}',2:body}, '', True
        import uuid
        runtime_root = book/'runs'/uuid.uuid4().hex
        self.assertTrue(run_chapter(chapter,'fixture','Fixture','URBAN',sources,book/'output_dich',
            callback,'fixture',force=force,total_chapters=max(1,chapter),runtime_root=runtime_root))
        return book, source

    def fake_reviews(self, package, candidate, *args):
        return native_reviews(package,candidate,self.root/'review_runtime')

    def test_complete_book_draft_review_promote_and_revalidate(self):
        book,source = self.draft_book()
        with patch('native_oauth.review_book_chapter.run_independent_reviews', side_effect=self.fake_reviews):
            path = review_and_promote(book,1,'fixture','fixture')
        approved = json.loads(path.read_text(encoding='utf-8'))
        text = path.with_name('chapter.txt').read_text(encoding='utf-8')
        self.assertEqual(require_approved(source,approved,text,path.parent)['status'], 'PASS')
        self.assertFalse(list((book/'output_dich').glob('*.txt')))
        self.assertEqual(approved['status'], 'APPROVED')
        evidence = json.loads(Path(approved['review_evidence']).read_text(encoding='utf-8'))
        self.assertEqual(evidence['review_policy']['mode'], 'antigravity_sessions')

    def test_failed_native_review_does_not_promote(self):
        book,_ = self.draft_book()
        def fail(package,candidate,*args):
            reviews = self.fake_reviews(package,candidate)
            reviews[0]['verdict']='FAIL'
            reviews[0]['issues']=[{'id':package['segments'][0]['id'],'reason':'fixture rejection'}]
            return reviews
        with patch('native_oauth.review_book_chapter.run_independent_reviews',side_effect=fail):
            with self.assertRaisesRegex(ValueError,'blocked promotion'):
                review_and_promote(book,1,'fixture','fixture')
        self.assertFalse((book/'approved').exists())

    def test_consecutive_approvals_use_bounded_verbatim_context(self):
        book,_ = self.draft_book()
        with patch('native_oauth.review_book_chapter.run_independent_reviews', side_effect=self.fake_reviews):
            review_and_promote(book,1,'fixture','fixture')
            self.draft_book(2)
            source,_,_,package,_ = prepare_review(book,2)
            self.assertEqual(package['context']['through_chapter'],1)
            self.assertLessEqual(len(package['context']['facts']),24)
            self.assertTrue(package['context']['facts'])
            path = review_and_promote(book,2,'fixture','fixture')
        approved = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(require_approved(source, approved,
            path.with_name('chapter.txt').read_text(encoding='utf-8'), path.parent)['status'],'PASS')
        previous = book/'sources/source_chapter_0001.json'
        previous.write_text('changed', encoding='utf-8')
        with self.assertRaises((ValueError, KeyError)):
            require_approved(source, approved, path.with_name('chapter.txt').read_text(encoding='utf-8'),path.parent)

    def test_resume_rejects_partial_success_receipt(self):
        from native_oauth.batch_run import verified_cached_result
        work = self.root/'cache/scene'
        contract = {'job_id':'scene','state_hash':'frozen','owned_segments':[{'id':'c0001p0001','source':'原文'}]}
        contract['contract_hash']=digest(contract)
        write_json(self.root/'contract.json',contract)
        runtime = {'status':'SUCCESS','exit_code':0,'actual_model':'fixture',
                   'partial_output':True,'conversation_id':'partial','result':{'response':'partial'}}
        candidate = {k:contract[k] for k in ('job_id','state_hash','contract_hash')}
        candidate.update(segments=[{'id':'c0001p0001','text':'Thử.'}], provenance={'conversation_id':'partial'})
        write_json(work/'candidate.json',candidate)
        write_json(work/'runtime/runtime.json',runtime)
        write_json(work/'worker_result.json',{'status':'DRAFT_COMPLETE_UNREVIEWED','actual_model':'fixture',
                    'candidate_hash':digest(candidate),'runtime':runtime})
        with self.assertRaises(ValueError):
            verified_cached_result({'contract':str(self.root/'contract.json'),'model':'fixture'},self.root/'cache')

    def test_canon_change_during_review_blocks_approval(self):
        book,_ = self.draft_book()
        write_json(book/'lore.json',{})
        def mutate(package,candidate,*args):
            reviews = self.fake_reviews(package,candidate)
            write_json(book/'lore.json',{'terms':{'新':'Mới'}})
            return reviews
        with patch('native_oauth.review_book_chapter.run_independent_reviews',side_effect=mutate):
            with self.assertRaises(ValueError):
                review_and_promote(book,1,'fixture','fixture')
        self.assertFalse((book/'approved').exists())

    def test_native_pipeline_defaults_to_two_native_reviews(self):
        p,c,_ = native_fixture(self.root)
        data = self.root/'inputs'
        data.mkdir()
        def reviews(package,candidate,*args):
            return native_reviews(package,candidate,self.root/'reviews')
        with patch('native_oauth.pipeline_native.prepare_inputs',return_value=(p,data)), \
             patch('native_oauth.pipeline_native.run_stage',return_value=c), \
             patch('native_oauth.pipeline_native.run_independent_reviews',side_effect=reviews) as checked:
            state = execute_pipeline('source','parse','hien_dai',self.root/'pipeline',
                                     'fixture','fixture','fixture',max_repairs=0)
        self.assertEqual(state['status'],'PASS')
        checked.assert_called_once()
        self.assertTrue(Path(state['output']).exists())

    def test_native_pipeline_failure_is_bounded_and_does_not_publish(self):
        p,c,_ = native_fixture(self.root)
        data = self.root/'inputs'
        data.mkdir()
        def reviews(package,candidate,*args):
            result = native_reviews(package,candidate,self.root/'reviews')
            result[0]['verdict']='FAIL'
            result[0]['issues']=[{'id':'c0001p0001','reason':'fixture error'}]
            return result
        with patch('native_oauth.pipeline_native.prepare_inputs',return_value=(p,data)), \
             patch('native_oauth.pipeline_native.run_stage',return_value=c) as generate, \
             patch('native_oauth.pipeline_native.run_independent_reviews',side_effect=reviews):
            state = execute_pipeline('source','parse','hien_dai',self.root/'pipeline',
                                     'fixture','fixture','fixture',max_repairs=1)
        self.assertEqual(state['status'],'BLOCKED')
        self.assertEqual(generate.call_count,2)
        self.assertFalse(list(data.rglob('*.publication.json')))
