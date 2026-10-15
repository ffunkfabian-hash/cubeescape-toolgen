## Autorenquellen und aktuelle Ausgabe

Die Generatorquellen liegen in `scripts/tool_assets/Bogen/`.
Der gemeinsame Einstieg ist `python3 toolgen/generate_tools.py --tier full`; neue Pakete liegen in `output/`.
Die hier liegenden Dateien sind historische Referenzen.

# Bogen – Standardbogen und Standardpfeil

Aus dem Feld „Standard“ der Bogen-Konzepttafel (`Referenzen/Bogen_Konzept.png`) entwickelt, in der Formensprache der
übrigen Werkzeuge und des weißen Classic-Roboters: dunkler Griff mit Rippen, Riser mit weißen Verkleidungen, Steuermodul
mit cyanfarbenem Display, zwei gegliederte Wurfarme mit Gelenken, Rollen an den Spitzen und eine leuchtende Sehne. Im
Weltmodell liegt ein Standardpfeil auf der Sehne.

## Varianten

- `CubeEscape_Bow_Standard.blend`, `.fbx`, `.glb`: kompaktes Weltmodell für die Roboterhand mit aufgelegtem Pfeil.
- `CubeEscape_Bow_Standard_FPS.blend`, `.fbx`, `.glb`: separate große Egoperspektiv-Version mit gleichmäßig 150 %
  Geometriegröße, Skalierung aller Objekte 1 und Kameramontage-Root am Ursprung.
- `CubeEscape_Arrow_Standard.blend`, `.fbx`, `.glb`: eigenständiger Standardpfeil, Ursprung an der Nocke, Spitze bei
  `Socket_Tip` (0; −0,715; 0) m. Dieselbe Geometrie wie der aufgelegte Pfeil; gedacht als Projektil der Spielaktion.
- `preview_white.png`: Studioansicht des Weltmodells; `view_side.png`, `view_front.png`, `view_top.png`: orthografische
  Prüfansichten.
- `preview_first_person.png`: große Version in der abgestimmten tiefen Egoperspektiv-Haltung; `preview_large.png`:
  freigestellt.
- `preview_draw_once.gif`, `animation_frames/`: ein einzelner Durchlauf der Aktionsanimation.

Die FPS-Kamera entspricht der abgesenkten Portalkanone: Ursprung `(0,0,0)`, Blick −Y, Welt-Z oben, rechts im Bild liegt
auf −X, 75° horizontales Sichtfeld, 16:9, 1600 × 900, Near Clip 3 cm, Handanker bei `(-0,26; -0,66; -0,50)` m, der
Pfeil zielt auf `(0; -4; 0)` m. Weil der Bogen aufrecht gehalten wird, ragt der obere Wurfarm aus dem Bild und der
untere liegt unter dem Bildrand; die Bildmitte bleibt frei. Unity-Händigkeit, Importachsen und die Kameramontage müssen
im Spiel abgeglichen werden.

## Bauteil- und Montagevertrag

Kategorie **Interactive**; Tags `tool`, `bow`, `handheld`, `robot-classic`, `white-shell`, bei FPS zusätzlich
`first-person-large`. Metermaßstab, Schussrichtung −Y, Z oben. Das Weltmodell misst etwa 0,19 × 0,74 × 1,03 m
(Breite × Tiefe × Höhe, Pfeil eingeschlossen); genaue Maße und Bounds stehen in `qa_geometry*.json` und `qa_arrow.json`.

- `Socket_Hand` im Griffzentrum (Asset-Ursprung), `Socket_SupportHand` an der Sehne auf Nockhöhe (Zughand),
  `Socket_Nock` an der Nocke, `Socket_Muzzle` vor dem Riser auf der Pfeilachse, `Socket_ArrowTip` an der Spitze des
  aufgelegten Pfeils.
- `LoadedArrowPresence` › `ArrowCarrier` › Pfeilteile: der Carrier wandert beim Spannen mit der Nocke; `LoadedArrowPresence`
  blendet den Modellpfeil nach dem Abschuss über Skalierung 0,001 aus (Ruhewert 1), weil Sichtbarkeit nicht in
  FBX/glTF-Animationen exportiert wird.
- Wurfarme, Spitzenverkleidungen, Rollen, Armstatus-Leuchten und Sehnen tragen den Shape Key `Draw` (`bow_flex`): Basis =
  entspannt, 1 = voll gespannt. Die Sehne ist eine dünne Röhre, deren Enden an Rolle und Nocke gepinnt sind.
- Objektnamen enthalten keinen Punkt (Blender hängt `.001` an Duplikate; die Prüfskripte dulden genau diesen Suffix).

## Aktionsanimation – nur bei Anwendung

Beide Bogenvarianten enthalten den Ablauf `Bow_Use` (4 s bei 24 fps, Frames 1–97), **kein Autoplay, keine
Dauerschleife**; die Dateien sind in der geladenen Ruhepose gespeichert (`Idle_Loaded`):

- 0–1,25 s: Spannen – Shape Key `Draw` 0 → 1, Nocke, Carrier und Pfeilspitze wandern 0,23 m (FPS: 0,345 m) nach hinten.
- 1,25–1,75 s: Halten.
- 1,75–1,96 s: Lösen (Frame 43 = Abschussereignis, `release_event_seconds` in `action_contract.json`); ab Frame 44 ist
  der Modellpfeil ausgeblendet, der Spielcode spawnt den eigenständigen Pfeil an `Socket_ArrowTip`.
- 1,96–3,25 s: Nachschwingen und Nachladen; ab Frame 79 ist der Pfeil wieder sichtbar.
- 3,25–4 s: Ruhepose; ohne neuen Aktionsaufruf keine weitere Bewegung.

`qa_animation*.json` hält neun Referenzposen (Matrizen der Anker und Bounds der morphenden Meshes) fest, die der
Reimport nachrechnet. Kein Projektil, keine Physik, kein Spielcode: Der Abschuss ist ein Ereignis für die Spielaktion.

## Lokaler Build und Prüfung

Blender 5.2.2 LTS und ImageMagick (`magick`) für das GIF. Im Ordner ausführen:

```bash
bash build_cube_escape_assets.sh
```

Reihenfolge: `create_standard_bow.py` (Weltmodell und Pfeil, Helfer in `bow_geometry.py`) → `create_standard_bow_fps.py`
(leitet die große Variante aus der frischen Basisdatei ab) → `animate_standard_bow.py` (Animation beider Varianten,
Neu-Export, Frames) → `make_animation_preview.py` → `verify_standard_bow.py` für `world`, `fps` und `arrow`.

Die Prüfung kontrolliert geschlossene Meshes, positives Volumen, endliche Koordinaten, Materialslots, UV-Flächen,
Einheits-Skalierung und Polygonbudget; die Bewegung an allen 97 Frames (Sehne bleibt an der Nocke, Ruhepose am Ende, in
FPS freies Zielfeld und Near Clipping). Danach werden die drei nativen Dateien erneut geöffnet und FBX sowie GLB
unabhängig importiert: Meshzahl, Metermaße, Anker, Pfeilhierarchie, Shape Keys, Materialien, UVs und die Referenzposen
der Animation werden verglichen (`qa_roundtrip*.json`, `build_complete*.json`).
