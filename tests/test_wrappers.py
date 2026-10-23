"""Wrappers around the shared tools (0.26, no embedded copy): ./check, ./release, scripts/heavy_lock.py and
scripts/shared_tools.py find the tools through the loader ./ce (tools_version) - tested in a temporary repo with a fake tools
folder (CE_TOOLS), no network."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")

FAKE_CE = '#!/bin/sh\necho "ce-args:$*"\n'
FAKE_RELEASE = (
    "import os, sys\n"
    "print('release-args:' + ' '.join(sys.argv[1:]))\n"
    "print('nobytecode:' + os.environ.get('PYTHONDONTWRITEBYTECODE', ''))\n"
)
FAKE_LOCK = (
    "import sys\n"
    "ROOT = None\n"
    "def main(argv):\n"
    "    print('lock-args:' + ' '.join(argv))\n"
    "    print('nobytecode:%s' % sys.dont_write_bytecode)\n"
    "    return 0\n"
)


class Wrappers(unittest.TestCase):
    def setUp(self):
        self.repo = self.temp()
        self.tools = self.temp()
        for name in ("ce", "check", "release"):
            shutil.copy(os.path.join(ROOT, name), os.path.join(self.repo, name))
        os.makedirs(os.path.join(self.repo, "scripts"))
        for name in ("heavy_lock.py", "shared_tools.py"):
            shutil.copy(os.path.join(SCRIPTS, name), os.path.join(self.repo, "scripts", name))
        with open(os.path.join(self.repo, ".ce-repo.json"), "w") as fh:
            json.dump({"name": "t", "tools_version": {"version": "0.21.0", "commit": "0" * 40}}, fh)
        for name, text in (("ce", FAKE_CE), ("ce_release.py", FAKE_RELEASE), ("heavy_lock.py", FAKE_LOCK)):
            with open(os.path.join(self.tools, name), "w") as fh:
                fh.write(text)
        self.env = dict(os.environ, CE_TOOLS=self.tools)
        self.env.pop("PYTHONDONTWRITEBYTECODE", None)

    def temp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        return os.path.realpath(folder.name)

    def run_in_repo(self, *argv):
        return subprocess.run(list(argv), cwd=self.repo, env=self.env, capture_output=True, text=True)

    def test_no_embedded_copy_is_left(self):
        # tracked files only: an ignored __pycache__ of old runs may survive a pull in an existing checkout
        tracked = subprocess.run(["git", "ls-files", "scripts/ce_tools"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(tracked.stdout.strip(), "", tracked.stderr)
        with open(os.path.join(ROOT, ".ce-repo.json")) as fh:
            config = json.load(fh)
        self.assertIn("tools_version", config)
        self.assertNotIn("tools_dir", config)

    def test_check_runs_ce_check(self):
        out = self.run_in_repo("./check", "--full")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("ce-args:check --full", out.stdout)

    def test_release_runs_the_shared_release_check_without_bytecode(self):
        out = self.run_in_repo("./release", "--execute")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("release-args:--repo %s --execute" % self.repo, out.stdout)
        self.assertIn("nobytecode:1", out.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.tools, "__pycache__")))

    def test_release_fails_clearly_without_tools(self):
        os.remove(os.path.join(self.tools, "ce_release.py"))
        out = self.run_in_repo("./release")
        self.assertEqual(out.returncode, 2)
        self.assertIn("ce_release.py missing", out.stderr)

    def test_heavy_lock_forwards_to_the_shared_lock_without_bytecode(self):
        out = self.run_in_repo(sys.executable, "scripts/heavy_lock.py", "status")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("lock-args:status", out.stdout)
        self.assertIn("nobytecode:True", out.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.tools, "__pycache__")))

    def test_heavy_lock_run_gets_the_checkout(self):
        out = self.run_in_repo(sys.executable, "scripts/heavy_lock.py", "run", "--", "true")
        self.assertIn("lock-args:run --checkout %s -- true" % self.repo, out.stdout)

    def test_heavy_lock_stops_without_tools(self):
        os.remove(os.path.join(self.tools, "ce"))
        out = self.run_in_repo(sys.executable, "scripts/heavy_lock.py", "status")
        self.assertNotEqual(out.returncode, 0)

    def test_shared_tools_names_the_tools_folder(self):
        code = "import sys; sys.path.insert(0, 'scripts'); import shared_tools; print(shared_tools.tools_dir())"
        out = self.run_in_repo(sys.executable, "-c", code)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), self.tools)


if __name__ == "__main__":
    unittest.main()
