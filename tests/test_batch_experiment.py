"""Offline worker/benchmark regressions; native OAuth calls are always mocked."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from semantic_gate import digest, read_json, write_json
from native_oauth.batch_contract import build_story_state, make_scene_contract
from native_oauth.batch_experiment import protocol, prepare_job, execute_job, run_manifest
from native_oauth.batch_source_prepass import extract_ledger
from native_oauth import prepare_batch_benchmark


def source_package(chapter, paragraphs, glossary=None):
    value = {'version': 'raw-source-benchmark-1', 'chapter': chapter, 'title': 'fixture',
             'glossary': glossary or {},
             'segments': [{'id': f'c{chapter:04d}p{i:04d}', 'source': text}
                          for i, text in enumerate(paragraphs, 1)]}
    value['package_hash'] = digest(value)
    return value


def analysis(package):
    return {'source_package_hash': package['package_hash'], 'provenance': {'engine': 'fixture'},
            'segments': [{'id': s['id'], 'source_hash': digest(s['source']), 'ner': [['Nh', '张羽', 0, 1]],
                          'srl': [{'predicate': '说', 'arguments': [['ARG0', '张羽', 0, 1]]}],
                          'dep': [], 'sdp': []} for s in package['segments']]}


def contract(job_id='offline-scene'):
    package = source_package(1, ['张羽说：“先等一等。”', '没有超过两万，也不是二十亿。', '周伟答应后来再说。'],
                             {'张羽': 'Trương Vũ'})
    state = build_story_state([package], [], package['glossary'], {'genre': 'hien_dai'})
    job = make_scene_contract(state, [package], ['c0001p0002'], overlap=1, job_id=job_id)
    job['parser_hints'] = [analysis(package)['segments'][1]]
    job['contract_hash'] = digest({k: v for k, v in job.items() if k != 'contract_hash'})
    return job


def candidate(job_contract):
    return {k: job_contract[k] for k in ('job_id', 'contract_hash', 'state_hash')} | {
        'segments': [{'id': s['id'], 'text': 'Bản thử ngoại tuyến.'} for s in job_contract['owned_segments']],
        'uncertainties': []}


def frozen_benchmark(root):
    """Minimal realistic lock, parser packages and source files; no network."""
    folder = root/'native_oauth/batch_benchmark'
    folder.mkdir(parents=True)
    real = [source_package(1, ['张羽说话。'], {'张羽': 'Trương Vũ'}),
            source_package(2, ['后来张羽回家。'], {'张羽': 'Trương Vũ'})]
    synthetic = source_package(101, ['她拒绝了。'])
    chapters = []
    for package in real:
        path = folder/f"source_{package['chapter']}.json"
        write_json(path, package)
        chapters.append({'chapter': package['chapter'], 'split': 'development' if package['chapter']==1 else 'heldout',
                         'source_package_path': str(path), 'source_package_hash': package['package_hash'],
                         'source_package_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'full_source_segments': package['segments'], 'excerpt_segments': package['segments']})
    write_json(folder/'synthetic_101.source.json', synthetic)
    locked = {'chapters': chapters, 'synthetic_scenarios': [{'chapter': 101, 'excerpt_segments': synthetic['segments']}],
              'reviewer_cases': [{'obligations': 'GOLD_SENTINEL_NOT_VISIBLE', 'expected_vietnamese': 'GOLD_VI_SENTINEL'}]}
    locked['corpus_sha256'] = digest(locked)
    write_json(folder/'locked_cases.json', locked)
    write_json(root/'native_oauth/genre_profiles.json', {'version': 'fixture', 'common': ['Natural Vietnamese'],
               'profiles': {'hybrid_cyberpunk_tu_tien': {}, 'hien_dai': {}}, 'certification': 'not BNS approval'})
    write_json(root/'native_oauth/research/chapter1_ltp_analysis.json', analysis(real[0]))
    write_json(folder/'analysis/chapter_0002.analysis.json', analysis(real[1]))
    write_json(folder/'analysis/chapter_0101.analysis.json', analysis(synthetic))
    return folder, locked, real


class BatchExperimentTests(unittest.TestCase):
    def test_worker_projection_retains_every_owned_and_neighbor_chinese_exactly(self):
        value = contract()
        body = protocol(value)
        projected = json.loads(body.split('CONTRACT WORKER VIEW:\n', 1)[1])
        for field in ('owned_segments', 'neighbor_segments'):
            self.assertEqual(projected[field], [{'id': s['id'], 'source': s['source']} for s in value[field]])
        self.assertEqual(projected['parser_hints'][0]['srl'][0]['arguments'], [['ARG0', '张羽']])
        self.assertIn('predicted roles only', body)

    def test_projection_excludes_gold_and_unrequested_parser_payloads(self):
        value = contract()
        value['reviewer_cases'] = {'gold': 'GOLD_SENTINEL'}
        value['parser_hints'][0]['expected_vietnamese'] = 'GOLD_VI_SENTINEL'
        value['parser_hints'][0]['dep'] = 'HUGE_DEP_TREE_SENTINEL'
        body = protocol(value)
        for hidden in ('GOLD_SENTINEL', 'GOLD_VI_SENTINEL', 'HUGE_DEP_TREE_SENTINEL'):
            self.assertNotIn(hidden, body)

    def test_prepare_job_rejects_old_candidate_and_preserves_it(self):
        value = contract()
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)/value['job_id']; work.mkdir()
            original = '{"old": "do not overwrite"}'
            (work/'candidate.json').write_text(original, encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fresh workspace'):
                prepare_job(value, temporary, 'gemini-3.8-flash-low')
            self.assertEqual((work/'candidate.json').read_text(encoding='utf-8'), original)

    def test_prepare_job_rejects_old_runtime_even_without_candidate(self):
        value = contract()
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)/value['job_id']/'runtime'; work.mkdir(parents=True)
            (work/'events.jsonl').write_text('old runtime', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'fresh workspace'):
                prepare_job(value, temporary, 'gemini-3.8-flash-low')

    def test_attested_native_model_mismatch_blocks_candidate(self):
        value = contract()
        with tempfile.TemporaryDirectory() as temporary:
            job = prepare_job(value, temporary, 'gemini-3.8-flash-low')
            def fake_run(prompt, runtime_folder, *args):
                runtime_folder.mkdir()
                write_json(job['work']/'candidate.json', candidate(value))
                (runtime_folder/'events.jsonl').write_text(json.dumps({'event': 'init', 'init': {
                    'model': 'gemini-3.8-flash-medium'}})+'\n', encoding='utf-8')
                return {'status': 'SUCCESS', 'conversation_id': 'offline', 'usage': {'total_tokens': 12}}
            with patch('native_oauth.batch_experiment.run', side_effect=fake_run) as native:
                result = execute_job(job)
            self.assertEqual(native.call_count, 1)
            self.assertEqual(result['status'], 'BLOCKED')
            self.assertIn('model mismatch', result['reason'])
            self.assertNotIn('candidate_hash', result)

    def test_exact_model_success_remains_unreviewed(self):
        value = contract()
        with tempfile.TemporaryDirectory() as temporary:
            job = prepare_job(value, temporary, 'gemini-3.8-flash-low')
            def fake_run(prompt, runtime_folder, *args):
                runtime_folder.mkdir()
                write_json(job['work']/'candidate.json', candidate(value))
                (runtime_folder/'events.jsonl').write_text(json.dumps({'event': 'init', 'init': {
                    'model': 'gemini-3.8-flash-low'}})+'\n', encoding='utf-8')
                return {'status': 'SUCCESS', 'conversation_id': 'offline', 'usage': {'total_tokens': 12}}
            with patch('native_oauth.batch_experiment.run', side_effect=fake_run):
                result = execute_job(job)
            self.assertEqual(result['status'], 'DRAFT_COMPLETE_UNREVIEWED')
            self.assertNotIn('publish', result)

    def test_unknown_usage_stops_before_scheduling_next_wave(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            jobs = []
            for i in range(4):
                path = base/f'contract-{i}.json'; write_json(path, contract(f'offline-{i}'))
                jobs.append({'contract': str(path), 'model': 'gemini-3.8-flash-low'})
            manifest = {'jobs': jobs, 'max_concurrency': 2, 'workspace': str(base/'workers'),
                        'result_path': str(base/'report.json')}
            def fake_execute(job):
                return {'job_id': job['contract']['job_id'], 'status': 'DRAFT_COMPLETE_UNREVIEWED',
                        'runtime': {'usage': {}}}
            with patch('native_oauth.batch_experiment.execute_job', side_effect=fake_execute) as execute:
                report = run_manifest(manifest)
            self.assertEqual(execute.call_count, 2)
            self.assertEqual(report['attempted_jobs'], 2)
            self.assertTrue(report['usage_unknown'])
            self.assertEqual(report['status'], 'BLOCKED')
            self.assertFalse((base/'workers/offline-2').exists())

    def test_prepass_glossary_conflicts_block_before_workers(self):
        first = source_package(1, ['张羽来了。'], {'张羽': 'Trương Vũ'})
        second = source_package(2, ['张羽又来了。'], {'张羽': 'Trương Ngọc'})
        with self.assertRaisesRegex(ValueError, 'Conflicting canonical'):
            extract_ledger([first, second], [analysis(first), analysis(second)])

    def test_prepass_requires_full_actual_parser_source_coverage(self):
        package = source_package(1, ['张羽来了。', '后来他走了。'], {'张羽': 'Trương Vũ'})
        parsed = analysis(package)
        parsed['segments'].pop()
        with self.assertRaisesRegex(ValueError, 'coverage mismatch'):
            extract_ledger([package], [parsed])
        parsed = analysis(package); parsed['segments'][0]['source_hash'] = 'different'
        with self.assertRaisesRegex(ValueError, 'quote mismatch'):
            extract_ledger([package], [parsed])

    def test_prepass_keeps_source_quotes_and_does_not_assert_coreference(self):
        package = source_package(1, ['张羽没有杀死周伟。'], {'张羽': 'Trương Vũ'})
        entries = extract_ledger([package], [analysis(package)])
        self.assertEqual(entries[0]['references'][0]['source_quote'], package['segments'][0]['source'])
        self.assertNotIn('interpretation', entries[0])
        self.assertNotIn('coreference', entries[0])

    def test_prepared_workers_never_receive_reviewer_gold(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            frozen_benchmark(root)
            with patch.object(prepare_batch_benchmark, 'ROOT', root):
                manifest_path = prepare_batch_benchmark.prepare()
            manifest = read_json(manifest_path)
            self.assertEqual(len(manifest['jobs']), 8)
            for job in manifest['jobs']:
                body = protocol(read_json(job['contract']))
                self.assertNotIn('GOLD_SENTINEL_NOT_VISIBLE', body)
                self.assertNotIn('GOLD_VI_SENTINEL', body)

    def test_replaced_source_and_matching_parser_cannot_reuse_old_corpus_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder, locked, real = frozen_benchmark(root)
            changed = source_package(2, ['被替换的张羽故事。'], {'张羽': 'Trương Vũ'})
            write_json(locked['chapters'][1]['source_package_path'], changed)
            write_json(folder/'analysis/chapter_0002.analysis.json', analysis(changed))
            with patch.object(prepare_batch_benchmark, 'ROOT', root):
                with self.assertRaises(ValueError):
                    prepare_batch_benchmark.prepare()


if __name__ == '__main__':
    unittest.main()
