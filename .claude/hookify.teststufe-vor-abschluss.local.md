---
name: teststufe-vor-abschluss
enabled: true
event: stop
action: block
conditions:
  - field: transcript
    operator: regex_match
    pattern: "file_path":"[^"]*/(?:toolgen|scripts/tool_assets)/[^"]*\.py"
  - field: transcript
    operator: not_contains
    pattern: TOOLGEN_OK
---

Generator geändert, aber keine erfolgreiche Teststufe belegt: vor Abschluss mindestens `--tier quick` ausführen.
