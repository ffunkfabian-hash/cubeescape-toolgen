"""Check local Markdown links, skill metadata, JSON config and shell syntax."""
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
errors = []
paths = [ROOT / name for name in ("README.md", "AGENTS.md", "CLAUDE.md", "CHANGELOG.md", "toolgen/README.md")]
paths += list((ROOT / "docs").glob("*.md")) + list((ROOT / ".agents/skills").rglob("SKILL.md"))
for path in paths:
    text = path.read_text()
    for link in re.findall(r"\]\(([^)]+)\)", text):
        target = unquote(link.split("#")[0])
        if target and "://" not in target and not (path.parent / target).exists():
            errors.append(f"{path.relative_to(ROOT)}: missing {link}")
    if path.name == "SKILL.md":
        assert text.startswith("---\n") and "\nname:" in text and "\ndescription:" in text
for path in [ROOT / ".claude/settings.json", ROOT / ".claude/agent-guard.json", ROOT / "data/tools.json"]:
    json.loads(path.read_text())
for path in [*ROOT.glob("viewer/*.sh"), *ROOT.glob("scripts/*.sh"), *ROOT.glob(".claude/hooks/*.sh")]:
    if subprocess.run(["bash", "-n", str(path)], check=False).returncode: errors.append(f"shell syntax: {path}")
if errors: raise SystemExit("\n".join(errors))
print(f"DOCS_OK {len(paths)} Markdown files, config and shell syntax")
