---
name: ausgabe-nie-von-hand
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: /output/
---

Generierte Toolgen-Ausgaben nie von Hand ändern. Generator oder Exporter korrigieren und die passende Teststufe laufen lassen.
