# Cube Escape – Toolgen

**0.2.0 · Slipforge.** Blender-Generator und nativer Mac-Viewer für die ausgearbeiteten Cube-Escape-Werkzeuge.
Oberfläche und Prüfablauf folgen [Robogen](https://github.com/ffunkfabian-hash/cubeescape-robogen): große 3D-Ansicht,
rechte Seitenleiste, Aktionssteuerung, Looks und Teststufen mit Cache. Gemeinsame Agentenregeln kommen aus
[ce-agent-tools](https://github.com/ffunkfabian-hash/ce-agent-tools).

## Start

Python 3, Blender 5.2.2 LTS, macOS 14+ und Xcode Command Line Tools; ImageMagick (`magick`) für GIFs und Bildtests.

```bash
python3 toolgen/generate_tools.py --tier quick
bash viewer/build.sh output/_quick
open output/_quick/ToolGenViewer.app
```

Die App bündelt den Katalog und zeigt die Portalkanone sofort an. Portalkanone, Magnetgreifer, Taschenlampe und Bogen
haben Welt- und FPS-Modelle, der Bogen zusätzlich einen separaten Pfeil. Die beiden Gehäuse sind schmaler und kürzer;
eine offene Zuführung legt Emitter und Greifkopf frei. Der Bogen hat schlankere Verkleidungen und eine offenere Silhouette.
Seine FPS-Haltung zeigt deutlich mehr Wurfarme und Sehne bei freier Bildmitte.

Orbit/Zoom, Iso/Front/Seite/Hinten/Ego, Drehteller, Boden und Anker helfen bei der Prüfung. „Ego“ lädt automatisch
das passende FPS-Modell, auch im A/B-Vergleich. Bogen und Magnetgreifer
spielen ihre Aktion auf Wunsch, mit Reset, Tempo und optionaler Prüfschleife. Materialfinish, Verkleidungsfarbe und
Leuchtstärke können verändert und als B-Vergleich gemerkt werden. Leertaste startet/pausiert; Cmd+O/Cmd+S laden/speichern
Looks, Cmd+Shift+S exportiert ein PNG.

„Werkzeug erzeugen“ startet dieselbe Pipeline wie die CLI. Ausgaben standardmäßig `~/Documents/CubeEscapeToolgen`,
änderbar im Viewer. Python und Blender müssen lokal installiert sein. `TOOLGEN_PYTHON`, `TOOLGEN_BLENDER` bzw.
`BLENDER_BIN` wählen Programme; `TOOLGEN_DATA` einen anderen Katalog. Die gebündelte Bibliothek bleibt beim Erzeugen verfügbar.

## Prüfungen

```bash
python3 -m unittest discover -s tests -v
python3 toolgen/generate_tools.py --tier standard
python3 toolgen/generate_tools.py --tier full
bash scripts/check_output.sh output
```

| Stufe | Ausgabe | Umfang |
|---|---|---|
| quick | `output/_quick` | Modelle, Animation, Geometrie-QA, Viewer-Daten; keine Bilder |
| standard | `output/_standard` | zusätzlich FBX-/GLB-Reimport und Bilder (12 Samples, 50 %) |
| full | `output` | dieselben Prüfungen, volle Bilder (40 Samples, 100 %) |

`--tool bow` grenzt einen Lauf ein. Ohne Änderung wiederholen: Cache-Treffer behalten alle geprüften Dateien.
`--no-cache` baut neu. Standardmäßig zwei Worker mit geteilter CPU-Kernzahl; `--workers`/`--threads` begrenzen die Last.
Bericht: `logs/toolgen_report.json` mit Schrittzeiten, Last, Cache und Zeitband. Schwere Last wird nicht bewertet.

Blender-QA prüft geschlossene Geometrie, Metermaße, Materialien, UVs, Anker, Hierarchie und Animation. Bogen und
Magnetgreifer haben je 97 Aktionsframes; der Bogen enthält Morphs und kehrt in die geladene Ruhepose zurück. Viewer-Tests
kontrollieren alle Varianten, Bewegung/Reset, Looks, beschädigte Daten und die Seitenleistenbreite.
Unity-Import, Kameramontage, Clip-Anbindung und Gameplay werden separat im Spiel abgenommen. Der unveränderte
Magnetgreifer-C#-Player enthält historische Kompilierungsnachweise, keine Unity-Laufzeitabnahme.

## Aufbau

- [AGENTS.md](AGENTS.md): Regeln und Plugins; [Test-Skill](.agents/skills/tg-testing/SKILL.md).
- `data/tools.json`: Katalog; `scripts/tool_assets/`: Autoren-Generatoren und gemeinsame Designprofile.
- `toolgen/`: gemeinsame Pipeline und Binärexport; [CLI-Details](toolgen/README.md).
- `viewer/`: SwiftUI-/SceneKit-App, universeller Build und Bildtests.
- `output/`: generierte, nicht versionierte `.blend`-/FBX-/GLB-Pakete, Bilder, QA und Manifeste.
- `outputs/`: historische Referenzpakete, Konzeptbilder und Shell-Einstiege als Kompatibilitätsrouten.
- [TECHNIK](docs/TECHNIK.md): Datenformat, Cache und Lehren aus Robogen; [CHANGELOG](CHANGELOG.md): Versionen.
- `work/`: historische Build-/Diagnoselogs, nicht der aktuelle Prüfstand.

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.
