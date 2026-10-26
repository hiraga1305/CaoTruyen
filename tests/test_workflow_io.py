"""Exercise real OS locks without models or network calls."""
import os
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from native_oauth.workflow_io import file_lock
from native_oauth.session_monitor import _file_lock


class FileLockTests(unittest.TestCase):
    def test_marker_is_written_only_after_os_lock_for_both_helpers(self):
        for helper in (file_lock, _file_lock):
            with self.subTest(helper=helper.__module__), tempfile.TemporaryDirectory() as directory:
                held = [False]
                if os.name == 'nt':
                    import msvcrt
                    original_lock = msvcrt.locking

                    def locking(fd, mode, size):
                        result = original_lock(fd, mode, size)
                        held[0] = mode != msvcrt.LK_UNLCK
                        return result

                    lock_patch = patch('msvcrt.locking', side_effect=locking)
                else:
                    import fcntl
                    original_lock = fcntl.flock

                    def locking(fd, mode):
                        result = original_lock(fd, mode)
                        held[0] = mode != fcntl.LOCK_UN
                        return result

                    lock_patch = patch('fcntl.flock', side_effect=locking)
                original_open = Path.open
                case = self

                class GuardedHandle:
                    def __init__(self, handle):
                        self.handle = handle

                    def __getattr__(self, name):
                        return getattr(self.handle, name)

                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        self.handle.close()

                    def write(self, data):
                        case.assertTrue(held[0], 'Lock marker was written before acquiring the OS lock')
                        return self.handle.write(data)

                def guarded_open(path, *args, **kwargs):
                    return GuardedHandle(original_open(path, *args, **kwargs))

                with lock_patch, patch.object(Path, 'open', guarded_open):
                    with helper(Path(directory) / 'state'):
                        self.assertTrue(held[0])
                self.assertFalse(held[0])

    def test_parallel_first_open_is_serialized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'new.lock'
            barrier = threading.Barrier(8)
            active = [0]

            def worker(_):
                barrier.wait(timeout=10)
                with file_lock(path):
                    active[0] += 1
                    self.assertEqual(active[0], 1)
                    time.sleep(0.002)
                    active[0] -= 1

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(worker, range(8)))
            self.assertEqual(path.stat().st_size, 1)
