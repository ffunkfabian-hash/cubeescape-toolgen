## Autorenquellen und aktuelle Ausgabe

Die Generatorquellen liegen in `scripts/tool_assets/Portalkanone/`.
Der gemeinsame Einstieg ist `python3 toolgen/generate_tools.py --tier full`; neue Pakete liegen in `output/`.
Die hier liegenden Dateien sind historische Referenzen.

# Portalkanone für Cube Escape

Es gibt zwei getrennte Varianten: das kompakte Weltmodell für den Roboter und eine **große Egoperspektiv-Version** mit 1,5-facher Geometriegröße. Beide verwenden dieselbe Designsprache und getrennte Bügel, Anzeigen und Leuchtteile.

## Große Version für die Egoperspektive

`CubeEscape_PortalGun_FPS.blend`, `.fbx` und `.glb` enthalten die große Kameravariante; `preview_first_person.png` zeigt sie bei **75° horizontalem Sichtfeld in 16:9**. `preview_large.png` zeigt sie freigestellt. Der Griff liegt in Blender bei `(-0,26; -0,66; -0,50)` m relativ zur Kamera, die Mündung zielt Richtung `(0; -4; 0)`. Die Haltung wurde auf Wunsch 10 cm abgesenkt, für eine tiefere Bildposition in Richtung Destiny 2. Größe und Kameraposition sind bereits in die Geometrie und Bauteilpositionen eingerechnet; sämtliche Objektskalierungen bleiben 1.

Der Root der FPS-Variante und `Socket_Camera` liegen am Kameraursprung. Die Kameramontage erfolgt über diesen Root; Größe und Versatz sind bereits eingerechnet. Blender-Kamera: Blickrichtung −Y, Z oben; aus Kamerasicht liegt die rechte Bildhälfte auf −X. Das Projektmapping `(x,z,-y)` würde den Griffversatz als `(-0,26; -0,50; 0,66)` m ausdrücken. Die tatsächliche Händigkeit, Blickrichtung und Root-Drehung im Unity-Import sind noch nicht im Spiel geprüft und müssen bei der Integration abgeglichen werden. Größe oder Versatz dabei nicht doppelt anwenden.

Das Modell nimmt den unteren rechten Bildbereich ein; das zentrale Zielfeld bleibt frei. Bei 75° wurde der Abstand aller Meshpunkte zur Kamera gegen eine Near-Clipping-Grenze von 3 cm geprüft. Am unteren Bildrand darf der Griff abgeschnitten werden, wie bei einem Viewmodel üblich. Die Hintergrund-Testgeometrie, Studiolichter und Kameras gehören ausschließlich zur Blender-Vorschau und sind von FBX/GLB ausgeschlossen. Hände, Wackeln, Schussanimation, Kamera-Layer und eine getrennte Viewmodel-Kamera sind noch nicht integriert. Größen- und Kamerawerte sind nachvollziehbare Startwerte für die erste Spielabnahme.

Der Generator `create_portal_gun_fps.py` leitet die FPS-Version aus der zuvor erzeugten Basisdatei ab. `qa_geometry_fps.json`, `qa_roundtrip_fps.json` und `build_complete_fps.json` enthalten ihre separaten Prüfnachweise. `bash build_cube_escape_assets.sh` erzeugt und prüft beide Varianten vollständig.

Aus dem Portal-Gun-Feld der bereitgestellten Konzepttafel abgeleitet: länglicher Korpus, dunkler hinterer Block mit Leuchtdisplay, kurze zylindrische Mündung, konzentrischer blauer Portalring und zwei offene Bügel. Zusätzlicher Griff unter dem hinteren Block. Weiße Verkleidungen und weich gerundete Kanten passen zum abgebildeten Roboter; kleine orange Statuslichter bleiben erhalten.

`preview_concept_colors.png` zeigt dieselbe Geometrie mit orangefarbenen Akzenten zum Vergleich mit der Konzepttafel. Die gespeicherte Blender-Datei und beide Exporte verwenden den weißen Look.

