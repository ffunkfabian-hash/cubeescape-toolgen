# Cube Escape – Werkzeug-Generatoren

Deterministische Blender-Python-Generatoren für die Handwerkzeuge des Spiels Cube Escape, jeweils als kompaktes Weltmodell für den weißen Classic-Roboter und als 150-%-Version für die Egoperspektive.

- `outputs/<Werkzeug>/` – Generator, `.blend`, FBX, GLB, Renderings, QA-JSON, README und `build_cube_escape_assets.sh` je Werkzeug (Portalkanone, Magnetgreifer, Taschenlampe, Bogen). Der Bogen liefert zusätzlich den eigenständigen Standardpfeil; Magnetgreifer und Bogen haben eine einmalige Aktionsanimation (`action_contract.json`), die nur auf Aufruf läuft.
- `outputs/Referenzen/` – Konzeptbilder und Roboter-Stilreferenz.
- `outputs/Allgemeiner_Design_Prompt.md`, `outputs/Werkzeug_Prompts.md` – Designsprache, Materialwerte, Kamera- und Montagevertrag.
- `work/` – Build-Logs und Debug-Skripte.

Geprüftes Ziel: Blender 5.2.2 LTS, für die GIF-Vorschauen ImageMagick (`magick`). Build je Werkzeug mit `bash outputs/<Werkzeug>/build_cube_escape_assets.sh`, bei anderer Installation `BLENDER_BIN` setzen. Jeder Build erzeugt, animiert und prüft nur sein Werkzeug und schreibt `build_complete*.json`; die Taschenlampe benutzt die Helfer aus `Portalkanone/create_portal_gun.py`, der Bogen die eigenen aus `Bogen/bow_geometry.py`. Die Geometrie ist deterministisch: GLB und QA-JSON bleiben bei einem Neubau bis auf Fließkomma-Rauschen in der letzten Stelle gleich; `.blend`, FBX und Renderings tragen Zeitstempel und Render-Rauschen. Die Assets sind Blender-seitig validiert; Unity-Import, Kameramontage und Gameplay sind nicht im Spiel getestet.
