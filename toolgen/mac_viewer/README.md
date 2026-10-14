# ToolGen Viewer für macOS

Die App ist die native Oberfläche für den Toolgen-Backend-Prozess, kein zweiter Generator. Sie bündelt die Python-CLI
und den Blender-Worker im App-Bundle und nutzt Blender sowie Python 3, die auf dem Mac installiert sind.

## Start

```bash
cd toolgen/mac_viewer
./build_viewer.sh
open .build/ToolGenViewer.app
```

In der App **Generate Portal Emitter** wählen. Sie startet dieselbe Blender-Pipeline wie der CLI-Aufruf, zeigt den
erzeugten OBJ-Export dreh- und zoombar an und lädt Contract, gemessene Geometrie-QA und Manifest in die Seitenleiste.
Standardmäßig landen Ergebnisse in `~/Documents/CubeEscapeToolgen/portal_emitter`. **Output folder…** ändert den
Ausgabeordner; **Open OBJ…** öffnet einen bestehenden Export.

Finder gestartete Apps erben nicht zwingend die Shell-Umgebung. Für abweichende Installationspfade können vor dem Start
`TOOLGEN_PYTHON`, `TOOLGEN_BLENDER` und `TOOLGEN_ROOT` gesetzt werden. Das App-Bundle enthält bereits den Python-Backend-
Code, `TOOLGEN_ROOT` ist daher nur für lokale Entwicklungsstarts oder externe Quellen nötig.

## Entwicklung

- `Package.swift`: Swift-Paket für die App
- `Sources/ToolGenViewerApp/main.swift`: App-Oberfläche, SceneKit-Ansicht und Prozessanbindung
- `build_viewer.sh`: baut das `.app`-Bundle und kopiert den gemeinsamen Python-Backend-Code in `Contents/Resources/toolgen`
