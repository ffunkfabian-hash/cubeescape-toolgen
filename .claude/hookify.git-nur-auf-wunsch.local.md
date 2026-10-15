---
name: git-nur-auf-wunsch
enabled: true
event: bash
action: warn
conditions:
  - field: command
    operator: regex_match
    pattern: \bgit\s+(?:-C\s+\S+\s+)?(?:commit|merge|tag|push)\b
---

Commit, Merge, Tag und Push nur auf ausdrücklichen Nutzerauftrag. Ein Feature-Auftrag allein erlaubt keine Veröffentlichung.
