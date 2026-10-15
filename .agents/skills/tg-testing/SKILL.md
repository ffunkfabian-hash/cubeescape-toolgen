---
name: tg-testing
description: Prüfe Toolgen-Generatoren, Blender-Exporte, Animationen, Cache und nativen Mac-Viewer nach Code-Änderungen. Verwende die passende Teststufe und Screenshot-Prüfung; keine Tests im Spielprojekt.
---

# Toolgen gezielt prüfen

1. `python3 scripts/testplan.py` (zeigt aus dem Diff den kleinsten Prüfweg, die betroffenen Werkzeuge und eine Zeitschätzung;
   `--run` führt ihn aus, `--files …` fragt für andere Dateien) und den Diff lesen: Generator/Animation, Pipeline/Cache,
   Viewer, Regeln/Doku?
2. Reine Python-Logik: `python3 -m unittest discover -s tests -v`. Syntax aller geänderten Python-Dateien prüfen;
   Blender-Imports dabei nur kompilieren, nicht im System-Python ausführen.
3. Generator/Animation/Export: `python3 toolgen/generate_tools.py --tier quick`, bei lokal begrenzten Änderungen
   `--tool <ID>`; gemeinsame Pipeline oder Exporter betrifft alle Werkzeuge. Neu angelegte Dateien sind im
   Inhaltsschlüssel enthalten, auch ohne `git add`.
4. Ohne Änderungen wiederholen: jeder betreffende Worker meldet `CACHE_HIT` (Paket) bzw. `STAGE_HIT` (Stufe); Manifest und
   Modelldateien bleiben bytegleich und werden nicht neu geschrieben. Der Stufen-Cache ist geteilt
   (`~/Library/Caches/CubeEscapeToolgen/cache`, `TOOLGEN_CACHE`): ein frischer Ausgabeordner oder Worktree ist warm, eine Änderung
   baut nur die betroffenen Stufen (`BUILD`/`RENDER` im Log, Zahlen unter `cache` im Bericht). Kalt-/Warmläufe nicht vermischen;
   `--no-cache` erzwingt Neubau, ein leerer `TOOLGEN_CACHE`-Ordner ergibt einen kalten Lauf. Bei Hash-/QA-Änderung muss neu gebaut werden.
   `--tier full` und `scripts/check_output.sh` warten auf die gemeinsame Sperre (`scripts/heavy_lock.py status` zeigt den Halter);
   den Wartebericht nicht als Fehler lesen, die Sperre nicht umgehen. Braucht eine Messung den Rechner für sich, siehe `AGENTS.md`.
5. Vor Commit `--tier standard`, für den Lieferstand `--tier full`: alle Welt-/FPS- und Pfeil-Exporte reimportieren.
   Der Bogen prüft alle 97 Frames und die exportierten Morphs; der Magnetgreifer prüft die Aktionsposen. Fehler im
   aktuellen Schrittlog beheben, nie den Prüfer lockern oder gespeicherte QA von Hand „grün“ machen.
6. Viewer: `bash viewer/build.sh <Ausgabe>` und `bash viewer/test_viewer.sh <Ausgabe>`. Tests schreiben Bilder nach
   `<Ausgabe>/QA/Viewer`; alle Varianten, Motion/Reset, Looks, beschädigte Puffer, unbekannte IDs und Seitenleistenbreite.
   Mindestens Welt- und FPS-Modell sowie Bogen gespannt und entspannt ansehen. Bei Interaktionsänderungen native App
   öffnen und Werkzeugwechsel, Leertaste, Schieberegler und Erzeugung praktisch prüfen.
   Bei Ego-Haltungen zusätzlich `qa_viewmodel.json` (97 Frames: Kontakte, Kameraabstand, freie Mitte, Ruhepose; verbindlich
   beim eingestellten Viewmodel-Sichtfeld für 16:9 und 16:10, `fov_range` und `head` ansehen: Werkzeugkopf unverdeckt)
   und ab Standard `qa_viewmodel_roundtrip.json` prüfen. Der Regler „Sichtfeld“ und `--fov` gehören zur Ego-Prüfung. Griff-/Zughand in Ruhe, voll gespannt und beim Nachgreifen
   ansehen. Verbindliche Gestaltung: `docs/TECHNIK.md` › Hände und Bewegungsgefühl. Genau vier Finger pro Hand (drei Greiffinger plus
   ein Daumen), Fingersegmente nicht als zusätzliche Finger lesbar, natürliche Händigkeit (linkes/rechtes Handgelenk auf seiner Griffseite,
   niemals um 180° drehen, nur um Finger zu zeigen), Hände vollständig, höchstens halbe Unterarme; keine Ellenbogen/Oberarme im Bild.
   Handwurzel mittig hinter der Handfläche (+Y), nicht unterhalb der Fingerreihe (−Z); Bogen und Griffhand
   bewegen sich beim Spannen/Schuss gemeinsam. Unterarm-Mesh nicht am sichtbaren Ende abschneiden: kontinuierlich über den Bildrand führen. Die proximale
   Hälfte über alle 97 Frames außerhalb prüfen. Bogen-/Handmaß gemeinsam abstimmen; Gliedlängen niemals aus
   Werkzeugabstand ableiten. Nach einem fehlgeschlagenen Bau keine alte Vorschau als neue Prüfung ausgeben.
   Screenshots/Movies mit `--data <frische Ausgabe>` erzeugen, damit kein altes App-Bundle verwendet wird;
   Movie-Export und FFmpeg-Aufruf stehen im Systemdoc. Handgrößen/Haltungen sind Daten in `data/viewmodels.json`, Bewegungsprofile in `motion_profiles.py`.
7. Spiel-Export (Stufe `game`): `<Werkzeug>/qa_game.json` muss `passed: true` sein, jede Prüfung (Palette, Renderer,
   Materialien, Maße, Anker, Clip bei animierten Werkzeugen, LOD1, Kollision, GLB-/FBX-Reimport) einzeln lesen; `preview_game.png` (ab Standard) ansehen:
   Weltmodell, LOD0, LOD1, Kollisionsboxen. Kollision gegen das tatsächliche Modell, Öffnungen frei. Viewer-Varianten
   „Spielmodell“ und „Ego-Spielmodell“ mit ansehen (Ego-Spielmodell neben dem gestalteten Ego-Modell: gleicher Bildausschnitt, matter). Dasselbe für das Ego-Modell (Stufe `game_fps`): `qa_game_fps.json` (zusätzlich `triangle_budget`),
   `preview_game_fps.png`; keine Kollision, Hände/Arme im Bild unverändert.
8. Regeln/Profile: `python3 scripts/check_rules.py --shared <ce-agent-tools>`; jeder Hook hat treffende und nicht
   treffende Fälle, Profile erlauben Prüfungen/Doku und sperren Code-Änderungen des Testläufers.

`scripts/check_output.sh [Ausgabe]` prüft Paketintegrität, Python-Tests, Viewer-Build und Viewer-Tests zusammen.
Ein erfolgreicher Bericht eines älteren Laufs beweist keine neue Änderung. Aktuellen Lauf und Logs nennen.
Leistungsangaben aus `logs/toolgen_report.json` mit Last, Stufe, Werkzeugumfang und Cache-Lage angeben.
Unity-Abnahme braucht das Spielprojekt bzw. eine separate Testkopie; diese Prüfungen starten kein Unity.
