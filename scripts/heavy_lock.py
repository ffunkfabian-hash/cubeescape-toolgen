#!/usr/bin/env python3
"""Thin forward to the shared heavy-run lock (heavy_lock.py of the pinned ce-agent-tools, `./ce tools where`).

Kept so the command line (`scripts/heavy_lock.py run|status`) and `import heavy_lock` (generate_tools.py, tests) keep working.
The lock itself (one queue for Cube Escape, Robogen, Cubegen, Toolgen) lives in ce-agent-tools; change it there and re-pin
tools_version, never here. Callers pass `checkout` explicitly (the shared default is cwd); a command-line `run` without
`--checkout` gets the repository root.
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shared_tools  # noqa: E402

sys.dont_write_bytecode = True  # never write .pyc into the checked tools cache (root ignores read-only)
_spec = importlib.util.spec_from_file_location("ce_tools_heavy_lock", os.path.join(shared_tools.tools_dir(), "heavy_lock.py"))
_shared = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("ce_tools_heavy_lock", _shared)
_spec.loader.exec_module(_shared)
globals().update({name: value for name, value in vars(_shared).items() if not name.startswith("__")})
ROOT = _shared.ROOT = shared_tools.ROOT  # the repository, not the plugin folder

if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv[:1] == ["run"] and "--checkout" not in argv:
        argv = ["run", "--checkout", ROOT] + argv[1:]
    sys.exit(_shared.main(argv))
