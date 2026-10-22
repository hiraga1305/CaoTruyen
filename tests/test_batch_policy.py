import copy
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch
from semantic_gate import digest,write_json
from native_oauth.batch_policy import quantity_candidates,next_route,choose_model
from native_oauth.prepare_batch_route import store_projection
from native_oauth.batch_run import execute,verified_cached_result


class BatchPolicyTests(unittest.TestCase):
    def test_batch_entrypoint_defaults_native_and_does_not_call_api(self):
        import agentic_batch_translator
        with patch.object(sys,'argv',['agentic_batch_translator.py','--manifest','frozen.json','--resume']),\
             patch('native_oauth.batch_run.main') as native,patch('pipeline_api.main') as api:
            agentic_batch_translator.main()
        native.assert_called_once_with(['--manifest','frozen.json','--resume'])
        api.assert_not_called()

    def test_api_compatibility_is_explicit_and_argv_restored_after_failure(self):
        import agentic_batch_translator
        argv=['agentic_batch_translator.py','--legacy-api','--chap','1']
        def fail():
            self.assertNotIn('--legacy-api',sys.argv)
            raise RuntimeError('provider blocked')
        with patch.object(sys,'argv',argv),patch('pipeline_api.main',side_effect=fail),\
             patch('native_oauth.batch_run.main') as native:
            with self.assertRaises(RuntimeError):agentic_batch_translator.main()
            self.assertEqual(sys.argv,argv)
        native.assert_not_called()

    def test_quantities_keep_original_units_and_comparison_uncertainty(self):
        source='每件不少于900克，不是多于900克；不超过三百件。'
        rows=quantity_candidates(source)
        self.assertTrue(rows)
        for row in rows:
            self.assertIn(row['source_quote'],source)
            self.assertNotIn('normalized_target',row)
            self.assertNotIn('relation_candidate',row)
        self.assertIn('不超过',rows[-1]['comparison_markers'])

    def test_failure_regenerates_whole_scene_and_quarantines_at_limit(self):
        decision=next_route([{'kind':'referent'}])
        self.assertEqual(decision['action'],'EXPAND_SOURCE_RETRIEVAL_AND_MERGE_DIALOGUE_SCENES')
        self.assertIn('whole',decision['regenerate_scope'])
        self.assertFalse(decision['publish'])
        self.assertEqual(next_route([{'kind':'referent'}],2)['action'],'QUARANTINE')
        self.assertFalse(next_route([])['publish'])

    def test_auto_routing_is_conservative_not_self_confidence(self):
        base={'owned_segments':[{'source':'他走进花园。'}],'neighbor_segments':[],
              'context_capsule':{'omitted_optional_entries':0},'parser_hints':[]}
        self.assertEqual(choose_model(base)['model'],'gemini-3.8-flash-low')
        risk=copy.deepcopy(base);risk['owned_segments'][0]['source']='她找上线申请小贷。'
        self.assertEqual(choose_model(risk)['model'],'gemini-3.8-flash-medium')
        risk=copy.deepcopy(base);risk['parser_hints']=[{'idiom_candidates':['不以为然道']}]
        self.assertEqual(choose_model(risk)['model'],'gemini-3.8-flash-medium')
        self.assertFalse(choose_model(risk)['publish'])

    def test_source_projection_does_not_store_previous_target_context(self):
        source={'chapter':1,'title':'test','source_ref':'original','glossary':{},
                'context':{'facts':[{'statement':'unapproved Vietnamese'}]},
                'segments':[{'id':'c0001p0001','source':'原文','original_fixture_id':'s1'}]}
        source['package_hash']=digest(source)
        projected=store_projection(source)
        self.assertNotIn('context',projected)
        self.assertEqual(projected['segments'],[{'id':'c0001p0001','source':'原文'}])
        self.assertEqual(projected['upstream_source_package_hash'],source['package_hash'])

    def _cache(self,folder):
        contract={'job_id':'scene','state_hash':'frozen-state','owned_segments':[{'id':'c0001p0001','source':'原文'}]}
        contract['contract_hash']=digest(contract);write_json(folder/'contract.json',contract)
        work=folder/'workers/scene';work.mkdir(parents=True)
        runtime={'status':'SUCCESS','conversation_id':'original-native-session','usage':{'total_tokens':12},
                 'actual_model':'gemini-3.8-flash-low','exit_code':0,'result':{'response':'candidate.json'}}
        write_json(work/'runtime/runtime.json',runtime)
        candidate={'job_id':'scene','state_hash':contract['state_hash'],'contract_hash':contract['contract_hash'],
                   'segments':[{'id':'c0001p0001','text':'Nguyên văn.'}],
                   'provenance':{'conversation_id':'original-native-session'}}
        write_json(work/'candidate.json',candidate)
        write_json(work/'worker_result.json',{'job_id':'scene','status':'DRAFT_COMPLETE_UNREVIEWED',
                   'actual_model':'gemini-3.8-flash-low','candidate_hash':digest(candidate),'runtime':runtime})
        return {'contract':str(folder/'contract.json'),'model':'gemini-3.8-flash-low'},candidate

    def test_resume_retains_original_native_provenance_without_new_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);spec,_=self._cache(folder)
            with patch('native_oauth.batch_run.run_manifest') as runner:
                report=execute({'jobs':[spec],'workspace':str(folder/'workers'),
                                'result_path':str(folder/'result.json')},resume=True)
            runner.assert_not_called()
            self.assertEqual(report['status'],'DRAFTS_COMPLETE_UNREVIEWED')
            self.assertEqual(report['new_reported_tokens'],0)
            self.assertFalse(report['publish'])

    def test_resume_rejects_changed_target_or_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);spec,candidate=self._cache(folder)
            bad={**spec,'model':'gemini-3.8-flash-medium'}
            with self.assertRaises(ValueError):verified_cached_result(bad,folder/'workers')
            candidate['segments'][0]['text']='Changed'
            write_json(folder/'workers/scene/candidate.json',candidate)
            with self.assertRaises(ValueError):verified_cached_result(spec,folder/'workers')


if __name__=='__main__':unittest.main()
