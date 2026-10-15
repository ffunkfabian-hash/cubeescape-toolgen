"""Exercise repository rules and profiles with the actual ce-shared guard, without vendoring it."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--shared", type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.shared.resolve() / "plugins/ce-shared/hooks"))
import guard

rules = []
for path in (ROOT / ".claude").glob("hookify.*.md"):
    rule = guard.parse_rule(path.read_text())
    if rule: rules.append(rule)
cases = {
    "ausgabe-nie-von-hand": ("file", "/repo/output/bow/ViewerData/scene.json", "/repo/scripts/tool_assets/Bogen/bow_geometry.py"),
    "cube-escape-nicht-aendern": ("file", "/Users/ffunk/Claude/Cube Escape/Assets/model.fbx", "/repo/viewer/Sources/Main.swift"),
    "viewer-pruefen": ("file", "/repo/viewer/Sources/Main.swift", "/repo/data/tools.json"),
    "git-nur-auf-wunsch": ("bash", "git push origin main", "git status --short"),
}
count = 0
for rule in rules:
    if rule["event"] == "stop":
        conditions = rule["conditions"]
        import re
        hit = '{"file_path":"/repo/toolgen/generate_tools.py"}'
        assert re.search(conditions[0]["pattern"], hit, re.IGNORECASE)
        assert not re.search(conditions[0]["pattern"], '{"file_path":"/repo/README.md"}', re.IGNORECASE)
        assert conditions[1]["pattern"] not in hit
        assert conditions[1]["pattern"] in hit + " TOOLGEN_OK"
        count += 4
        continue
    event, hit, miss = cases[rule["name"]]
    tool = "Bash" if event == "bash" else "Edit"
    key = "command" if event == "bash" else "file_path"
    assert guard.matching_rules([rule], tool, {key: hit}), rule["name"]
    assert not guard.matching_rules([rule], tool, {key: miss}), rule["name"]
    count += 2


def payload(agent, tool, data):
    return {"agent_type": agent, "cwd": str(ROOT), "tool_name": tool, "tool_input": data}


def denied(value):
    return guard.decide(value, []) .get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


for agent, allowed, rejected in [
    ("tg-test-runner", "python3 toolgen/generate_tools.py --tier quick", "git commit -m x"),
    ("tg-doc-keeper", "python3 scripts/check_docs.py", "python3 toolgen/generate_tools.py --tier full")]:
    assert not denied(payload(agent, "Bash", {"command": allowed}))
    assert denied(payload(agent, "Bash", {"command": rejected}))
    count += 2
assert denied(payload("tg-test-runner", "Edit", {"file_path": str(ROOT / "README.md")}))
assert not denied(payload("tg-doc-keeper", "Edit", {"file_path": str(ROOT / "docs/TECHNIK.md")}))
assert denied(payload("tg-doc-keeper", "Edit", {"file_path": str(ROOT / "toolgen/generate_tools.py")}))
count += 3
print(f"RULES_OK {count} checks with ce-shared from {args.shared}")
