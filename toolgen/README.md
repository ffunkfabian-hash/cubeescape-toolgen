# Gemeinsame Toolgen-Pipeline

`python3 toolgen/generate_tools.py --tier quick|standard|full` erzeugt alle vierzehn ausgearbeiteten Werkzeuge (Portalkanone, Magnetgreifer, Taschenlampe, Bogen, die neun Waffen und seit 0.24 das Scout-Gewehr).
`--tool portal_emitter|magnet_gripper|flashlight|bow|pistol|assault_rifle|pulse_rifle|shotgun|sniper_rifle|smg|fusion_rifle|trace_rifle|rocket_launcher|scout_rifle` ist wiederholbar; `--output` wählt den Ordner, `--blender` ein Programm.
Frühere IDs (`tools.json` › `renamed_from`) nimmt `--tool` mit Warnung an, bis ein Werkzeug sie wieder trägt; `scout_rifle` (0.17–0.23 Alias des Spurgewehrs) ist seit 0.24 das Scout-Gewehr.
`build_toolset.py --tool <ID> [--output ...] [--force]` bleibt als Kompatibilitätseinstieg für Quick.
Der frühere einfache Portal-Worker und die zweite Viewer-Implementierung sind entfernt.

Die älteren Presets in `tool_contract.py` bleiben für Python-Aufrufer erhalten; ihre Zielmaße sind keine Messwerte der
aktuellen Modelle. Integration verwendet erzeugte `qa_geometry*.json`, `action_contract.json`,
`flashlight_runtime_contract.json` und die tatsächlichen Anker.

## Ablauf

1. Werkzeugkatalog, Blender-Version und Worker-Budget lesen; Ausgabe exklusiv sperren.
2. Stufenschlüssel und alle Manifest-Hashes prüfen; beschädigte Pakete sind keine Cache-Treffer.
3. Quellen in einen eigenen temporären Autor-Ordner kopieren; die Stufen aus `STAGES` nacheinander aus dem geteilten
   Stufen-Cache holen oder bauen: Welt, FPS, Aktionsanimation, Ego-Hände, Spiel-Export (Aktionsanimationen und Ego-QA inklusive).
4. Binäre SceneKit-Daten je Variante (Welt, FPS, Pfeil, Spielmodell) mit Morphs und gebackenen Transformationen exportieren und prüfen.
5. Standard/Voll: Blender, FBX und GLB unabhängig prüfen; Renderings und Aktions-GIFs erzeugen.
6. Nur erfolgreiche Pakete übernehmen, Manifest/Katalog aktualisieren. Bei Übernahmefehler vorheriges Paket wiederherstellen.

Bei Fehlern bleibt das vorherige Paket erhalten. Der aktuelle Bericht nennt `passed: false` und das Schrittlog.
`.toolgen-lock/owner.json` nennt den Besitzer; nur eine belegbar verwaiste Sperre darf entfernt werden.

## Ausgabe

Je Werkzeug `<Ausgabe>/<tool_id>/`: `.blend`, FBX, GLB, Geometrie-/Animations-QA und Verträge, `viewmodel_camera.json`,
`<Asset>_Game.*` mit `unity_contract.json` und `qa_game.json`, `<Asset>_FPS_Game.*` mit `unity_contract_fps.json` und `qa_game_fps.json`; bei Standard/Voll Reimport-QA, Bilder/GIFs. `ViewerData/<variant>/`: `scene.json`, `vertices.bin`, `indices.bin`, `anim.bin`, `qa_viewer.json`.
`manifest.json` sichert Dateien und Inhaltsschlüssel; `<Ausgabe>/catalog.json` führt die sichtbaren Modelle.

`logs/toolgen_report.json` misst Schritte, Worker, Threads, Last, Cache (Treffer, gebaute und gerenderte Stufen, Aufräumen)
und die Sperre. Das Zeitband vergleicht ruhige Läufe mit
identischer Maschine, Stufe, Werkzeugauswahl und Worker-Zahl; warme und kalte Caches bleiben getrennt.

[Bedienung und Voraussetzungen](../README.md) · [Technik](../docs/TECHNIK.md)

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.
