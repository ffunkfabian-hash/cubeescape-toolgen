"""Tests for the shared heavy-run queue without starting Blender."""
import importlib.util
import json
import os
import signal
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


    def free(self):
        """True when nobody holds the lock (takes and drops it at once)."""
        import fcntl
        fd = os.open(self.lockfile, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False
        finally:
            os.close(fd)

    def grandchild_run(self, grandchild, then):
        """heavy_lock.py run with a command that starts a grandchild (same process group), says 'go <pid>', then `then`."""
        command = ("import os, subprocess, sys\n"
                   f"subprocess.Popen([sys.executable, '-c', {grandchild!r}], stdout=subprocess.DEVNULL)\n"
                   "print('go', os.getpid(), flush=True)\n" + then)
        wrapper = subprocess.Popen([sys.executable, str(ROOT / "scripts/heavy_lock.py"), "run", "--what",
                                    "toolgen check_output", "--", sys.executable, "-c", command], env=self.env,
                                   stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: wrapper.poll() is None and wrapper.kill())
        self.addCleanup(wrapper.stdout.close)
        word, pid = wrapper.stdout.readline().split()
        self.assertEqual(word, "go")
        return wrapper, int(pid)

    def test_a_grandchild_keeps_the_lock_after_its_parent_died(self):
        # Codex review of 0.4: check_output.sh died, Blender below it still ran - the lock was free
        marker = Path(self.temp.name) / "grandchild-ended"
        grandchild = f"import time; time.sleep(1.5); open({str(marker)!r}, 'w').write('x')"
        wrapper, command_pid = self.grandchild_run(grandchild, "import time; time.sleep(30)")
        os.kill(command_pid, signal.SIGKILL)  # the command dies, the grandchild goes on
        time.sleep(.4)
        self.assertIsNone(wrapper.poll(), "the wrapper still waits for the grandchild")
        self.assertFalse(marker.exists())
        self.assertFalse(self.free(), "the lock is held while the grandchild runs")
        self.assertNotEqual(wrapper.wait(timeout=10), 0, "the killed command stays a failure")
        self.assertTrue(marker.exists(), "the lock was held until the grandchild ended")
        self.assertTrue(self.free())

    def test_a_term_reaches_the_grandchildren_before_the_lock_is_free(self):
        marker = Path(self.temp.name) / "grandchild-ended"
        grandchild = ("import signal, sys, time\n"
                      f"def done(*a): time.sleep(.5); open({str(marker)!r}, 'w').write('x'); sys.exit(0)\n"
                      "signal.signal(signal.SIGTERM, done)\n"
                      f"open({str(marker) + '.ready'!r}, 'w').close()\ntime.sleep(30)\n")
        wrapper, _ = self.grandchild_run(grandchild, "import time; time.sleep(30)")
        ready = str(marker) + '.ready'
        deadline = time.monotonic() + 10
        while not os.path.exists(ready):  # the grandchild has set its handler
            self.assertLess(time.monotonic(), deadline, "the grandchild did not start")
            time.sleep(.02)
        wrapper.terminate()
        wrapper.wait(timeout=10)
        self.assertTrue(marker.exists(), "the grandchild got the TERM and ended before the lock was free")
        self.assertTrue(self.free())

if __name__ == "__main__":
    unittest.main()
