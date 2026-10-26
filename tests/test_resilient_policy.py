"""Offline policy regressions: no model, network or publication of real books."""
import copy
import unicodedata
import unittest
from semantic_gate import digest,CHECKS,LITERARY_CHECKS
from native_oauth.resilient_policy import POLICY,REVIEW_POLICY,review_hints,content_findings
from native_oauth.resilient_gate import validate_translation,validate_compact_review,freeze
from native_oauth.recovery_native import ProtocolFailure,ContentFailure,classify


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.packet=freeze({'validation_policy':POLICY,'segments':[{'id':'c0001p0001','source':'林御摇头。'}],
            'glossary':{'林御':'Lâm Ngự'}})
        self.value={'package_hash':self.packet['package_hash'],'segments':[{'id':'c0001p0001','text':'Hắn lắc đầu.'}]}

    def review(self,obligations=True):
        packet=freeze({'review_policy':REVIEW_POLICY,'scope_slots':[1],
            'catalog':[{'slot':1,'source':'林御摇头。','target':'Hắn lắc đầu.',
                        **({'review_obligations':[{'kind':'entity_reference'}]} if obligations else {})}]})
        value={'package_hash':packet['package_hash'],'verdict':'PASS','checks':dict.fromkeys(CHECKS,True),
            'literary_checks':dict.fromkeys(LITERARY_CHECKS,True),'rows':[[1,'PASS']],'issues':[],
            'semantic_obligations_checked':[1] if obligations else []}
        return packet,value

    def test_pronoun_is_a_review_duty_not_a_missing_string_failure(self):
        validate_translation(self.packet,self.value)
        hints=review_hints(self.packet,self.value)
        self.assertEqual(hints['c0001p0001'][0]['kind'],'entity_reference')
        self.assertEqual(hints['c0001p0001'][0]['canonical_name'],'Lâm Ngự')

    def test_nfc_nfd_case_and_whitespace_do_not_change_native_text_or_create_false_name_hint(self):
        text=unicodedata.normalize('NFD','LÂM\u00a0 NGỰ lắc đầu.')
        self.value['segments'][0]['text']=text
        validate_translation(self.packet,self.value)
        self.assertEqual(review_hints(self.packet,self.value),{})
        self.assertEqual(self.value['segments'][0]['text'],text)

    def test_accents_and_word_boundaries_are_not_discarded(self):
        for name,text in [('Lâm Ngự','Lâm Ngũ lắc đầu.'),('An','Anh lắc đầu.')]:
            self.packet['glossary']={'林御':name};self.value['segments'][0]['text']=text
            self.assertIn('c0001p0001',review_hints(self.packet,self.value))

    def test_legacy_gate_is_not_retroactively_relaxed(self):
        packet=freeze({k:v for k,v in self.packet.items() if k not in ('validation_policy','package_hash')})
        value={**self.value,'package_hash':packet['package_hash']}
        with self.assertRaises(ContentFailure):validate_translation(packet,value)

    def test_missing_duplicate_reordered_ids_and_wrong_hash_stay_hard_errors(self):
        for rows in ([],[self.value['segments'][0]]*2,[{'id':'c0001p0002','text':'Hắn lắc đầu.'}]):
            with self.assertRaises(ProtocolFailure):validate_translation(self.packet,{**self.value,'segments':rows})
        with self.assertRaises(ProtocolFailure):validate_translation(self.packet,{**self.value,'package_hash':'other'})

    def test_empty_replacement_surrogate_and_unexplained_hanzi_remain_errors(self):
        for text in ('','\u200b\ufeff','林御 lắc đầu.','\ufffd','\ud800','\U00020000'):
            self.value['segments'][0]['text']=text
            with self.assertRaises(ContentFailure):validate_translation(self.packet,self.value)

    def test_yijing_symbol_is_not_misclassified_as_a_chinese_word(self):
        self.value['segments'][0]['text']='Biểu tượng ䷀ xuất hiện.'
        validate_translation(self.packet,self.value)

    def test_script_quote_needs_native_claim_exact_source_target_and_review_duty(self):
        self.packet['segments'][0]['source']='他说：这个“人”字很重要。'
        self.value['segments'][0]['text']='Hắn nói chữ “人” này rất quan trọng.'
        with self.assertRaises(ContentFailure):validate_translation(self.packet,self.value)
        self.value['source_script_quotes']=[{'id':'c0001p0001','quote':'人','reason':'The plot explicitly discusses this written character'}]
        validate_translation(self.packet,self.value)
        self.assertEqual(review_hints(self.packet,self.value)['c0001p0001'][0]['kind'],'source_script_quote')
        self.value['segments'][0]['text']+=' 未翻译'
        with self.assertRaises(ContentFailure):validate_translation(self.packet,self.value)

    def test_script_claim_cannot_reference_another_id_or_invent_a_source_quote(self):
        for claim in ({'id':'c0002p0001','quote':'林御','reason':'quoted'},
                      {'id':'c0001p0001','quote':'张羽','reason':'quoted'}):
            self.value['source_script_quotes']=[claim]
            with self.assertRaises(ProtocolFailure):validate_translation(self.packet,self.value)

    def test_both_reviewers_must_explicitly_cover_flagged_slots(self):
        packet,value=self.review();validate_compact_review(packet,value)
        for checked in (None,[],[True],[1,1],[2]):
            wrong={**value,'semantic_obligations_checked':checked}
            with self.assertRaises(ProtocolFailure):validate_compact_review(packet,wrong)

    def test_optional_style_suggestion_does_not_create_fake_semantic_failure(self):
        packet,value=self.review();value['suggestions']=[{'slot':1,'source_ref':0,'target_ref':0,'kind':'style','reason':'A shorter phrasing is also possible'}]
        validate_compact_review(packet,value)
        value['suggestions'][0]['kind']='entities'
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet,value)

    def test_valid_entity_fail_is_preserved(self):
        packet,value=self.review();value.update(verdict='FAIL',rows=[[1,'FAIL']],
            issues=[{'slot':1,'source_ref':0,'target_ref':0,'kind':'entities','reason':'Wrong character'}])
        validate_compact_review(packet,value)
        value['verdict']='PASS'
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet,value)

    def test_needs_context_must_include_an_actionable_exact_source_query(self):
        packet,value=self.review();value.update(verdict='FAIL',rows=[[1,'FAIL']],
            issues=[{'slot':1,'source_ref':0,'target_ref':0,'kind':'needs_context','reason':'Need prior identity context'}])
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet,value)

    def test_pronoun_context_query_may_use_an_earlier_name_but_not_a_future_name(self):
        packet,value=self.review();packet['catalog']=[{'slot':1,'chapter':2,'source':'他走了。','target':'Hắn đi rồi.'},
            {'slot':2,'chapter':3,'source':'张羽来了。','target':'Trương Vũ đến.'}]
        packet['source_context']=[{'chapter':1,'for_chapter':2,'source':'林御来到这里。'}]
        value.update(verdict='FAIL',rows=[[1,'FAIL']],semantic_obligations_checked=[],
            issues=[{'slot':1,'source_ref':0,'target_ref':0,'kind':'needs_context','reason':'Need referent','context_query':'林御'}])
        validate_compact_review(packet,value)
        value['issues'][0]['context_query']='张羽'
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet,value)
        value['issues'][0]['context_query']='林御';validate_compact_review(packet,value)
        value['issues'][0]['context_query']='不存在'
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet,value)

    def test_malformed_objects_are_format_errors_not_unclassified_permanent_blocks(self):
        with self.assertRaises(ProtocolFailure):validate_translation(self.packet,[])
        packet,value=self.review()
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet,[])
        value['issues']=[None];value.update(verdict='FAIL',rows=[[1,'FAIL']])
        with self.assertRaises(ProtocolFailure):validate_compact_review(packet,value)

    def test_chapter_ids_and_typed_content_are_not_http_quota_or_permission_errors(self):
        for text in ('c0429p0001 missing','c0403p0001 missing','c0503p0001 missing'):
            self.assertEqual(classify(ValueError(text)),'UNCLASSIFIED')
        self.assertEqual(classify(ProtocolFailure('403 permission denied in a quoted story')),'FORMAT')
        self.assertEqual(classify(ContentFailure('invoked a tool is source dialogue')),'CONTENT')
        for text,expected in [('429 quota exhausted','QUOTA'),('HTTP Error 403: Forbidden','ACCESS'),('status_code=503','NETWORK')]:
            self.assertEqual(classify(ValueError(text)),expected)


if __name__=='__main__':unittest.main()
