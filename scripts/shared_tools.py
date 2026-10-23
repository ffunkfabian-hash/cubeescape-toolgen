"""Locate the shared tools of ce-agent-tools (pinned in .ce-repo.json > tools_version) through the loader ./ce.

The repo keeps no copy: `./ce tools where` names the folder (CE_TOOLS, installed plugin or the checked cache). Scripts that
import a shared module (ce_docs, ce_contract, the heavy-run lock) call `tools_dir()` or `use()` instead of a path of their own.
"""
import importlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tools_dir(root=ROOT):
    out = subprocess.run([sys.executable, os.path.join(root, "ce"), "tools", "where"], capture_output=True, text=True)
    folder = out.stdout.strip().split(" (")[0]
    if out.returncode or not os.path.isfile(os.path.join(folder, "ce")):
        sys.exit("shared tools not available - run ./ce tools fetch\n" + out.stderr)
    return folder


def use(module):
    """Import a module of the shared tools without writing bytecode into the (read-only, checked) tools folder."""
    sys.dont_write_bytecode = True
    folder = tools_dir()
    if folder not in sys.path:
        sys.path.insert(0, folder)
    return importlib.import_module(module)
