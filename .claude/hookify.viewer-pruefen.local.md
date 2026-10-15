---
name: viewer-pruefen
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: /viewer/(?!\.build/)|/toolgen/export_viewer\.py$
---

Viewer geändert: `viewer/build.sh` und `viewer/test_viewer.sh` ausführen und Welt/FPS/Animationsbilder prüfen.
