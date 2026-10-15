## Autorenquellen und aktuelle Ausgabe

Die Generatorquellen liegen in `scripts/tool_assets/Taschenlampe/`.
Der gemeinsame Einstieg ist `python3 toolgen/generate_tools.py --tier full`; neue Pakete liegen in `output/`.
Die hier liegenden Dateien sind historische Referenzen.

# Cube Escape – Taschenlampe

Eigenständiges, deterministisch generiertes Blender-Asset nach Feld 06 der Konzepttafel. Die Konzeptform (kurzer zylindrischer Lampenkopf, nach unten geneigter Griff, gerichteter warmer Lichtstrahl) ist in die weiße/silbergraue Classic-Materialfamilie mit dunkler Mechanik, cyanblauen Statusanzeigen und sparsamen orangefarbenen Akzenten übertragen.

## Varianten und Dateien

- `CubeEscape_Flashlight.blend`, `.fbx`, `.glb`: kompaktes Hand-/Weltmodell.
- `CubeEscape_Flashlight_FPS.blend`, `.fbx`, `.glb`: separate 150-%-FPS-Version mit eingebackener Kameraposition und Einheits-Skalierungen.
- `preview_white.png`, `preview_first_person.png`, `preview_large.png`: Produkt-, Egoperspektiv- und freigestellte Ansichten.
- `view_side.png`, `view_front.png`, `view_top.png`: orthografische Prüfansichten.
- `create_flashlight.py`, `create_flashlight_fps.py`: lokale Blender-Generatoren.
- `verify_flashlight.py`: erneutes Öffnen und unabhängiger FBX-/GLB-Reimport.
- `flashlight_runtime_contract.json`: Vorschlag für den Lichtstrahl zur späteren Spielintegration.

Metermaßstab, Blender Z-up, lokale Geräteachse −Y. Der Handanker sitzt im Griff; `Socket_Muzzle` liegt auf der nach vorn gerichteten Mittelachse. `Socket_SupportHand` und `Socket_CenterOfMass` sind zusätzliche Montage-/Gameplay-Anker. FPS-Root und `Socket_Camera` liegen am Kameraursprung; Größe, Drehung und Offset sind eingerechnet. Beim Import keine zusätzliche Skalierung oder Position anwenden. FBX-/Unity-Achsen und Kameramontage im Zielprojekt abgleichen.

Die Blender-Datei enthält nur in der Präsentation Kamera, Studiolicht und Vorschauumgebung; Exporte enthalten Asset und Anker. Der warme Linsenkern ist sichtbare Emissionsgeometrie. Der tatsächliche gerichtete Lichtstrahl, Schatten, Toggle-Eingabe und das Sichtbarmachen versteckter Elemente sind **nicht** Spielintegration. `flashlight_runtime_contract.json` schlägt dafür einen Spotstrahler an `Socket_Muzzle` vor (12 m, 42°, warmweiß); diese Werte müssen im Spiel abgestimmt werden.

UVs verwenden deterministische per-face Boxprojektion mit überlappenden Inseln; es gibt keinen gepackten Textur-/Lightmap-Atlas. Keine Fremd-Assets oder Plugins.

## Build und Prüfungen

Mit Blender 5.2.2 LTS im Ordner ausführen:

```bash
bash build_cube_escape_assets.sh
```

Für eine andere Installation `BLENDER_BIN=/pfad/zu/Blender` setzen. Die Generatoren prüfen Mesh-Manifoldheit, Volumen, UVs, Materialzuweisung und Einheits-Skalierung. Der FPS-Build kontrolliert Clipping, freie Bildmitte und Ausrichtung des Lichtankers. Der Verifier öffnet die gespeicherten Blender-Dateien erneut und prüft FBX/GLB unabhängig auf Maße, Hierarchie, Anker, Materialslots und UVs. Prüfmarker bestätigen Asset-/Exportvalidierung, keine Abnahme in Unity oder im Spiel.