## Dateien und Verwendung

- `CubeEscape_PortalGun.blend`: bearbeitbares Modell, getrennte Bauteile, Vorschaukamera und Studiolicht.
- `CubeEscape_PortalGun.fbx`: sichtbare Geometrie und Anker für Unity.
- `CubeEscape_PortalGun.glb`: PBR-Materialien einschließlich Emission für glTF-kompatible Anwendungen.
- `create_portal_gun.py`: vollständiger lokaler Generator ohne Zusatzpakete oder externe Assets.
- `verify_portal_gun.py`: eigenständige Prüfung der gespeicherten Datei und Reimport beider Formate.
- `qa_geometry.json`, `qa_roundtrip.json`, `build_complete.json`: Prüfergebnisse dieses Builds.

Kategorie **Interactive**. Tags: tool, portal, handheld, robot-classic, white-shell. Geometrie und Größen stehen in `qa_geometry.json`; etwa 60,6 cm lang, 22,6 cm breit und 35,1 cm hoch einschließlich Griff und Bügeln. Das ist eine erste Designgröße, keine bereits im Spiel erprobte Handmontage.

Blender: Meter, Z oben, Schussrichtung −Y. Root am Geräteursprung, Skalierung überall 1. `Socket_Hand` liegt im Griffzentrum, `Socket_Muzzle` an der Mündung und `Socket_SupportHand` unter dem Korpus. Für eine Handmontage den Handanker benutzen, nicht die Mitte der Bounding Box. `Pivot_Upper` und `Pivot_Lower` besitzen eigene Bügelhierarchien. Leuchtteile und Anzeigen bleiben separate Meshes. Die Bügel sind für spätere Bewegung vorbereitet, aber nicht animiert.

UVs sind deterministische Boxprojektionen mit absichtlich überlappenden Inseln für Materialflächen. Kein einmalig gepacktes Textur- oder Lightmap-Atlas. Materialien sind einfarbige Principled-PBR-Materialien; keine generierten Bildtexturen notwendig. Die Farbwerte orientieren sich an der Palette `Classic` des lokalen Roboter-Generators. FBX überträgt Emission je nach Zielanwendung unterschiedlich; in Unity passende Materialien zuweisen und Bloom aktivieren, wenn ein Halo gewünscht ist.

Eigenständiges visuelles Asset: noch kein Unity-Prefab, keine Portalplatzierung, Teleportation oder Kollision. Der bestehende Environment-Kit-Importer und der Roboter-Viewer wurden nicht erweitert. Der Kategorien-/Montagevertrag ist eine Dokumentation für die spätere Integration, keine zusätzliche produktive Registry. Keine URP-/HDRP-Darstellung geprüft.

## Erneut erzeugen

Blender 5.2.2 LTS ist das geprüfte Ziel. Im Ordner ausführen:

```bash
bash build_cube_escape_assets.sh
```

Bei anderer Installation `BLENDER_BIN=/pfad/zu/Blender` setzen. Der Build erstellt ausschließlich diese Portalkanone. Er ersetzt nur seine eigene Blender-Szene; vorhandene andere Szenen bleiben bei interaktiver Ausführung erhalten. CLI-Ausführung verwendet eine eigene Hintergrundinstanz.

Die Prüfung kontrolliert geschlossene Meshes, positives Volumen, endliche Koordinaten, Materialslots, nicht degenerierte UVs, Einheits-Skalierung und das Polygonbudget. Danach werden die native Datei erneut geöffnet und FBX sowie GLB unabhängig importiert: Meshzahl, Metermaße, Anker, Bügelhierarchien, Materialbindungen und UVs werden verglichen. Vorschauen wurden visuell kontrolliert. Ein fehlerfreier Marker bestätigt den Asset-Build, keine Gameplay-Abnahme.
