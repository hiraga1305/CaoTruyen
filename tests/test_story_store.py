"""Storage/provenance tests, never translation quality scores."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from semantic_gate import digest
from native_oauth.story_store import StoryStore


def package(chapter, texts, glossary=None):
    p = {'chapter': chapter, 'version': 'raw-source-benchmark-1',
         'segments': [{'id': f'c{chapter:04d}p{i:04d}', 'source': text} for i, text in enumerate(texts, 1)],
         'glossary': glossary or {}}
    p['package_hash'] = digest(p)
    return p


class StoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'story.sqlite3'
        self.store = StoryStore(self.path, 'book-1')
        self.p1 = package(1, ['张羽给姐姐转账五百。', '她没有答应。', '张羽后来回家。'], {'张羽': 'Trương Vũ'})

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_persistent_idempotent_and_optimistic_transactions(self):
        one = self.store.index_package(self.p1, expected_revision=0)
        self.assertEqual(one['revision'], 1)
        again = self.store.index_package(self.p1, expected_revision=1)
        self.assertFalse(again['changed'])
        self.assertEqual(again['revision_hash'], one['revision_hash'])
        other = StoryStore(self.path, 'book-1')
        try:
            other.index_package(package(2, ['张羽来了。']), expected_revision=1)
            with self.assertRaisesRegex(ValueError, 'Stale'):
                self.store.index_package(package(3, ['他走了。']), expected_revision=1)
        finally:
            other.close()
        self.assertEqual(self.store.revision, 2)
        self.assertEqual(self.store.integrity_check()['paragraphs'], 4)

    def test_future_quotes_and_newer_revision_are_excluded(self):
        self.store.index_package(self.p1, expected_revision=0)
        self.store.index_package(package(2, ['张羽其实是另一人。']), expected_revision=1)
        cap = self.store.retrieve_capsule(['c0001p0002'], ['张羽'], revision=1, pronoun_recent=0)
        self.assertEqual([e['source_id'] for e in cap['evidence']], ['c0001p0001'])
        self.assertNotIn('另一人', json.dumps(cap, ensure_ascii=False))
        with self.assertRaisesRegex(ValueError, 'absent'):
            self.store.retrieve_capsule(['c0002p0001'], ['张羽'], revision=1)
        with self.assertRaisesRegex(ValueError, 'future'):
            self.store.retrieve_capsule(['c0001p0002'], before_id='c0001p0003')

    def test_changed_source_and_glossary_conflicts_roll_back(self):
        self.store.index_package(self.p1, expected_revision=0)
        changed = package(1, ['张羽没有转账。'], {'张羽': 'Trương Vũ'})
        with self.assertRaisesRegex(ValueError, 'source changed'):
            self.store.index_package(changed, expected_revision=1)
        with self.assertRaisesRegex(ValueError, 'glossary'):
            self.store.index_package(package(2, ['张羽来了。'], {'张羽': 'Khác'}), expected_revision=1)
        self.assertEqual(self.store.revision, 1)
        self.assertEqual(self.store.integrity_check()['paragraphs'], 3)

    def test_quote_hash_and_original_source_are_verified_at_retrieval(self):
        self.store.index_package(self.p1, expected_revision=0)
        cap = self.store.retrieve_capsule(['c0001p0002'], ['张羽'], pronoun_recent=0)
        evidence = cap['evidence'][0]
        self.assertEqual(evidence['quote_hash'], digest(evidence['source_quote']))
        self.store.db.execute("UPDATE mentions SET quote='张羽转账五万。' WHERE key='张羽'")
        with self.assertRaisesRegex(ValueError, 'quote hash'):
            self.store.retrieve_capsule(['c0001p0002'], ['张羽'], pronoun_recent=0)
        with self.assertRaisesRegex(ValueError, 'mention'):
            self.store.integrity_check()

    def test_quote_entries_cannot_admit_drafts_or_invented_evidence(self):
        fake = [{'ledger_id': 'x', 'keys': ['张羽'], 'references': [{'source_id': 'c0001p0001', 'source_quote': '张羽杀了姐姐'}]}]
        with self.assertRaisesRegex(ValueError, 'original source'):
            self.store.index_package(self.p1, fake, expected_revision=0)
        draft = copy.deepcopy(self.p1)
        draft['segments'][0]['text'] = 'Bản dịch'
        draft['package_hash'] = digest({k: v for k, v in draft.items() if k != 'package_hash'})
        with self.assertRaisesRegex(ValueError, 'target draft'):
            self.store.index_package(draft, expected_revision=0)
        self.assertEqual(self.store.revision, 0)

    def test_budget_recent_retrieval_and_book_identity(self):
        self.store.index_package(self.p1, expected_revision=0)
        cap = self.store.retrieve_capsule(['c0001p0003'], [], pronoun_recent=1, max_entries=1, max_chars=2000)
        self.assertEqual(cap['evidence'][0]['source_id'], 'c0001p0002')
        self.assertIn('not_coreference', cap['evidence'][0]['retrieved_by'])
        self.assertLessEqual(len(json.dumps(cap, ensure_ascii=False, sort_keys=True, separators=(',', ':'))), 2000)
        with self.assertRaisesRegex(ValueError, 'identity'):
            StoryStore(self.path, 'different-book')
        with self.assertRaisesRegex(ValueError, 'cap'):
            self.store.index_package(package(2, ['太长。']), expected_revision=1, max_source_chars=1)
        self.assertEqual(self.store.revision, 1)

    def test_new_mention_index_does_not_mutate_old_snapshot(self):
        self.store.index_package(self.p1, expected_revision=0)
        original = self.store.snapshot(1)
        entry = {'ledger_id': 'amount', 'keys': ['五百'], 'references': [
            {'source_id': 'c0001p0001', 'source_quote': '转账五百'}]}
        self.store.index_package(self.p1, [entry], expected_revision=1)
        old = self.store.retrieve_capsule(['c0001p0002'], ['五百'], revision=1, pronoun_recent=0)
        new = self.store.retrieve_capsule(['c0001p0002'], ['五百'], revision=2, pronoun_recent=0)
        self.assertEqual(old['evidence'], [])
        self.assertEqual(new['evidence'][0]['source_quote'], '转账五百')
        self.assertEqual(original, self.store.snapshot(1))

    def test_capsule_character_limit_includes_its_hash(self):
        self.store.index_package(self.p1, expected_revision=0)
        cap = self.store.retrieve_capsule(['c0001p0003'], ['张羽'], max_entries=1, max_chars=1000)
        serialized = json.dumps(cap, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        self.assertLessEqual(len(serialized), 1000)
        self.assertGreater(cap['omitted_evidence_candidates'], 0)
        self.assertEqual(cap['capsule_hash'], digest({k: v for k, v in cap.items() if k != 'capsule_hash'}))

    def test_actual_mentions_query_uses_the_index_and_source_corruption_fails(self):
        self.store.index_package(self.p1, expected_revision=0)
        plan = self.store.db.execute('EXPLAIN QUERY PLAN SELECT * FROM mentions '
            'WHERE key=? AND (chapter,ordinal)<(?,?) AND introduced_revision<=? '
            'ORDER BY chapter DESC,ordinal DESC,quote_hash LIMIT ?', ('张羽', 2, 1, 1, 4))
        self.assertIn('mention_lookup', ' '.join(str(tuple(row)) for row in plan))
        self.store.db.execute("UPDATE paragraphs SET source='张羽转账五万。' WHERE source_id='c0001p0001'")
        with self.assertRaisesRegex(ValueError, 'source hash'):
            self.store.retrieve_capsule(['c0001p0002'], ['张羽'], pronoun_recent=0)

    def test_distant_return_keeps_original_family_anchor_and_latest_event(self):
        source = package(1, ['林青是林河的妹妹。', '林青到了车站。', '林青读了一封信。',
            '林青没有答应。', '林青继续等待。', '林青后来回家。', '她没有再提这件事。'], {'林青': 'Lâm Thanh'})
        self.store.index_package(source, expected_revision=0)
        latest_only = self.store.retrieve_capsule(['c0001p0007'], ['林青'],
            pronoun_recent=0, retain_first_anchor=False, max_entries=8, max_chars=10000)
        improved = self.store.retrieve_capsule(['c0001p0007'], ['林青'],
            pronoun_recent=0, max_entries=8, max_chars=10000)
        self.assertNotIn('c0001p0001', [e['source_id'] for e in latest_only['evidence']])
        ids = [e['source_id'] for e in improved['evidence']]
        self.assertIn('c0001p0001', ids)
        self.assertIn('c0001p0006', ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(improved['evidence'][0]['source_quote'], '林青是林河的妹妹。')
        self.assertTrue(improved['retain_first_source_anchor'])
        self.assertIn('not coreference', improved['retrieval'])

    def test_first_anchor_never_uses_a_future_confirmation_or_new_revision(self):
        self.store.index_package(package(1, ['甲说他不知道。', '他离开。'], {'甲': 'Giáp'}), expected_revision=0)
        self.store.index_package(package(2, ['甲就是乙。'], {'甲': 'Giáp'}), expected_revision=1)
        current = self.store.retrieve_capsule(['c0001p0002'], ['甲'], revision=2, pronoun_recent=0)
        self.assertEqual([e['source_quote'] for e in current['evidence']], ['甲说他不知道。'])
        self.assertNotIn('甲就是乙', json.dumps(current, ensure_ascii=False))
        self.assertLessEqual(len(json.dumps(current, ensure_ascii=False)), 12000)

    def test_original_package_can_be_resumed_from_past_snapshot_without_approval(self):
        self.store.index_package(self.p1, expected_revision=0)
        self.store.index_package(package(2, ['她又回来了。']), expected_revision=1)
        past = self.store.get_source_package(1, revision=1)
        self.assertEqual(past, self.p1)
        past['segments'][0]['source'] = 'modified caller copy'
        self.assertEqual(self.store.get_source_package(1, revision=1), self.p1)
        self.assertNotIn('approved_translation', past)
        self.assertNotIn('status', past)
        with self.assertRaisesRegex(ValueError, 'absent'):
            self.store.get_source_package(2, revision=1)

    def test_original_package_read_rejects_tampered_package_and_resealed_text(self):
        self.store.index_package(self.p1, expected_revision=0)
        edited = package(1, ['张羽转账五万。', '她没有答应。', '张羽后来回家。'], {'张羽': 'Trương Vũ'})
        self.store.db.execute('UPDATE chapters SET package_json=?,package_hash=? WHERE chapter=1',
            (json.dumps(edited, ensure_ascii=False), edited['package_hash']))
        with self.assertRaisesRegex(ValueError, 'immutable index revision'):
            self.store.get_source_package(1)


if __name__ == '__main__':
    unittest.main()
