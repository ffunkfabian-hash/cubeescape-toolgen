"""Bundle only verified model packages and source code; omit caches and working logs."""
import json
import shutil
import sys
from pathlib import Path

output, resources, root = map(Path, sys.argv[1:])
sys.path.insert(0, str(root / "toolgen"))
from generate_tools import valid_package

catalog = json.loads((output / "catalog.json").read_text())
for tool in sorted({entry["tool"] for entry in catalog["models"]}):
    if not valid_package(output / tool):
        raise RuntimeError(f"Model package integrity failed: {tool}")
    shutil.copytree(output / tool, resources / "ViewerData" / tool)
shutil.copyfile(output / "catalog.json", resources / "ViewerData/catalog.json")
backend = resources / "backend"
for folder in ("toolgen", "scripts/tool_assets", "data"):
    shutil.copytree(root / folder, backend / folder,
                    ignore=shutil.ignore_patterns(".build", "output", "__pycache__", "*.pyc", "mac_viewer"))
