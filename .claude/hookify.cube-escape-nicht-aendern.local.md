---
name: cube-escape-nicht-aendern
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: /Cube Escape/(Assets|Packages|ProjectSettings|Tools|Docs)/
---

Das Spielprojekt wird nicht aus Toolgen verändert. Integration in dessen eigener Sitzung und Testkopie durchführen.
