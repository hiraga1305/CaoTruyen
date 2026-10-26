"""Actual local Git/locks and mocked upstream; never models or network calls."""
import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import native_oauth.workflow_guard as guard
from native_oauth.run_agy import run
from native_oauth.workflow_io import atomic_json


class WorkflowGuardTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        workflow = json.loads((guard.ROOT / 'workflow.json').read_text(encoding='utf-8'))
        atomic_json(self.root / 'workflow.json', workflow)
        names = ('translate.py', 'native_oauth/workflow_guard.py',
                 'native_oauth/resilient_translation.py', 'native_oauth/run_agy.py')
        for name in names:
            p = self.root / name;p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('# Offline source fixture\n', encoding='utf-8')
        self.lock = {'schema': 'caotruyen-release-1', 'workflow_id': workflow['id'], 'version': workflow['version'],
                     'files': {name: guard.file_hash(self.root / name) for name in ('workflow.json', *names)}}
        atomic_json(self.root / guard.LOCK, self.lock)
        (self.root / 'unrelated_novel.txt').write_text('Original fixture', encoding='utf-8')
        self.git('init', '-q');self.git('add', '--', *self.lock['files'], guard.LOCK, 'unrelated_novel.txt')
        self.commit()
        self.remote_head = self.git('rev-parse', 'HEAD')
        original_git = guard.git_output

        def local_git(root, *args):
            if args[0] == 'ls-remote':
                self.assertEqual(args[2], guard.REPOSITORY + '.git')
                self.assertEqual(args[-1], 'refs/heads/main')
                return self.remote_head + '\trefs/heads/main'
            return original_git(root, *args)

        for setting in (patch.object(guard, 'ROOT', self.root),
                        patch.object(guard, '_import_lock_hash', guard.file_hash(self.root / guard.LOCK)),
                        patch.object(guard, 'git_output', side_effect=local_git),
                        patch.dict(guard._leases, {}, clear=True),
                        patch.dict(os.environ, {'ANTIGRAVITY_ARTIFACT_DIR': str(self.root / 'session')}),
                        contextlib.redirect_stdout(io.StringIO())):
            setting.__enter__();self.addCleanup(setting.__exit__, None, None, None)
        self.job = self.root / 'audit/job'
        self.config = {'workflow_release': guard.release_identity(guard.local_release()),
                       'continuity_policy': workflow['continuity_policy'], 'validation_policy': workflow['validation_policy'],
                       'review_policy': workflow['review_policy'], 'book': str(self.root / 'book'), 'through': 5,
                       'translator': 'fixture', 'reviewer': 'fixture', 'reviewer2': 'fixture', 'fallback': 'fixture-high'}
        atomic_json(self.job / 'configuration.json', self.config)

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, capture_output=True, check=True).stdout.decode().strip()

    def commit(self):
        self.git('-c', 'user.name=Offline fixture', '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
                 'commit', '-qm', 'Offline fixture release')

    def request(self, role='translator'):
        work = self.job / 'native_attempts' / role / 'attempt-01'
        data = work / 'native_oauth/runs/chapter1';data.mkdir(parents=True, exist_ok=True)
        prompt = data / (role + '.prompt.txt');prompt.write_text('Offline fixture', encoding='utf-8')
        packet = ({'continuity_contract': {'version': self.config['continuity_policy']},
                   'validation_policy': self.config['validation_policy']} if role == 'translator' else
                  {'continuity_policy': self.config['continuity_policy'], 'review_policy': self.config['review_policy']})
        atomic_json(data / 'source.json', packet)
        return prompt, data / (role + '.runtime'), work

    def test_doctor_verifies_git_main_and_ignores_unrelated_dirty_novel_data(self):
        (self.root / 'unrelated_novel.txt').write_text('User edit preserved', encoding='utf-8')
        report = guard.doctor(job=self.job)
        self.assertEqual(report['status'], 'CURRENT');self.assertTrue(report['job_compatible_release'])
        self.assertEqual(report['git_commit'], self.remote_head)

    def test_old_checkout_cannot_become_current_by_printing_a_new_version(self):
        value = json.loads((self.root / 'workflow.json').read_text(encoding='utf-8'));value['version'] = '999.0.0'
        atomic_json(self.root / 'workflow.json', value)
        with self.assertRaises(guard.WorkflowGateError):guard.doctor()

    def test_uncommitted_rebuilt_lock_is_not_trusted_even_when_local_hashes_match(self):
        value = copy.deepcopy(self.lock);value['extra'] = 'Local rewrite is not upstream evidence'
        atomic_json(self.root / guard.LOCK, value)
        with self.assertRaisesRegex(guard.WorkflowGateError, 'verified Git commit'):guard.doctor()

    def test_old_upstream_commit_blocks_before_native_process(self):
        self.remote_head = 'f' * 40
        with self.assertRaisesRegex(guard.WorkflowGateError, 'canonical GitHub main'):
            with guard.authorized_invocation(self.job, self.config):pass
        self.assertFalse((self.job/'workflow_startup.json').exists())

    def test_snapshot_inside_repo_is_not_a_valid_launch_root(self):
        snapshot = self.root / 'audit/workflow_snapshot'
        for name in (*self.lock['files'], guard.LOCK):
            target = snapshot / name;target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.root / name, target)
        with self.assertRaisesRegex(guard.WorkflowGateError, 'repository root'):guard.doctor(snapshot)

    def test_legacy_native_entry_point_without_lease_never_starts_cli(self):
        prompt, runtime, work = self.request()
        with patch('native_oauth.run_agy.subprocess.Popen') as process:
            with self.assertRaisesRegex(guard.WorkflowGateError, 'no process-local'):
                run(prompt, runtime, model='fixture', workspace=work, stdin_prompt=True)
            process.assert_not_called()

    def test_copied_receipt_after_invocation_does_not_authorize_another_call(self):
        with guard.authorized_invocation(self.job, self.config):pass
        self.assertTrue((self.job / 'workflow_startup.json').exists())
        prompt, runtime, work = self.request()
        with self.assertRaises(guard.WorkflowGateError):guard.before_native(prompt, runtime, 'fixture', work, False, True)

    def test_current_lease_allows_independent_threaded_roles(self):
        requests = [self.request(role) for role in ('translator', 'meaning-reviewer', 'literary-reviewer')]
        with guard.authorized_invocation(self.job, self.config), ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda r: guard.before_native(r[0], r[1], 'fixture', r[2], False, True), requests))
        self.assertFalse(guard._leases)

    def test_upstream_changed_during_watch_stops_next_wave(self):
        with guard.authorized_invocation(self.job, self.config):
            guard.check_boundary(self.job)
            self.remote_head = 'e' * 40
            with self.assertRaises(guard.WorkflowGateError):guard.check_boundary(self.job)

    def test_code_changed_after_import_blocks_next_native_call_without_popen(self):
        prompt, runtime, work = self.request()
        with guard.authorized_invocation(self.job, self.config):
            (self.root / 'native_oauth/resilient_translation.py').write_text('# Changed workflow\n', encoding='utf-8')
            with patch('native_oauth.run_agy.subprocess.Popen') as process:
                with self.assertRaisesRegex(guard.WorkflowGateError, 'release lock'):
                    run(prompt, runtime, model='fixture', workspace=work, stdin_prompt=True)
                process.assert_not_called()

    def test_stale_import_requires_a_fresh_python_process(self):
        with patch.object(guard, '_import_lock_hash', '0' * 64):
            with self.assertRaisesRegex(guard.WorkflowGateError, 'older release'):
                with guard.authorized_invocation(self.job, self.config):pass

    def test_job_policy_cannot_be_downgraded(self):
        config = {**self.config, 'continuity_policy': 'old-policy'}
        atomic_json(self.job / 'configuration.json', config)
        with self.assertRaisesRegex(guard.WorkflowGateError, 'another release/policy'):
            with guard.authorized_invocation(self.job, config):pass

    def test_configuration_tampering_after_startup_is_not_an_upgrade(self):
        prompt, runtime, work = self.request()
        with guard.authorized_invocation(self.job, self.config):
            atomic_json(self.job / 'configuration.json', {**self.config, 'through': 500})
            with self.assertRaisesRegex(guard.WorkflowGateError, 'configuration changed'):
                guard.before_native(prompt, runtime, 'fixture', work, False, True)

    def test_mutating_a_caller_dictionary_cannot_change_the_allowed_model(self):
        prompt, runtime, work = self.request()
        with guard.authorized_invocation(self.job,self.config):
            self.config['translator']='unconfigured-model'
            guard.before_native(prompt,runtime,'fixture',work,False,True)
            with self.assertRaisesRegex(guard.WorkflowGateError,'role/workspace/model'):
                guard.before_native(prompt,runtime,'unconfigured-model',work,False,True)

    def test_packet_cannot_keep_current_badge_while_using_old_policy(self):
        prompt, runtime, work = self.request()
        with guard.authorized_invocation(self.job, self.config):
            atomic_json(prompt.parent / 'source.json', {'validation_policy': 'old'})
            with self.assertRaisesRegex(guard.WorkflowGateError, 'continuity policy'):
                guard.before_native(prompt, runtime, 'fixture', work, False, True)

    def test_tool_enabled_wrong_model_or_unowned_paths_are_rejected(self):
        prompt, runtime, work = self.request()
        variants = [('fixture', work, True, True, runtime), ('fixture', work, False, False, runtime),
                    ('other-model', work, False, True, runtime), ('fixture', self.root, False, True, runtime),
                    ('fixture', work, False, True, self.root / 'unowned-runtime')]
        with guard.authorized_invocation(self.job, self.config):
            for model, workspace, tools, stdin, target in variants:
                with self.subTest(variant=(model, workspace, tools, stdin)), self.assertRaises(guard.WorkflowGateError):
                    guard.before_native(prompt, target, model, workspace, tools, stdin)

    def test_lease_is_removed_after_interruption(self):
        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            with guard.authorized_invocation(self.job, self.config):raise RuntimeError('interrupted')
        self.assertFalse(guard._leases)

    def test_code_hash_is_portable_across_lf_and_crlf(self):
        path = self.root / 'native_oauth/run_agy.py'
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.assertEqual(guard.doctor()['status'], 'CURRENT')

    def test_future_version_is_read_from_upstream_metadata_not_a_pinned_number(self):
        value = json.loads((self.root / 'workflow.json').read_text(encoding='utf-8'));value['version'] = '9.4.0'
        atomic_json(self.root / 'workflow.json', value)
        lock = copy.deepcopy(self.lock);lock['version'] = '9.4.0';lock['files']['workflow.json'] = guard.file_hash(self.root / 'workflow.json')
        atomic_json(self.root / guard.LOCK, lock)
        self.git('add', '--', 'workflow.json', guard.LOCK);self.commit();self.remote_head = self.git('rev-parse', 'HEAD')
        self.assertEqual(guard.doctor()['workflow_version'], '9.4.0')


if __name__ == '__main__':unittest.main()
