"""Tests for the shared heavy-run queue without starting Blender."""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("toolgen_heavy_lock", ROOT / "scripts/heavy_lock.py")
heavy_lock = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(heavy_lock)


class HeavyLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.lockfile = str(Path(self.temp.name) / "heavy.lock")
        # check_output.sh runs these tests while it holds the real lock: drop its markers.
        outer = {name: value for name, value in os.environ.items() if name not in ("CE_HEAVY_HELD", "CE_HEAVY_LOCK")}
        self.env = dict(outer, CE_HEAVY_LOCK_FILE=self.lockfile)
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_holder_line_and_release(self):
        lock = heavy_lock.HeavyLock("toolgen test", checkout="/checkout").acquire()
        try:
            line = json.loads(Path(self.lockfile).read_text())
            self.assertEqual((line["pid"], line["what"], line["checkout"]), (os.getpid(), "toolgen test", "/checkout"))
            self.assertIn("since", line)
            self.assertIn("toolgen test", heavy_lock.holder())
        finally:
            lock.release()
        self.assertIsNone(heavy_lock.holder())
        self.assertNotIn("CE_HEAVY_HELD", os.environ)

    def test_waits_then_acquires_after_release(self):
        held = heavy_lock.HeavyLock("first").acquire()
        output = []
        def release():
            time.sleep(.15); held.release()
        thread = threading.Thread(target=release); thread.start()
        with patch.dict(os.environ, CE_HEAVY_HELD=""):
            waiter = heavy_lock.HeavyLock("second", poll=.01, out=output.append).acquire()
        thread.join()
        try:
            self.assertTrue(waiter.held)
            self.assertTrue(any("first" in line for line in output))
        finally:
            waiter.release()

    def test_opt_out_and_already_held_environment(self):
        for env, expected in ((dict(self.env, CE_HEAVY_LOCK="0"), "CE_HEAVY_LOCK=0"),
                              (dict(self.env, CE_HEAVY_HELD="1"), "CE_HEAVY_HELD=1")):
            result = subprocess.run([sys.executable, str(ROOT / "scripts/heavy_lock.py"), "run", "--", sys.executable,
                                     "-c", "import os; print(os.getenv('CE_HEAVY_HELD',''))"], env=env,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout)

    def test_lock_descriptor_is_not_inherited_by_child(self):
        lock = heavy_lock.HeavyLock("parent").acquire()
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(.3)"])
        lock.release()
        try:
            self.assertIsNone(heavy_lock.holder())
        finally:
            child.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
