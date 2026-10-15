#!/usr/bin/env python3
"""Thin forward to the embedded shared heavy-run lock (scripts/ce_tools/heavy_lock.py, from ce-agent-tools).

Kept so `python3 scripts/heavy_lock.py run|status` and `import heavy_lock` (generate_tools.py, tests) keep working.
The lock itself (one queue for Cube Escape, Robogen, Cubegen, Toolgen) lives in the embedded copy; update it with
`python3 $CE_TOOLS/ce_sync.py --repo .`, never edit it. Callers pass `checkout` explicitly (the shared default is cwd).
"""
import importlib.util
import os
import sys

_SHARED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ce_tools", "heavy_lock.py")
_spec = importlib.util.spec_from_file_location("ce_tools_heavy_lock", _SHARED)
_shared = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("ce_tools_heavy_lock", _shared)
_spec.loader.exec_module(_shared)
globals().update({name: value for name, value in vars(_shared).items() if not name.startswith("__")})

if __name__ == "__main__":
    sys.exit(_shared.main(sys.argv[1:]))
