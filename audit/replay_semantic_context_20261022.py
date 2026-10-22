"""Offline replay only: no model calls, translation jobs or novel edits.

Run from the repository root with .venv/Scripts/python.exe -X utf8
audit/replay_semantic_context_20261022.py. Counts measure heuristic coverage,
not semantic translation accuracy. Existing bilingual samples are historical.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.book_49736.batch_pipeline_runner import get_semantic_profile
from native_oauth.chapter_integrity import validate_source
from native_oauth.chapter_runner import split_scenes
from native_oauth.semantic_context import UNKNOWN, context_tail, dialogue_cues


def protected_snapshot():
    files = []
    for book in ('14713', '16014', '49736'):
        for folder in ('sources', 'output_dich', 'dist'):
            base = ROOT / 'native_oauth' / f'book_{book}' / folder
            if base.exists():
                for path in sorted(p for p in base.rglob('*') if p.is_file()):
                    files.append((path.relative_to(ROOT).as_posix(),
                                  hashlib.sha256(path.read_bytes()).hexdigest()))
    encoded = json.dumps(files, ensure_ascii=False, separators=(',', ':')).encode()
    return {'file_count': len(files), 'sha256_of_path_and_file_hashes': hashlib.sha256(encoded).hexdigest()}


def main():
    before = protected_snapshot()
    entities, rules, glossary = get_semantic_profile()
    pre = UnifiedSemanticPreprocessor()
    stats = dict(chapters=0, paragraphs=0, bounded_chunks=0, quotes=0,
                 explicit_local_speakers=0, explicit_local_pairs=0,
                 unresolved_speaker_or_listener=0, same_identity_pairs=0)
    blocked = []
    sources = {}
    previous = []
    for path in sorted((ROOT / 'native_oauth/book_49736/sources').glob('source_chapter_*.json')):
        source = json.loads(path.read_text(encoding='utf-8'))
        segments = validate_source(source)
        sources[source['chapter']] = segments
        paragraphs = [p['source'] for p in segments]
        stats['chapters'] += 1
        stats['paragraphs'] += len(paragraphs)
        try:
            chunks = split_scenes(paragraphs)
        except ValueError as exc:
            blocked.append({'chapter': source['chapter'], 'reason': str(exc)})
            previous = paragraphs
            continue
        assert [p for chunk in chunks for p in chunk] == paragraphs
        assert all(len(chunk) <= 20 and sum(map(len, chunk)) <= 3200 for chunk in chunks)
        offset = 0
        for idx, chunk in enumerate(chunks, 1):
            contract, tagged = pre.build_scene_contract(
                source['chapter'], idx, chunk, entities, rules, glossary=glossary,
                genre='URBAN_SUSPENSE_MYSTERY',
                source_before=context_tail(paragraphs[:offset] if offset else previous))
            assert len(tagged) == len(chunk)
            assert not any('Ø_SHIFT=' in p or 'HOSTILE_SHIFT' in p for p in tagged)
            stats['bounded_chunks'] += 1
            for cue in contract.semantic_context['dialogues']:
                stats['quotes'] += 1
                known = cue['speaker'] != UNKNOWN
                both = known and cue['listener'] != UNKNOWN
                stats['explicit_local_speakers'] += int(known)
                stats['explicit_local_pairs'] += int(both)
                stats['unresolved_speaker_or_listener'] += int(not both)
                stats['same_identity_pairs'] += int(both and cue['speaker_id'] == cue['listener_id'])
            offset += len(chunk)
        assert offset == len(paragraphs)
        previous = paragraphs

    baseline = json.loads((ROOT / 'audit/semantic_address_review_20261021.evidence.json').read_text(encoding='utf-8'))
    samples = []
    for sample in baseline['samples']:
        segments = sources[sample['chapter']]
        matches = [i for i, p in enumerate(segments) if p['source'] == sample['source']]
        assert matches
        pos = matches[0]
        samples.append({'chapter': sample['chapter'], 'source_id': segments[pos]['id'],
                        'source': sample['source'], 'legacy_target': sample['target'],
                        'legacy_assessment': sample['assessment'],
                        'current_advisory_cues': dialogue_cues(
                            sample['source'], entities,
                            context_tail([p['source'] for p in segments[:pos]]))})

    synthetic = []
    cases = [('姜柔甲对秦疏影说：“你先坐。”', '姜柔甲', '秦疏影'),
             ('薑柔甲對秦疏影說：“你先坐。”', '姜柔甲', '秦疏影'),
             ('秦疏影对云千峰说：“我去接孩子。”', '秦疏影', '云千峰'),
             ('秦疏影對雲千峰說：“我去接孩子。”', '秦疏影', '云千峰'),
             ('云千峰对姜柔甲说：“别找死，快回来！”', '云千峰', '姜柔甲'),
             ('“我的哥哥消失了，我想知道他在哪。”', UNKNOWN, UNKNOWN),
             ('“小臻聽話，跟著周阿姨去睡覺，我在加班，晚一些回去，乖。”', UNKNOWN, UNKNOWN)]
    for raw, speaker, listener in cases:
        cue = dialogue_cues(raw, entities)[0]
        assert (cue['speaker'], cue['listener']) == (speaker, listener)
        _, shift, proposed = pre.route_dialogues(raw, entities)
        assert not shift and not proposed
        synthetic.append({'source': raw, 'cue': cue, 'generated_pronoun_rules': proposed})
    real_adversarial = []
    for chapter, paragraph in ((1, 62), (7, 59), (126, 72), (153, 30)):
        segments = sources[chapter]
        raw, preceding = segments[paragraph - 1]['source'], segments[paragraph - 2]['source']
        cues = dialogue_cues(raw, entities, preceding)
        if (chapter, paragraph) in ((1, 62), (7, 59)):
            assert cues[0]['speaker'] == UNKNOWN
        if (chapter, paragraph) == (126, 72):
            assert cues[0]['listener'] == UNKNOWN
        if (chapter, paragraph) == (153, 30):
            assert len(cues) == 1 and cues[0]['end'] == len(raw)
        real_adversarial.append({'source_id': segments[paragraph - 1]['id'],
                                 'preceding_source': preceding, 'source': raw, 'cues': cues})
    after = protected_snapshot()
    assert before == after, 'Offline replay modified protected novel data'
    report = {'date': '2026-10-22',
              'scope': 'Offline heuristic replay, not a translation accuracy benchmark. No post-fix model output.',
              'source_book': '49736', 'coverage_counts': stats, 'budget_blocks': blocked,
              'legacy_samples': samples, 'synthetic_regressions': synthetic,
              'additional_source_adversarial_regressions': real_adversarial,
              'canonical_names': {name: glossary[name][0] for name in ('云千峰', '雲千峰', '罗琳娜', '羅琳娜', '法緹娜', '蘇菲.鍾')},
              'protected_data_unchanged_during_replay': before == after,
              'protected_data_snapshot': after}
    target = ROOT / 'audit/semantic_context_fix_20261022.evidence.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(target), 'coverage_counts': stats,
                      'budget_blocks': len(blocked), 'protected_data_unchanged': before == after}, ensure_ascii=False))


if __name__ == '__main__':
    main()
