---
name: tg-testing
description: Prüfe Toolgen-Generatoren, Blender-Exporte, Animationen, Cache und nativen Mac-Viewer nach Code-Änderungen. Verwende die passende Teststufe und Screenshot-Prüfung; keine Tests im Spielprojekt.
---

# Toolgen gezielt prüfen

1. `git status --short` und Diff lesen: Generator/Animation, Pipeline/Cache, Viewer, Regeln/Doku?
2. Reine Python-Logik: `python3 -m unittest discover -s tests -v`. Syntax aller geänderten Python-Dateien prüfen;
   Blender-Imports dabei nur kompilieren, nicht im System-Python ausführen.
3. Generator/Animation/Export: `python3 toolgen/generate_tools.py --tier quick`, bei lokal begrenzten Änderungen
   `--tool <ID>`; gemeinsame Pipeline oder Exporter betrifft alle Werkzeuge. Neu angelegte Dateien sind im
   Inhaltsschlüssel enthalten, auch ohne `git add`.
4. Ohne Änderungen wiederholen: jeder betreffende Worker meldet `CACHE_HIT`; Manifest und Modelldateien bleiben
   bytegleich und werden nicht neu geschrieben. Kalt-/Warmläufe nicht vermischen. Bei Hash-/QA-Änderung muss neu gebaut werden.
5. Vor Commit `--tier standard`, für den Lieferstand `--tier full`: alle Welt-/FPS- und Pfeil-Exporte reimportieren.
   Der Bogen prüft alle 97 Frames und die exportierten Morphs; der Magnetgreifer prüft die Aktionsposen. Fehler im
   aktuellen Schrittlog beheben, nie den Prüfer lockern oder gespeicherte QA von Hand „grün“ machen.
6. Viewer: `bash viewer/build.sh <Ausgabe>` und `bash viewer/test_viewer.sh <Ausgabe>`. Tests schreiben Bilder nach
   `<Ausgabe>/QA/Viewer`; alle Varianten, Motion/Reset, Looks, beschädigte Puffer, unbekannte IDs und Seitenleistenbreite.
   Mindestens Welt- und FPS-Modell sowie Bogen gespannt und entspannt ansehen. Bei Interaktionsänderungen native App
   öffnen und Werkzeugwechsel, Leertaste, Schieberegler und Erzeugung praktisch prüfen.
7. Regeln/Profile: `python3 scripts/check_rules.py --shared <ce-agent-tools>`; jeder Hook hat treffende und nicht
   treffende Fälle, Profile erlauben Prüfungen/Doku und sperren Code-Änderungen des Testläufers.

`scripts/check_output.sh [Ausgabe]` prüft Paketintegrität, Python-Tests, Viewer-Build und Viewer-Tests zusammen.
Ein erfolgreicher Bericht eines älteren Laufs beweist keine neue Änderung. Aktuellen Lauf und Logs nennen.
Leistungsangaben aus `logs/toolgen_report.json` mit Last, Stufe, Werkzeugumfang und Cache-Lage angeben.
Unity-Abnahme braucht das Spielprojekt bzw. eine separate Testkopie; diese Prüfungen starten kein Unity.
