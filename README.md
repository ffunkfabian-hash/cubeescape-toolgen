# Cube Escape – Werkzeug-Generatoren

Deterministische Blender-Python-Generatoren für die Handwerkzeuge des Spiels Cube Escape, jeweils als kompaktes Weltmodell für den weißen Classic-Roboter und als 150-%-Version für die Egoperspektive.

- `outputs/<Werkzeug>/` – Generator, `.blend`, FBX, GLB, Renderings, QA-JSON und `build_cube_escape_assets.sh` je Werkzeug (Portalkanone, Magnetgreifer, Taschenlampe, Bogen).
- `outputs/Referenzen/` – Konzeptbilder und Roboter-Stilreferenz.
- `outputs/Allgemeiner_Design_Prompt.md`, `outputs/Werkzeug_Prompts.md` – Designsprache, Materialwerte, Kamera- und Montagevertrag.
- `work/` – Build-Logs und Debug-Skripte.

Geprüftes Ziel: Blender 5.2.2 LTS. Build je Werkzeug mit `bash outputs/<Werkzeug>/build_cube_escape_assets.sh`, bei anderer Installation `BLENDER_BIN` setzen. Die Assets sind Blender-seitig validiert; Unity-Import, Kameramontage und Gameplay sind nicht im Spiel getestet.
