# Cube Escape – Toolgen

**0.8.0 · Gunmetal.** Blender-Generator und nativer Mac-Viewer für die ausgearbeiteten Cube-Escape-Werkzeuge,
mit Spiel-Export für Unity. Oberfläche und Prüfablauf folgen [Robogen](https://github.com/ffunkfabian-hash/cubeescape-robogen):
große 3D-Ansicht, rechte Seitenleiste, Aktionssteuerung, Looks und Teststufen mit geteiltem Stufen-Cache. Gemeinsame Agentenregeln kommen aus
[ce-agent-tools](https://github.com/ffunkfabian-hash/ce-agent-tools).

## Start

Python 3, Blender 5.2.2 LTS, macOS 14+ und Xcode Command Line Tools; ImageMagick (`magick`) für GIFs und Bildtests.

```bash
python3 toolgen/generate_tools.py --tier quick
bash viewer/build.sh output/_quick
open output/_quick/ToolGenViewer.app
```

Dazu kommen neun Handwaffen (Pistole bis Raketenwerfer, Elementfarben KINETIC/ENERGY/SOLAR/VOID/ARC) mit Ego-Modell, Stützhand am Handschutz,
Rückstoß und Use-Clip: [TECHNIK](docs/TECHNIK.md) › Waffen 1–9.

Die App bündelt den Katalog und zeigt die Portalkanone sofort an. Portalkanone, Magnetgreifer, Taschenlampe und Bogen
haben Welt- und FPS-Modelle, der Bogen zusätzlich einen separaten Pfeil. Die beiden Gehäuse sind schmaler und kürzer;
eine offene Zuführung legt Emitter und Greifkopf frei. Der Bogen hat schlankere Verkleidungen und eine offenere Silhouette.
Die Ego-Modelle haben Roboterhände und Unterarme im Mitt-Stil von Robogen, jede Hand mit drei Greiffingern und einem
Daumen. Portalkanone und Magnetgreifer werden mit zwei Händen gehalten, die Taschenlampe mit einer. Sichtbar sind die Hände und maximal halbe Unterarme;
Ellenbogen und Oberarme bleiben außerhalb des Bildes. Die Unterarme laufen ohne sichtbare Schnittkante über den Bildrand.
Der Bogen liegt diagonal in der linken Hand;
die rechte Hand spannt die Sehne, löst und greift beim Nachladen erneut zu. Haltung und Bewegungsphasen orientieren
sich an den Destiny-2-Referenzen; die Geometrie und Animationen werden hier prozedural erzeugt.
Das Ego-Sichtfeld steht als Datenwert in `data/viewmodels.json` (vertikal 46,69°, Near Clip 3 cm) und gehört im Spiel
zu einem eigenen Viewmodel-FOV; jedes Ego-Paket enthält dazu `viewmodel_camera.json`.

Der Spiel-Export (Stufe `game`) macht aus jedem Weltmodell ein Unity-fertiges Spielmodell: statische Teile in einem
Renderer, bewegliche Teile getrennt, matte Cube-Escape-Materialien (`data/game_palette.json`), Dreiecksbudget
(`data/game_budget.json`), LOD0/LOD1, Kollisionsboxen und `unity_contract.json`. Die Stufe `game_fps` macht dasselbe für das
Ego-Modell (eigenes Budget, keine Kollision, Viewmodel-Kameradaten in `unity_contract_fps.json`). Details und Werte:
[TECHNIK](docs/TECHNIK.md) › Spiel-Export; Einbau-Vorbereitung: [UNITY_EINBAU](docs/UNITY_EINBAU.md).

Orbit/Zoom, Iso/Front/Seite/Hinten/Ego, Drehteller, Boden und Anker helfen bei der Prüfung. „Ego“ lädt automatisch
das passende FPS-Modell, auch im A/B-Vergleich; der Regler „Sichtfeld“ der Ego-Ansicht (35–75°, Zurücksetzen auf den Datenwert) wirkt
auf Ansicht, A/B und PNG (Kommandozeile `--fov`). Die Varianten „Spielmodell“ und „Ego-Spielmodell“ zeigen den Spiel-Export (nur LOD0, Ego mit derselben Kamera und Animation); die Ego-Taste öffnet aus dem Spielmodell das Ego-Spielmodell, sonst das gestaltete Ego-Modell. Bogen und Magnetgreifer
spielen ihre Aktion auf Wunsch, mit Reset, Tempo und optionaler Prüfschleife. Materialfinish, Verkleidungsfarbe und
Leuchtstärke können verändert und als B-Vergleich gemerkt werden. Leertaste startet/pausiert; Cmd+O/Cmd+S laden/speichern
Looks, Cmd+Shift+S exportiert ein PNG.

„Werkzeug erzeugen“ startet dieselbe Pipeline wie die CLI. Ausgaben standardmäßig `~/Documents/CubeEscapeToolgen`,
änderbar im Viewer. Python und Blender müssen lokal installiert sein. `TOOLGEN_PYTHON`, `TOOLGEN_BLENDER` bzw.
`BLENDER_BIN` wählen Programme; `TOOLGEN_DATA` einen anderen Katalog. Die gebündelte Bibliothek bleibt beim Erzeugen verfügbar.

## Prüfungen

```bash
python3 scripts/testplan.py              # kleinster Prüfweg aus dem Diff; --run führt ihn aus
python3 -m unittest discover -s tests -v
python3 toolgen/generate_tools.py --tier standard
python3 toolgen/generate_tools.py --tier full
bash scripts/check_output.sh output
```

| Stufe | Ausgabe | Umfang |
|---|---|---|
| quick | `output/_quick` | Modelle, Animation, Geometrie-QA, Spiel-Export mit QA, Viewer-Daten; keine Bilder |
| standard | `output/_standard` | zusätzlich FBX-/GLB-Reimport der Weltmodelle und Bilder (12 Samples, 50 %) |
| full | `output` | dieselben Prüfungen, volle Bilder (40 Samples, 100 %) |

`--tool bow` grenzt einen Lauf ein. Jede Stufe hat einen eigenen Inhaltsschlüssel; ihr Ergebnis liegt im geteilten Cache
`~/Library/Caches/CubeEscapeToolgen/cache` (`TOOLGEN_CACHE`, Grenze `TOOLGEN_CACHE_LIMIT_GB`, Standard 4). Ein frischer
Ausgabeordner oder Worktree startet damit warm; eine Änderung baut nur die betroffenen Stufen neu. Ohne Änderung wiederholen:
Cache-Treffer behalten alle geprüften Dateien. `--no-cache` baut neu. Standardmäßig zwei Worker mit geteilter CPU-Kernzahl;
`--workers`/`--threads` begrenzen die Last. `full` und `check_output.sh` warten auf die gemeinsame Sperre
(`scripts/heavy_lock.py`, geteilt mit Robogen, Cube Escape und Cubegen; `CE_HEAVY_LOCK=0` überspringt sie).
Bericht: `logs/toolgen_report.json` mit Schrittzeiten, Last, Cache und Zeitband. Schwere Last wird nicht bewertet.

Blender-QA prüft geschlossene Geometrie, Metermaße, Materialien, UVs, Anker, Hierarchie und Animation. Der Spiel-Export
prüft Palette, Renderer- und Materialzahl, Abmessungen gegen das Weltmodell in jedem Clipbild, identische Anker, LOD1, Kollisionsboxen und den
Blend-/GLB-/FBX-Reimport (`qa_game.json`, Ego: `qa_game_fps.json`). Bogen und
Magnetgreifer haben je 97 Aktionsframes; der Bogen enthält Morphs und kehrt in die geladene Ruhepose zurück. Viewer-Tests
kontrollieren alle Varianten, Bewegung/Reset, echte Zwischenbild-Interpolation, Looks, beschädigte Daten und die Seitenleistenbreite.
Die Handbaugruppen prüfen an allen 97 Frames Griffkontakt, freie Bildmitte, Kameraabstand und Rückkehr zur Ruhepose,
verbindlich beim eingestellten Sichtfeld für 16:9 und 16:10 (±8° nur berichtet), dazu die Sicht auf den Werkzeugkopf;
Standard/Voll vergleichen die Gelenkposen nach FBX-/GLB-Reimport.
Unity-Import, Kameramontage, Clip-Anbindung und Gameplay werden separat im Spiel abgenommen. Der unveränderte
Magnetgreifer-C#-Player enthält historische Kompilierungsnachweise, keine Unity-Laufzeitabnahme.

## Aufbau

- [AGENTS.md](AGENTS.md): Regeln und Plugins; [Test-Skill](.agents/skills/tg-testing/SKILL.md).
- `data/tools.json`: Katalog; `scripts/tool_assets/`: Autoren-Generatoren und gemeinsame Designprofile.
- `data/viewmodels.json`: Ego-Haltungen, Handgrößen, Viewmodel-Sichtfeld und Herkunft des Robogen-Mitt-Vertrags.
- `data/game_palette.json`: matte Spielpalette mit Cube-Escape-Materialnamen; `data/game_budget.json`: LOD0-Dreiecksbudgets.
- `toolgen/`: gemeinsame Pipeline (`generate_tools.py`, Stufenliste `STAGES`), Stufen-Cache (`toolcache.py`), Spiel-Export
  (`game_export.py`) und Binärexport; [CLI-Details](toolgen/README.md).
- `scripts/`: `testplan.py` (Prüfweg aus dem Diff), `heavy_lock.py` (gemeinsame Sperre), `check_output.sh`, `check_docs.py`.
- `viewer/`: SwiftUI-/SceneKit-App, universeller Build und Bildtests.
- `output/`: generierte, nicht versionierte `.blend`-/FBX-/GLB-Pakete, Bilder, QA und Manifeste.
- `outputs/`: historische Referenzpakete, Konzeptbilder und Shell-Einstiege als Kompatibilitätsrouten.
- [TECHNIK](docs/TECHNIK.md): Datenformat, Hände, Spiel-Export, Cache und Lehren aus Robogen; [CHANGELOG](CHANGELOG.md): Versionen.
- `work/`: historische Build-/Diagnoselogs, nicht der aktuelle Prüfstand.

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.
