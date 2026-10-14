# Toolgen

Toolgen ist ein Blender-basierter Generator für die 3D-Modelle der Cube-Escape-Werkzeuge. Die Architektur folgt den
bewährten Generatoren Robogen und Cubegen: ein reproduzierbarer Erzeugungskern, messbare Geometrie-QA, Exporte samt
Manifest und eine Mac-App als Oberfläche für denselben CLI-Prozess. Das Spielverhalten bleibt im Unity-Projekt.

## Orientierung an den Referenzgeneratoren

- [Robogen](https://github.com/ffunkfabian-hash/cubeescape-robogen) trennt Modellteile und Bauprozess von Export,
  automatisierter QA und Vorschauen. Toolgen übernimmt dieses Generator-/QA-/Export-Prinzip für einen ersten Werkzeugtyp.
- [Cubegen](https://github.com/ffunkfabian-hash/lowpoly_cubeescape_model_generatior) hat einen CLI-Backend-Prozess,
  den auch die native Mac-Oberfläche startet. Toolgen verwendet denselben Ansatz statt eine zweite Modelllogik in Swift
  oder einen reinen Contract-Viewer zu bauen.

## Aktueller Generator

Der erste vertikale Durchstich ist der Portal-Emitter:

```bash
python3 toolgen/build_toolset.py --tool portal_emitter
```

Toolgen sucht Blender über `TOOLGEN_BLENDER`, `PATH` oder den üblichen macOS-App-Pfad. Einen anderen Speicherort kann man
explizit angeben:

```bash
python3 toolgen/build_toolset.py \
  --tool portal_emitter \
  --blender "/Applications/Blender.app/Contents/MacOS/Blender" \
  --output "toolgen/output"
```

Das Ergebnis liegt unter `toolgen/output/portal_emitter/`:

- `PortalEmitter.blend`: editierbare Blender-Quelldatei
- `PortalEmitter.fbx`: Unity-Import
- `PortalEmitter.glb`: Austausch-/Laufzeitvorschau
- `PortalEmitter.obj` und `.mtl`: Modellansicht in der nativen Mac-App
- `preview.png`: reproduzierbarer Blender-Render
- `tool_contract.json`: Werkzeug- und Socket-Vertrag
- `qa_geometry.json`: Geometrieprüfungen am Quellmesh und FBX-Rundlauf (Objekte, Hierarchie, Maße, Sockets, Materialien)
- `manifest.json`: Version, kanonischer Mesh-Hash und SHA-256-Prüfsummen aller erzeugten Dateien

Der kanonische Mesh-Hash erfasst Vertices, Flächenorientierung und Materialnamen unabhängig von Export-Metadaten.
Blender speichert in FBX- und `.blend`-Containern zusätzlich native IDs, Zeitstempel und Quellpfade; deren Datei-Hashes
im Manifest dienen deshalb der Integritätsprüfung eines konkreten Pakets, nicht als Vergleich der Modellgeometrie
zwischen zwei Läufen. GLB, OBJ, MTL, Vorschau-Pixel, Vertrag und Messwerte werden bytegleich erzeugt.

Ein vorhandenes Paket wird standardmäßig nicht überschrieben. `--force` ersetzt es erst, nachdem die neue Ausgabe
vollständig erzeugt, geprüft und ihre Prüfsummen verifiziert wurden.

## Architektur

- `tool_contract.py`: Presets und Vertrag, den Unity und Generator gemeinsam nutzen.
- `build_toolset.py`: CLI, Blender-Auswahl, Staging, Exportprüfung und sichere Übernahme.
- `blender_worker.py`: Blender-Erzeugung, Export, Vorschau und gemessene Geometrie-QA.
- `mac_viewer/`: native Oberfläche. Sie startet `build_toolset.py`; sie enthält keine zweite Generatorlogik.

Nur `portal_emitter` ist bereits ein echter Generator. Die bestehenden Preset-Namen für weitere Werkzeuge sind noch
keine Implementierungen und werden deshalb nicht als fertige Assets ausgegeben.

## Unity-Vertrag

Der Portal-Emitter-Export behält den Unity-Namen `PortalEmitter` und den vom Spiel gesuchten `Muzzle`-Anker. Blender
verwendet Meter, Vorderseite −Y, oben +Z, Grip-Ursprung und getrennte, geschlossene Low-Poly-Teile. Gameplay,
ToolBelt und Portal-Logik werden nicht generiert.

Dieser Prototyp ergänzt die vorhandenen Generatoren unter `outputs/`; er ersetzt oder vereinheitlicht sie noch nicht.

## Mac-App

```bash
cd toolgen/mac_viewer
./build_viewer.sh
open .build/ToolGenViewer.app
```

Die App kann den Portal-Emitter generieren, die exportierte OBJ-Datei drehbar darstellen und Contract/QA/Prozessausgabe
anzeigen. Sie verwendet denselben Python-CLI- und Blender-Worker wie der Terminalaufruf.

## Prüfungen

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile toolgen/tool_contract.py toolgen/build_toolset.py toolgen/blender_worker.py
```
