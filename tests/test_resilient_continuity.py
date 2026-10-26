"""Generic editorial rules: no novel-specific names, models or network calls."""
import copy
import unittest

from native_oauth.resilient_continuity import (VERSION, CHECKS, declared_entries,
    selected_entries, row_obligations, scoped_canon, validate_review)
from native_oauth.resilient_gate import validate_compact_review
from native_oauth.recovery_native import ProtocolFailure
from semantic_gate import CHECKS as MEANING, LITERARY_CHECKS


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.entry = {'key': 'person-01', 'kind': 'name', 'zh': '江月', 'vi': 'Giang Nguyệt',
            'scope': 'The named character only; quoted text, deliberate aliases and clear pronouns need contextual review.',
            'source_id': 'c0002p0001', 'source_quote': '江月走了。'}
        self.canon = {'continuity_entries': [self.entry]}
        self.source = {'book_id': 'fiction-fixture', 'chapter': 2, 'title': '測試',
            'segments': [{'id': 'c0002p0001', 'source': '江月走了。'}]}

    def review(self, target='Giang Nguyệt đi rồi.'):
        packet = {'package_hash': 'fixture', 'review_policy': 'resilient-review-2',
            'continuity_policy': VERSION, 'scope_slots': [1], 'catalog': [
                {'slot': 1, 'chapter': 2, 'id': 'c0002p0001', 'source': '江月走了。', 'target': target,
                 'review_obligations': row_obligations({'continuity_contract': {'entries': [self.entry]}}, '江月走了。')}]}
        value = {'package_hash': 'fixture', 'verdict': 'PASS', 'checks': dict.fromkeys(MEANING, True),
            'literary_checks': dict.fromkeys(LITERARY_CHECKS, True), 'rows': [[1, 'PASS']], 'issues': [],
            'semantic_obligations_checked': [1], 'continuity_checks': dict.fromkeys(CHECKS, True),
            'continuity_decisions': [{'slot': 1, 'key': 'person-01', 'status': 'consistent',
                                     'reason': 'This is the declared spelling for this source entity.'}]}
        return packet, value

    def test_rules_are_selected_by_source_and_chapter_not_book_name_or_genre(self):
        for book_id in ('space-fixture', 'historical-fixture', 'school-fixture'):
            self.source['book_id'] = book_id
            self.assertEqual(selected_entries(self.canon, self.source), [self.entry])
        self.source['chapter'] = 1
        self.assertEqual(selected_entries(self.canon, self.source), [])
        self.source['chapter'] = 2; self.source['segments'][0]['source'] = '陌生人走了。'
        self.assertEqual(selected_entries(self.canon, self.source), [])

    def test_future_and_expired_conventions_are_not_native_prompt_context(self):
        self.entry['valid_to_chapter'] = 3
        self.assertEqual(scoped_canon(self.canon, 1)['continuity_entries'], [])
        self.assertEqual(scoped_canon(self.canon, 4)['continuity_entries'], [])
        self.assertEqual(scoped_canon(self.canon, 2)['continuity_entries'], [self.entry])
        canon = {'source_bound_terms': [{'source_id': 'c1000p0001', 'zh': '孤'}]}
        self.assertEqual(scoped_canon(canon, 20)['source_bound_terms'], [])

    def test_duplicate_missing_scope_invalid_id_and_future_start_are_rejected(self):
        changes = ({'source_id': True}, {'source_id': 'c0000p0001'}, {'source_id': 'invented'},
                   {'scope': ''}, {'kind': []}, {'valid_from_chapter': 1}, {'valid_from_chapter': True},
                   {'valid_to_chapter': 1}, {'source_quote': '另一個人'}, {'unexpected': 'field'})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                declared_entries({'continuity_entries': [{**self.entry, **change}]})
        with self.assertRaises(ValueError):declared_entries({'continuity_entries': [self.entry, self.entry]})

    def test_alias_identity_is_explicit_and_requires_source_evidence(self):
        self.entry['aliases_zh'] = ['夜客']
        with self.assertRaises(ValueError):declared_entries(self.canon)
        self.entry['source_quote'] = '江月的別名是夜客。'
        declared_entries(self.canon)
        self.source['segments'][0]['source'] = '夜客回来了。'
        self.assertEqual(selected_entries(self.canon, self.source), [self.entry])

    def test_address_rule_needs_both_speaker_and_recipient_evidence(self):
        self.entry.update(kind='address', source_quote='江月向陈青说：“你先走。”')
        with self.assertRaises(ValueError):declared_entries(self.canon)
        self.entry.update(speaker_zh='江月', addressee_zh='陈青')
        declared_entries(self.canon)
        self.entry['addressee_zh'] = '不存在'
        with self.assertRaises(ValueError):declared_entries(self.canon)

    def test_shared_chinese_surface_does_not_merge_two_scoped_entities(self):
        other = {**self.entry, 'key': 'person-02', 'vi': 'Giang Duyệt', 'scope': 'A different person in quoted historical records.'}
        self.assertEqual(len(declared_entries({'continuity_entries': [self.entry, other]})), 2)

    def test_consistent_spelling_requires_both_native_checks_and_owned_decision(self):
        packet, value = self.review(); validate_compact_review(packet, value)
        for field, wrong in (('continuity_checks', {}), ('continuity_checks', dict.fromkeys(CHECKS, False)),
                             ('continuity_decisions', []), ('continuity_decisions', [None])):
            with self.subTest(field=field, wrong=wrong), self.assertRaises(ProtocolFailure):
                validate_compact_review(packet, {**value, field: wrong})

    def test_pronoun_variation_is_reviewable_without_a_missing_string_hard_failure(self):
        packet, value = self.review('Người ấy đi rồi.')
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet, value)
        value['continuity_decisions'][0].update(status='valid_variation',
            reason='The adjacent source attributes this action to the same person; the neutral pronoun does not invent gender.')
        validate_compact_review(packet, value)
        self.assertEqual(packet['catalog'][0]['target'], 'Người ấy đi rồi.')

    def test_wrong_name_cannot_be_recorded_consistent_or_downgraded_to_style(self):
        packet, value = self.review('Giang Duyệt đi rồi.')
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet, value)
        value['continuity_decisions'][0]['status'] = 'violation'
        value['suggestions'] = [{'slot': 1, 'source_ref': 0, 'target_ref': 0, 'kind': 'style', 'reason': 'Change the name'}]
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet, value)
        value.update(verdict='FAIL', rows=[[1, 'FAIL']], issues=[
            {'slot': 1, 'source_ref': 0, 'target_ref': 0, 'kind': 'continuity', 'reason': 'Different spelling of the same established name'}])
        validate_compact_review(packet, value)

    def test_missing_identity_context_needs_actionable_source_query(self):
        packet, value = self.review('Người ấy đi rồi.')
        value['continuity_decisions'][0]['status'] = 'needs_context'
        value.update(verdict='FAIL', rows=[[1, 'FAIL']], issues=[
            {'slot': 1, 'source_ref': 0, 'target_ref': 0, 'kind': 'needs_context',
             'reason': 'Cannot distinguish the two identities', 'context_query': '江月'}])
        validate_compact_review(packet, value)
        value['issues'][0]['context_query'] = '未来人物'
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet, value)

    def test_decisions_cannot_skip_duplicate_or_reference_unassigned_slots(self):
        packet, value = self.review()
        for change in ({'slot': 2}, {'slot': True}, {'key': 'other'}, {'reason': ''}, {'status': 'PASS'}):
            wrong = copy.deepcopy(value); wrong['continuity_decisions'][0].update(change)
            with self.subTest(change=change), self.assertRaises(ProtocolFailure):validate_review(packet, wrong)
        value['continuity_decisions'] *= 2
        with self.assertRaises(ProtocolFailure):validate_review(packet, value)

    def test_empty_canon_still_requires_generic_inspections_without_extra_model_calls(self):
        packet, value = self.review();packet['catalog'][0].pop('review_obligations')
        value.update(continuity_decisions=[], semantic_obligations_checked=[])
        validate_compact_review(packet, value)
        value.pop('continuity_checks')
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet, value)

    def test_old_approved_schema_does_not_acquire_new_requirements(self):
        packet, value = self.review()
        packet.pop('continuity_policy');value.pop('continuity_checks');value.pop('continuity_decisions')
        validate_compact_review(packet, value)

    def test_accepted_vietnamese_form_is_not_an_automatic_entity_merge(self):
        packet, value = self.review('Cô Giang đi rồi.')
        packet['catalog'][0]['review_obligations'][0]['accepted_forms'] = ['Cô Giang']
        validate_compact_review(packet, value)


if __name__ == '__main__':unittest.main()
