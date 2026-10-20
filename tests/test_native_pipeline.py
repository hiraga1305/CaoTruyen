import copy
import json
import tempfile
import unittest
from pathlib import Path
from semantic_gate import build_package,digest,write_json
from native_oauth.pipeline_native import prepare_inputs,validate_literary_review,LITERARY_CHECKS
from native_oauth.json_format_repair import repair_text_fields
from tests.test_semantic_gate import fixture


class NativePipelineTests(unittest.TestCase):
    def test_analysis_wrong_source_and_coverage_rejected(self):
        source = build_package(1,'test',['张羽没有杀死他。'],{'张羽':'Trương Vũ'},'fixture')
        parsed = {'source_package_hash':source['package_hash'],'provenance':{'model':'fixture'},
                  'limits':'fixture','segments':[{'id':source['segments'][0]['id'],
                  'source_hash':digest(source['segments'][0]['source']),'srl':[],'dep':[],'ner':[]}]}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_json(root/'source.json',source)
            bad=copy.deepcopy(parsed)
            bad['segments'][0]['source_hash']='bad'
            write_json(root/'parse.json',bad)
            with self.assertRaises(ValueError):
                prepare_inputs(root/'source.json',root/'parse.json','hien_dai',root/'workspace')
            bad['segments']=[]
            write_json(root/'parse.json',bad)
            with self.assertRaises(ValueError):
                prepare_inputs(root/'source.json',root/'parse.json','hien_dai',root/'workspace')

    def test_literary_inspection_is_required(self):
        with self.assertRaises(ValueError):
            validate_literary_review({})
        review={'literary_checks':dict.fromkeys(LITERARY_CHECKS,True)}
        validate_literary_review(review)
        review['literary_checks']['genre_voice']=False
        with self.assertRaises(ValueError):
            validate_literary_review(review)

    def test_genres_are_distinct_and_not_certified(self):
        profiles=json.loads((Path(__file__).resolve().parents[1]/'native_oauth/genre_profiles.json').read_text(encoding='utf-8'))
        self.assertNotEqual(profiles['profiles']['tien_hiep']['pronouns'],profiles['profiles']['hien_dai']['pronouns'])
        self.assertIn('not BNS approval',profiles['certification'])

    def test_quote_repair_preserves_words_and_dialogue_quotes(self):
        bad='{\n"segments": [\n{\n"id": "c0001p0001",\n"text": ""Đến nơi chưa?""\n}\n]\n}'
        payload,changed=repair_text_fields(bad)
        self.assertTrue(changed)
        self.assertEqual(payload['segments'][0]['text'],'"Đến nơi chưa?"')

    def test_partial_content_is_not_salvaged(self):
        with self.assertRaises(json.JSONDecodeError):
            repair_text_fields('{"segments":[')

    def test_codex_policy_requires_isolated_sessions_and_preserves_default(self):
        from semantic_gate import evaluate,candidate_hash
        p,c,r=fixture()
        c['model']='native/fixture'
        for i,review in enumerate(r):
            review.update({'model':'codex/gpt-inherited','identity_basis':'codex_subagent',
                           'agent_session':'session'+str(i),'candidate_hash':candidate_hash(c)})
        r[1]['literary_checks']=dict.fromkeys(LITERARY_CHECKS,True)
        policy={'mode':'codex_gpt_sessions','required_sessions':['session0','session1']}
        self.assertEqual(evaluate(p,c,r,review_policy=policy)['status'],'PASS')
        self.assertEqual(evaluate(p,c,r)['status'],'BLOCKED')
        r[1]['agent_session']='session0'
        self.assertEqual(evaluate(p,c,r,review_policy=policy)['status'],'BLOCKED')

    def test_direct_codex_publication_cannot_bypass_literary_review(self):
        from semantic_gate import evaluate,candidate_hash,publish
        p,c,r=fixture()
        c['model']='native/fixture'
        for i,review in enumerate(r):
            review.update({'model':'codex/gpt-inherited','identity_basis':'codex_subagent',
                           'agent_session':'session'+str(i),'candidate_hash':candidate_hash(c)})
        policy={'mode':'codex_gpt_sessions','required_sessions':['session0','session1']}
        for checks in ({},dict.fromkeys(LITERARY_CHECKS,False)):
            r[1]['literary_checks']=checks
            with tempfile.TemporaryDirectory() as folder:
                with self.assertRaises(ValueError):
                    publish(p,c,r,folder,review_policy=policy)
                self.assertFalse(list(Path(folder).glob('*.txt')))


if __name__=='__main__':
    unittest.main()
