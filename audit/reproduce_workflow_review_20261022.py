"""Read-only workflow audit, with destructive legacy behavior isolated in temp.

No real model calls, crawl jobs, translation workers or production edits.
"""
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from semantic_gate import digest, validate_package
from native_oauth.chapter_integrity import validate_source
from native_oauth.batch_run import verified_cached_result
from native_oauth.book_49736.style_and_entity_guard import StyleAndEntityGuard
from native_oauth.run_agy import require_complete_runtime
from native_oauth.urban_auditor import UrbanAuditor


DOCUMENTS = [
    'AGENTS.md', 'README.md', 'QUALITY_WORKFLOW.md', 'PIPELINE_GUIDE.md',
    'DEPLOYMENT_GUIDE.md', 'native_oauth/README.md', 'native_oauth/WORKFLOW.md',
    'native_oauth/BATCH_WORKFLOW.md', 'native_oauth/batch_route_design.md',
    'native_oauth/BATCH_RESULT_20261013.md',
    'native_oauth/batch_benchmark/benchmark_design.md',
    *[p.relative_to(ROOT).as_posix() for p in sorted((ROOT / '.agents').rglob('*.md'))],
]
CODE = [
    'quality_pipeline.py', 'pipeline_api.py', 'pipeline_dich_truyen.py',
    'agentic_batch_translator.py', 'semantic_gate.py',
    'native_oauth/pipeline_native.py', 'native_oauth/native_evidence.py', 'native_oauth/review_book_chapter.py', 'native_oauth/book_publication.py',
    'native_oauth/batch_run.py', 'native_oauth/batch_experiment.py',
    'native_oauth/batch_contract.py', 'native_oauth/batch_policy.py',
    'native_oauth/chapter_runner.py', 'native_oauth/chapter_integrity.py',
    'native_oauth/quality_gate.py', 'native_oauth/semantic_context.py',
    'native_oauth/scene_contract.py', 'native_oauth/session_monitor.py',
    'native_oauth/wave_orchestrator.py', 'native_oauth/zipper_coordinator.py',
    'native_oauth/autonomous/self_healing_engine.py', 'native_oauth/urban_auditor.py',
    'native_oauth/book_14713/batch_pipeline_runner.py',
    'native_oauth/book_16014/batch_pipeline_runner.py',
    'native_oauth/book_49736/batch_pipeline_runner.py',
    'native_oauth/book_49736/wujian_pipeline_runner.py',
    'native_oauth/book_49736/wave_runner.py',
    'native_oauth/book_49736/sliding_pool_runner.py',
    'native_oauth/book_49736/wave_orchestrator.py',
    'native_oauth/book_49736/style_and_entity_guard.py',
    'native_oauth/book_49736/surgical_polish_325.py',
    'native_oauth/book_49736/status_tracker.py', 'native_oauth/book_49736/build_ebooks.py',
]


