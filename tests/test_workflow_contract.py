"""The folder's declared workflow must match its real entry point and defaults."""
import inspect
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from native_oauth.resilient_translation import Runner
from native_oauth.resilient_policy import POLICY,REVIEW_POLICY
from native_oauth.resilient_continuity import VERSION as CONTINUITY
from native_oauth.revise_book import run_campaign


class WorkflowContractTests(unittest.TestCase):
    def test_release_contract_matches_runner_defaults(self):
        root=Path(__file__).resolve().parents[1]
        contract=json.loads((root/'workflow.json').read_text(encoding='utf8'))
        defaults=inspect.signature(Runner).parameters
        for name in ('workers','review_workers','model','review_model','fallback','timeout','max_repairs','checkpoint_every'):
            self.assertEqual(defaults[name].default,contract['defaults'][name])
        self.assertEqual(contract['validation_policy'],POLICY);self.assertEqual(contract['review_policy'],REVIEW_POLICY)
        self.assertEqual(contract['continuity_policy'],CONTINUITY)
        self.assertEqual(inspect.signature(run_campaign).parameters['mode'].default,'resilient')

    def test_api_defaults_to_four_resilient_translators(self):
        with patch('native_oauth.resilient_translation.Runner') as runner:
            run_campaign('book_fixture','job_fixture',5)
            self.assertEqual(runner.call_args.kwargs['workers'],4)
            runner.return_value.run.assert_called_once_with()
