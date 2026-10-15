# Toolgen – Technik und Prüfverträge

## Vorlage und Daten

Robogen liefert die Vorlage: SwiftUI + SceneKit, rechte Seitenleiste, universeller Compiler-Cache,
gebündelte Modelldaten, Screenshot-Einstiege, separater Playhead, Teststufen und gemeinsame Regeln aus ce-agent-tools.
Robogens roboterbezogene Skin-/Rig-Systeme werden nicht dupliziert.

Viewer-Format 1: Blender `(x,y,z)` → SceneKit `(x,z,−y)`, Meter, Y oben und Front +Z. Hierarchie und Anker bleiben erhalten.
`scene.json` enthält Nodes, Eltern, Restpose, Meshblöcke, Materialien, Morphs, Bounds, fps und Frames.
`vertices.bin`: little-endian float32, 8 Werte (Position 3, Normal 3, UV 2). `indices.bin`: uint32-Dreiecksindizes
relativ zum Meshblock. `anim.bin`: pro Frame/Node Position 3, Quaternion 4, Skalierung 3, danach Morph-Gewichte.
Morph-Ziele behalten die Originalvertex-Zuordnung und liegen als eigene Blöcke im Vertex-Puffer.

Materialdaten stammen aus Principled BSDF. Looks verändern Verkleidung, Finish und Leuchtstärke; Original stellt sie zurück.
Der Viewer prüft Version, Hierarchie/Zyklen, Puffergrößen, Indexgrenzen und endliche Werte. Im Ruhezustand kein Timer;
der Playhead aktualisiert nur die Zeitleiste. FPS: Kamera am Ursprung, Blick +Z, 75° horizontal, Near Clip 3 cm.
Der Knopf „Ego“ lädt vor dem Kamerawechsel die passende FPS-Variante, auch für einen gespeicherten B-Vergleich.
Andere Ansichten untersuchen die gewählte Variante; Werkzeugwechsel erhalten die FPS-Auswahl.
Modellversatz und 150-%-Geometrie sind im Asset gebacken. Der Bogen wird weiter vorne gehalten, um mehr Sehne und
Wurfarme zu zeigen; sein Pfeil zielt weiter zum gleichen Punkt.

## Cache und Worker

Schlüssel: Version/Schema, Werkzeugdaten, Stufe/Renderparameter, Blender-Version, Quellcode und Begleitverträge;
Taschenlampe zusätzlich Portalkanonen-Helfer. Alle Datei-Hashes werden bei Cache-Treffern geprüft. Compiler-Cache:
Swift-Quellen, Build-Skript, Architekturen und Compiler. Dateizeiten sind keine Cache-Schlüssel.

Jeder Worker hat einen isolierten Autor-Ordner, die Zusammenführung folgt der Katalogreihenfolge.
Render-Limits sind persistente Blender-Handler: `open_mainfile` darf Sample-/Thread-Vorgaben nicht entfernen.
Quick überspringt Bilder, prüft Geometrie und Bewegung. Standard/Full unterscheiden Präsentationsqualität, nicht QA.

Übernahme: altes Paket als Backup verschieben, neues übernehmen, bei Fehler altes wiederherstellen.
Ausgabe-Lock verhindert zwei Schreiber. Blender-/FBX-Container enthalten native Pfade/IDs/Metadaten; Datei-Hashes
prüfen Integrität. Der kanonische Viewer-Hash erfasst Geometrie, Animation und Materialien ohne Container-Metadaten.

## Gestaltung und Bogen-Fix

`design_profiles.py` komprimiert nur das Gehäuse beider Werkzeuge um einen festen Anker: Breite ×0,70, Länge ×0,64,
Höhe ×0,68. Emitter/Greifkopf, Griff und semantische Anker bleiben erhalten. Ein schlanker Zuführungskern mit zwei
freiliegenden Schienen verbindet Kopf und Gehäuse. Transformänderungen werden in Mesh-Koordinaten gebacken; Skalierung bleibt 1.

Der Bogen hat kleinere Riser-Verkleidungen, ein kompaktes Statusmodul und dünnere Wurfarme/Gelenke. Die offene,
lange mechanische Silhouette orientiert sich an futuristischen Bögen wie Destiny 2, bei eigener Cube-Escape-Formensprache.

Die alte Objektsuche schnitt Namen am ersten Punkt ab; Generatornamen mit Dezimalzahlen gingen dadurch verloren
(`StopIteration`). Der korrigierte Generator benutzt Millimeterzahlen, die Suche vollständige Namen und ausschließlich
numerische Blender-Suffixe. `Bow_Use`: 97 Frames bei 24 fps, Shape Key Draw für Wurfarme/Sehne, gemeinsam bewegte
Nocke/Carrier/Spitze. LoadedArrowPresence skaliert nach Release auf 0,001 und beim Nachladen zurück auf 1.
Der separate Pfeil ist ein Asset, kein simuliertes Projektil. QA prüft Kontakt/Anker/Ruhepose sowie FPS-Near-Clip
und freie Bildmitte über alle Frames; Reimport vergleicht Anker-Matrizen und Morph-Bounds an Referenzposen.

## Grenzen

Blender-Reimport und SceneKit-Bilder belegen keine Unity- oder Gameplay-Abnahme. Anker unter anderem Socket_Hand,
Socket_Muzzle, beim Bogen Socket_Nock/Socket_ArrowTip, beim Magnetgreifer Socket_Grab. Ältere Contract-Zielnamen
sind keine geprüfte Unity-Montage. Der unveränderte Magnetgreifer-Player behält seinen historischen Quellhash und die
Kompilierungsherkunft. Licht, Schussereignis, Projektil und Greifphysik werden beim Einbau separat geprüft.

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.

Die Pipeline erfasst die ASTs der Paketproduzenten `build`/`hash_file` über `PIPELINE_CACHE_FUNCTIONS`.
Render-/Autoren-/Exporterquellen werden vollständig erfasst; reine Berichtsänderungen lösen keinen Modell-Neubau aus.
Neue Paketschreib-Helfer gehören in diese Liste. Dieses Verhalten ist mit Cache-Regressionsfällen geprüft.
