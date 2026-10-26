"""Real failure-path regressions; every transport/model is offline or mocked."""
import ast
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from semantic_gate import digest
from native_oauth.chapter_integrity import inspect_chapter, render_text, require_approved
from native_oauth.chapter_runner import run_chapter, split_scenes
from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.quality_gate import QualityGate4A
from native_oauth.spot_auditor import SpotAuditor4B
from native_oauth.run_agy import classify_completion, require_complete_runtime, IncompleteNativeOutput, run
import native_oauth.session_monitor as monitor

ROOT = Path(__file__).resolve().parents[1]


def source_fixture(count=4):
    source = {'book_id': 'test', 'chapter': 1, 'title': 'Test',
              'segments': [{'id': f'c0001p{i:04d}', 'source': f'这是段落{i}。'} for i in range(1, count + 1)]}
    source['package_hash'] = digest(source)
    return source


class NativeCompletionTests(unittest.TestCase):
    def test_success_with_active_response_is_not_complete(self):
        events = [{'event': 'step_update', 'step_update': {'step_type': 'agent_response', 'state': 'ACTIVE'}},
                  {'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'unfinished'}}]
        result = classify_completion(events, '', 0)
        self.assertEqual(result['status'], 'INCOMPLETE_STEP')
        self.assertTrue(result['partial_output'])

    def test_archived_six_cut_scenes_are_timeouts_despite_cli_success(self):
        for chapter, scene in ((239, 2), (248, 1), (299, 1), (306, 1), (310, 2), (318, 2)):
            folder = ROOT / f'native_oauth/book_49736/runs/chapter_{chapter:04d}/scene_{scene}/runtime'
            events = [json.loads(line) for line in (folder / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
            completion = classify_completion(events, (folder / 'diagnostics.txt').read_text(encoding='utf-8'), 0)
            self.assertEqual(completion['status'], 'PARTIAL_TIMEOUT')
            with self.assertRaises(IncompleteNativeOutput):
                require_complete_runtime(dict(completion, exit_code=0), 'gemini-3.8-flash-high')

    def test_native_driver_uses_diagnostics_and_preserves_real_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            prompt = folder / 'prompt.txt'
            prompt.write_text('synthetic', encoding='utf-8')
            child = Mock()
            child.poll.side_effect = [None, 0]

            def popen(*args, **kwargs):
                kwargs['stdout'].write(json.dumps({'event': 'init', 'init': {'model': 'fixture'}}) + '\n')
                kwargs['stdout'].write(json.dumps({'event': 'result', 'result': {'status': 'SUCCESS', 'response': 'partial'}}) + '\n')
                kwargs['stdout'].flush()
                kwargs['stderr'].write('[agy] print timeout after 2m30s with turn in progress; returning partial output\n')
                kwargs['stderr'].flush()
                return child

            with patch('native_oauth.run_agy.subprocess.Popen', side_effect=popen), patch('native_oauth.run_agy.time.sleep'), \
                    patch('native_oauth.workflow_guard.before_native'):
                runtime = run(prompt, folder / 'runtime', model='fixture')
            self.assertEqual(runtime['status'], 'PARTIAL_TIMEOUT')
            self.assertEqual(runtime['exit_code'], 0)
            child.terminate.assert_not_called()

    def test_complete_transport_requires_reported_model(self):
        base = {'status': 'SUCCESS', 'exit_code': 0, 'actual_model': 'fixture', 'result': {'response': 'complete'}}
        self.assertEqual(require_complete_runtime(base, 'fixture'), 'complete')
        with self.assertRaises(ValueError):
            require_complete_runtime(dict(base, actual_model='other'), 'fixture')


class GateCoverageTests(unittest.TestCase):
    def setUp(self):
        self.gate = QualityGate4A()
        self.contract, _ = UnifiedSemanticPreprocessor().build_scene_contract(1, 1, ['他走了。'], [], [], genre='URBAN_MODERN')

    def test_empty_duplicate_and_reordered_output_blocked(self):
        for text, count in [('§1 ', 1), ('§1 Một.\n§1 Hai.', 1), ('§2 Hai.\n§1 Một.', 2)]:
            self.assertFalse(self.gate.verify_paragraphs(text, count, self.contract).is_pass)

    def test_multiline_is_preserved_without_losing_content(self):
        result = self.gate.verify_paragraphs('§1 Dòng đầu.\nCâu thứ hai.', 1, self.contract)
        self.assertTrue(result.is_pass)
        self.assertIn('Câu thứ hai.', result.sanitized_paragraphs[1])

    def test_repair_cannot_pad_or_approve_missing_paragraphs(self):
        result = self.gate.verify_paragraphs('§1 Một.', 2, self.contract)
        auditor = SpotAuditor4B(self.gate)
        tasks = auditor.identify_repair_targets(result, ['甲', '乙'], self.contract)
        self.assertFalse(tasks)
        after = auditor.apply_deterministic_repair(result, self.contract)
        self.assertFalse(after.is_pass)
        self.assertNotIn(2, after.sanitized_paragraphs)

    def test_urban_genre_is_shared_by_contract_and_gate(self):
        self.assertEqual(self.contract.genre, 'URBAN_MODERN')
        result = self.gate.verify_paragraphs('§1 Anh ta rời đi.', 1, self.contract)
        self.assertNotIn('MODERN_PRONOUN_IN_NARRATIVE', [v.error_code for v in result.violations])


class ChapterBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = self.root / 'book/sources'
        self.output = self.root / 'book/output_dich'
        self.sources.mkdir(parents=True)
        self.output.mkdir()
        self.source = source_fixture()
        self.write_source()
        self.patches = [patch.object(monitor, 'ROOT', self.root),
                        patch.object(monitor, 'get_active_artifact_dir', return_value=self.root / 'artifacts'),
                        patch.object(monitor.SessionMonitor, '_instance', None)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def write_source(self):
        (self.sources / 'source_chapter_0001.json').write_text(json.dumps(self.source), encoding='utf-8')

    def execute(self, callback, force=False, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return run_chapter(1, 'test', 'Synthetic', 'URBAN_MODERN', self.sources, self.output,
                               callback, 'fixture', force, total_chapters=4, **kwargs)

    def test_failure_never_writes_production_or_complete_draft(self):
        def callback(scene, paragraphs, context):
            return {i: 'Bản thử.' for i in range(1, len(paragraphs) + 1)}, '', False
        self.assertFalse(self.execute(callback))
        self.assertEqual(list(self.output.iterdir()), [])
        self.assertFalse(list((self.root / 'book/drafts').glob('*.txt')))
        receipt = json.loads((self.root / 'book/drafts/chuong_0001.receipt.json').read_text())
        self.assertEqual(receipt['status'], 'BLOCKED')
        self.assertEqual(monitor.SessionMonitor._instance.completed_count, 0)

    def test_timeout_discards_partial_attempt_and_regenerates_bounded_children(self):
        calls = []
        def callback(scene, paragraphs, context):
            calls.append(len(paragraphs))
            if len(paragraphs) > 2:
                raise IncompleteNativeOutput('synthetic timeout')
            return {i: 'Bản thử ' + p for i, p in enumerate(paragraphs, 1)}, '', True
        self.assertTrue(self.execute(callback))
        self.assertEqual(calls, [4, 2, 2])
        draft = json.loads((self.root / 'book/drafts/chuong_0001.dich.json').read_text(encoding='utf-8'))
        self.assertEqual(inspect_chapter(self.source, draft), [])
        self.assertEqual([r['raw_zh'] for r in draft['bilingual_alignment']], [r['source'] for r in self.source['segments']])
        self.assertFalse(list(self.output.iterdir()))

    def test_cache_ignores_legacy_txt_and_rejects_changed_source(self):
        legacy = self.output / 'chuong_0001.txt'
        legacy.write_text('Bất c', encoding='utf-8')
        calls = []
        def callback(scene, paragraphs, context):
            calls.append(scene)
            return {i: 'Bản thử.' for i in range(1, len(paragraphs) + 1)}, '', True
        self.assertTrue(self.execute(callback))
        self.assertTrue(self.execute(callback))
        self.assertEqual(len(calls), 1)
        self.source['segments'][0]['source'] += '变更'
        self.source['package_hash'] = digest({k: v for k, v in self.source.items() if k != 'package_hash'})
        self.write_source()
        self.assertFalse(self.execute(callback))
        self.assertEqual(len(calls), 1)
        self.assertEqual(legacy.read_text(encoding='utf-8'), 'Bất c')

    def test_oversized_single_paragraph_is_blocked_before_transport(self):
        with self.assertRaises(ValueError):
            split_scenes(['甲' * 3201])

    def test_all_four_entrypoints_use_shared_boundary(self):
        import importlib
        for name in ('book_14713.batch_pipeline_runner', 'book_16014.batch_pipeline_runner',
                     'book_49736.batch_pipeline_runner', 'book_49736.wujian_pipeline_runner'):
            module = importlib.import_module('native_oauth.' + name)
            args = [1, None, None, None] + ([None] if 'wujian' in name else [])
            with patch.object(module, 'run_chapter', return_value=False) as boundary:
                self.assertFalse(module.process_chapter(*args))
                boundary.assert_called_once()

    def test_actual_scene_does_not_pad_missing_ids(self):
        import native_oauth.book_49736.wujian_pipeline_runner as module
        from native_oauth.cartridges.urban_suspense import UrbanSuspenseCartridge
        with patch.object(module, 'RUNS_DIR', self.root / 'runs'), patch.object(module, 'invoke_llm', return_value='§1 Một đoạn.'):
            translated, _, passed = module.translate_scene(
                UnifiedSemanticPreprocessor(), QualityGate4A(), SpotAuditor4B(), UrbanSuspenseCartridge(),
                1, 1, ['他走了。', '她走了。'], '', 'fixture')
        self.assertFalse(passed)
        self.assertEqual(set(translated), {1})

    def test_source_changed_during_generation_is_not_committed(self):
        def callback(scene, paragraphs, context):
            changed = copy.deepcopy(self.source)
            changed['segments'][0]['source'] += '改'
            changed['package_hash'] = digest({k: v for k, v in changed.items() if k != 'package_hash'})
            (self.sources / 'source_chapter_0001.json').write_text(json.dumps(changed), encoding='utf-8')
            return {i: 'Bản thử.' for i in range(1, len(paragraphs) + 1)}, '', True
        self.assertFalse(self.execute(callback))
        self.assertFalse(list((self.root / 'book/drafts').glob('*.txt')))

    def test_native_runtime_evidence_is_required_and_tampering_blocks_cache(self):
        runtime_root = self.root / 'runs'
        calls = []
        def callback(scene, paragraphs, context):
            calls.append(scene)
            folder = runtime_root / 'chapter_0001' / f'scene_{scene}' / 'runtime'
            folder.mkdir(parents=True, exist_ok=True)
            (folder / 'runtime.json').write_text(json.dumps({
                'status': 'SUCCESS', 'exit_code': 0, 'actual_model': 'fixture', 'result': {'response': '\n'.join(f'§{i} Bản thử.' for i in range(1,len(paragraphs)+1))}}), encoding='utf-8')
            return {i: 'Bản thử.' for i in range(1, len(paragraphs) + 1)}, '', True
        self.assertTrue(self.execute(callback, runtime_root=runtime_root))
        file = runtime_root / 'chapter_0001/scene_1/runtime/runtime.json'
        bad = json.loads(file.read_text())
        bad['status'] = 'PARTIAL_TIMEOUT'
        file.write_text(json.dumps(bad), encoding='utf-8')
        self.assertFalse(self.execute(callback, runtime_root=runtime_root))
        self.assertEqual(len(calls), 1)

    def test_progress_uses_verified_drafts_and_polish_keeps_one_alignment(self):
        import native_oauth.book_49736.status_tracker as tracker
        import native_oauth.book_49736.surgical_polish_325 as polisher
        def callback(scene, paragraphs, context):
            return {i: 'Cùng với việc trời nổi gió.' for i in range(1, len(paragraphs) + 1)}, '', True
        self.assertTrue(self.execute(callback))
        legacy = self.output / 'chuong_0001.txt'
        legacy.write_text('Bất c', encoding='utf-8')
        with patch.object(tracker, 'BOOK_DIR', self.sources.parent), patch.object(tracker, 'LIVE_STATUS_FILE', self.root / 'status.json'):
            status = tracker.calculate_progress(target_chapters=4)
        self.assertEqual(status['completed_chapters_count'], 1)
        with patch.object(polisher, 'OUTPUT_DIR', self.output), patch.object(polisher, 'BOOK_DIR', self.sources.parent):
            report = polisher.polish_chapter(1)
        self.assertEqual(report['status'], 'UNREVIEWED_PROPOSAL')
        folder = self.sources.parent / 'polished_drafts'
        candidate = json.loads((folder / 'chuong_0001.dich.json').read_text(encoding='utf-8'))
        self.assertEqual(inspect_chapter(self.source, candidate, (folder / 'chuong_0001.txt').read_text(encoding='utf-8')), [])
        self.assertEqual(legacy.read_text(encoding='utf-8'), 'Bất c')

    def test_audit_counts_actual_records_instead_of_matching_metadata(self):
        import comprehensive_novel_audit as audit
        candidate = {'chapter_num': 1, 'total_paragraphs': 4, 'translated_paragraphs': 4,
                     'source_hash': self.source['package_hash'], 'bilingual_alignment': [
                         {'para_id': 'c0001p0001', 'raw_zh': self.source['segments'][0]['source'], 'translated_vi': 'Bất c'}]}
        (self.output / 'chuong_0001.txt').write_text('Bất c\n', encoding='utf-8')
        (self.output / 'chuong_0001.dich.json').write_text(json.dumps(candidate), encoding='utf-8')
        with patch.object(audit, 'SOURCES_DIR', self.sources), patch.object(audit, 'OUTPUT_DIR', self.output), contextlib.redirect_stdout(io.StringIO()):
            report = audit.run_full_audit(1, self.root / 'audit.json')
        self.assertEqual(report['total_paras'], 1)
        self.assertEqual(report['verified_chapters'], 0)
        self.assertIn('COVERAGE_IDS', report['integrity_findings'][0]['errors'])


class ApprovalAndMonitorTests(unittest.TestCase):
    def test_heuristic_score_cannot_approve_reversed_subject(self):
        from native_oauth.autonomous.self_healing_engine import AutonomousSelfHealingEngine
        from native_oauth.core.ast.semantic_parser import ASTNode, DiscourseType
        node = ASTNode('x', DiscourseType.NARRATION, '张三昨天晚上杀了李四。', '张三昨天晚上杀了李四。')
        _, ledger = AutonomousSelfHealingEngine().audit_and_heal_chapter(
            'fixture', [node], {'x': 'Lý Tứ đã giết Trương Tam vào tối hôm qua.'})
        self.assertFalse(ledger.publication_approved)

    def test_actual_book_loader_rejects_missing_chapter(self):
        path = ROOT / 'native_oauth/book_49736/build_ebooks.py'
        fn = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body
                  if isinstance(n, ast.FunctionDef) and n.name == 'load_all_chapters')
        with tempfile.TemporaryDirectory() as directory:
            namespace = {'TOTAL_CHAPTERS': 1, 'OUTPUT_DICH_DIR': Path(directory),
                         'BOOK_DIR': Path(directory), 'json': json, 'require_approved': require_approved,
                         'load_approved_chapters': __import__('native_oauth.book_publication',fromlist=['load_approved_chapters']).load_approved_chapters}
            exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), 'exec'), namespace)
            with self.assertRaisesRegex(ValueError, 'missing/extra chapters'):
                namespace['load_all_chapters']()

    def test_publication_needs_actual_review_and_exact_final_text(self):
        from tests.test_semantic_gate import fixture
        source, draft, reviews = fixture()
        candidate = {'chapter_num': source['chapter'], 'source_hash': source['package_hash'],
                     'total_paragraphs': len(source['segments']), 'translated_paragraphs': len(draft['segments']),
                     'bilingual_alignment': [{'para_id': s['id'], 'raw_zh': s['source'], 'translated_vi': t['text']}
                                             for s, t in zip(source['segments'], draft['segments'])]}
        text = render_text(candidate['bilingual_alignment'])
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            with self.assertRaises(ValueError):
                require_approved(source, candidate, text, folder)
            evidence = {'package': source, 'candidate': draft, 'reviews': reviews}
            (folder / 'review.json').write_text(json.dumps(evidence), encoding='utf-8')
            candidate['review_evidence'] = 'review.json'
            self.assertEqual(require_approved(source, candidate, text, folder)['status'], 'PASS')
            with self.assertRaises(ValueError):
                require_approved(source, candidate, text + 'Thêm nội dung.', folder)

    def test_monitor_is_idempotent_and_active_or_failed_is_not_completed(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(monitor, 'ROOT', Path(folder)), patch.object(monitor, 'get_active_artifact_dir', return_value=Path(folder) / 'artifacts'):
            mon = monitor.SessionMonitor('synthetic', 'Synthetic', 325)
            mon.record_worker_active('w', 325, 65)
            self.assertEqual(mon.completed_count, 0)
            self.assertIn('0.0%', mon.render_markdown_badge())
            for _ in range(2):
                mon.record_chapter_done(325, 'Test', 65, 'w', 2, 10, 1, True)
            self.assertEqual(mon.completed_count, 1)
            self.assertEqual(mon.total_words_accumulated, 10)
            mon2 = monitor.SessionMonitor('synthetic', 'Synthetic', 325)
            mon2.record_chapter_done(324, 'Test', 65, 'w2', 2, 20, 1, True)
            mon.record_chapter_done(325, 'Failed rerun', 65, 'w', 0, 0, 1, False)
            self.assertEqual(mon.completed_count, 1)
            self.assertEqual(mon.total_words_accumulated, 20)
            self.assertEqual(mon.history[-1].status, 'FAILED')


class CrawlIdentityTests(unittest.TestCase):
    def test_wrong_book_or_title_cannot_be_replaced_by_expected_title(self):
        from native_oauth.book_49736.crawl_chapters import validate_page_identity, normalized_title
        correct = '<div class="name">《尋找無間地獄》第58章 真.舔臉！</div>'
        validate_page_identity(correct, '58.第58章 真舔臉！')
        self.assertEqual(normalized_title('58.第58章 真舔臉！'), normalized_title('第58章 真.舔臉！'))
        for wrong in ('<div class="name">《別的書》第58章 真舔臉！</div>',
                      '<div class="name">《尋找無間地獄》第59章 其他</div>'):
            with self.assertRaises(ValueError):
                validate_page_identity(wrong, '第58章 真舔臉！')


if __name__ == '__main__':
    unittest.main()
