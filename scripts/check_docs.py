#!/usr/bin/env python3
"""Thin wrapper (0.22): the shared ce_docs.py checks Markdown links/anchors, skill front matter, JSON and shell syntax
with the lists in .ce-repo.json > docs (check, json, shell). python3 scripts/check_docs.py [--json REPORT]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "ce_tools"))
import ce_docs  # noqa: E402

if __name__ == "__main__":
    sys.exit(ce_docs.main(["--repo", str(Path(__file__).resolve().parents[1]), *sys.argv[1:]]))
