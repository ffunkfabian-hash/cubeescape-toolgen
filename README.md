# Cube Escape – Werkzeug-Generatoren

Deterministische Blender-Python-Generatoren für die Handwerkzeuge des Spiels Cube Escape, jeweils als kompaktes Weltmodell für den weißen Classic-Roboter und als 150-%-Version für die Egoperspektive.

- `outputs/<Werkzeug>/` – Generator, `.blend`, FBX, GLB, Renderings, QA-JSON und `build_cube_escape_assets.sh` je Werkzeug (Portalkanone, Magnetgreifer, Taschenlampe, Bogen).
- `outputs/Referenzen/` – Konzeptbilder und Roboter-Stilreferenz.
- `outputs/Allgemeiner_Design_Prompt.md`, `outputs/Werkzeug_Prompts.md` – Designsprache, Materialwerte, Kamera- und Montagevertrag.
- `work/` – Build-Logs und Debug-Skripte.

Geprüftes Ziel: Blender 5.2.2 LTS. Build je Werkzeug mit `bash outputs/<Werkzeug>/build_cube_escape_assets.sh`, bei anderer Installation `BLENDER_BIN` setzen. Die Assets sind Blender-seitig validiert; Unity-Import, Kameramontage und Gameplay sind nicht im Spiel getestet.

## Toolgen-CLI und Mac-Viewer

`toolgen/` enthält zusätzlich einen gemeinsamen CLI-/Blender-Prototyp und eine native macOS-App. Die bestehenden
Werkzeug-Generatoren und ihre Exporte unter `outputs/` bleiben eigenständig und unverändert. Der Prototyp erzeugt
derzeit ausschließlich einen Portal-Emitter, prüft den FBX-Rundlauf und stellt den OBJ-Export in SceneKit dar.

```bash
python3 toolgen/build_toolset.py --tool portal_emitter
cd toolgen/mac_viewer
./build_viewer.sh
open .build/ToolGenViewer.app
```

Voraussetzungen sind Python 3, Blender 5.2.2 LTS und macOS 14 oder neuer für die App. Details, QA-Grenzen und Tests:
[`toolgen/README.md`](toolgen/README.md).