def main():
    files = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in DOCUMENTS + CODE}
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        book = base / 'fixture_book'
        (book / 'output_dich').mkdir(parents=True)
        (book / 'sources').mkdir()
        target = book / 'output_dich/chuong_0001.txt'
        original = 'CHƯƠNG 1: THỬ\n\nChương 1: Thử\n\nAnh ấy 走 rồi.\n'
        target.write_text(original, encoding='utf-8')
        result = UrbanAuditor(str(book)).audit_and_heal_chapter(1)
        rewritten = target.read_text(encoding='utf-8')
        destructive = {'source_file_existed': (book / 'sources/source_chapter_0001.json').exists(),
                       'original_fixture': original, 'rewritten_fixture': rewritten,
                       'overwrote_txt': rewritten != original,
                       'removed_untranslated_source_character': '走' not in rewritten,
                       'reported_gate_pass': result.is_gate_pass,
                       'patches': result.patches_applied}
        assert not any(destructive[k] for k in ('overwrote_txt', 'removed_untranslated_source_character', 'reported_gate_pass'))
        assert not destructive['source_file_existed']

        guard = StyleAndEntityGuard()
        pronoun_probe = []
        for source, translated in (('我们走吧。', '“Chúng ta đi thôi.”'),
                                   ('她这么说。', '“Cô ta nói vậy.”'),
                                   ('在下告辞。', '“Tại hạ xin cáo từ.”')):
            passed, issues = guard.audit_paragraph('fixture', source, translated)
            pronoun_probe.append({'source': source, 'target': translated,
                                  'passed': passed, 'issues': issues})
        assert pronoun_probe[0]['passed'] and pronoun_probe[1]['passed']
        assert pronoun_probe[2]['passed']

        # Cache probe uses a coherent but partial runtime receipt in a temp job.
        # This demonstrates a guard gap, not that actual cached jobs were bad.
        runtime = {'status': 'SUCCESS', 'partial_output': True, 'exit_code': 0,
                   'actual_model': 'fixture', 'conversation_id': 'fixture-session',
                   'result': {'response': 'fixture incomplete'}}
        contract = {'job_id': 'fixture-job', 'state_hash': 'fixture-state',
                    'owned_segments': [{'id': 'c0001p0001', 'source': '测试。'}]}
        contract['contract_hash'] = digest(contract)
        contract_path = base / 'contract.json'
        contract_path.write_text(json.dumps(contract), encoding='utf-8')
        work = base / contract['job_id']
        (work / 'runtime').mkdir(parents=True)
        candidate = {k: contract[k] for k in ('job_id', 'contract_hash', 'state_hash')}
        candidate.update(segments=[{'id': 'c0001p0001', 'text': 'Thử.'}],
                         provenance={'conversation_id': runtime['conversation_id']})
        receipt = {'status': 'DRAFT_COMPLETE_UNREVIEWED', 'runtime': runtime,
                   'actual_model': 'fixture', 'candidate_hash': digest(candidate)}
        for path, value in ((work / 'candidate.json', candidate),
                            (work / 'runtime/runtime.json', runtime),
                            (work / 'worker_result.json', receipt)):
            path.write_text(json.dumps(value), encoding='utf-8')
        try:
            accepted = verified_cached_result({'contract': str(contract_path), 'model': 'fixture'}, base)
        except ValueError:
            accepted = None
        try:
            require_complete_runtime(runtime, 'fixture')
            common_guard_rejected = False
        except ValueError:
            common_guard_rejected = True
        cache_probe = {'synthetic_partial_runtime_accepted_by_batch_resume': accepted is not None,
                       'same_runtime_rejected_by_common_runtime_guard': common_guard_rejected,
                       'scope': 'Synthetic guard probe; not a claim about real historical cache contents.'}
        assert accepted is None and common_guard_rejected

    local_source = json.loads((ROOT / 'native_oauth/book_49736/sources/source_chapter_0001.json').read_text(encoding='utf-8'))
    schema_probe = {'local_book_source_valid': bool(validate_source(local_source)),
                    'source_fields': list(local_source)}
    try:
        validate_package(local_source)
        schema_probe['accepted_directly_by_semantic_gate'] = True
    except ValueError as exc:
        schema_probe.update(accepted_directly_by_semantic_gate=False, reason=str(exc))

    direct_calls = {}
    for filename in ('native_oauth/chapter_runner.py', 'native_oauth/book_49736/sliding_pool_runner.py'):
        tree = ast.parse((ROOT / filename).read_text(encoding='utf-8-sig'))
        direct_calls[filename] = sorted({ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)})
    assert not any('self.guard.' in call for call in direct_calls['native_oauth/book_49736/sliding_pool_runner.py'])
    evidence = {'date': '2026-10-22', 'scope': 'Workflow/code audit plus isolated offline probes. No production translation or review run.',
                'file_fingerprints': files, 'legacy_auditor_temp_reproduction': destructive,
                'guard_tokenization_temp_reproduction': pronoun_probe,
                'batch_resume_temp_reproduction': cache_probe, 'source_schema_probe': schema_probe,
                'direct_calls_only_not_complete_call_graph': direct_calls}
    output = ROOT / 'audit/workflow_review_postfix_20261022.evidence.json'
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'evidence': str(output), 'document_count': len(DOCUMENTS),
                      'code_file_count': len(CODE), 'isolated_probes': 'PASS'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
