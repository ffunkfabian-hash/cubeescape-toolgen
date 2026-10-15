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
der Playhead aktualisiert nur die Zeitleiste. FPS: Kamera am Ursprung, Blick +Z, Sichtfeld vertikal 46,69°
(Datenwert, siehe Viewmodel-Sichtfeld), Near Clip 3 cm. Die Variante „Spielmodell“ (`game`) erscheint, wenn der Katalog sie
enthält; ohne sie arbeitet der Viewer unverändert.
Der Knopf „Ego“ lädt vor dem Kamerawechsel die passende FPS-Variante, auch für einen gespeicherten B-Vergleich.
Die Ego-Ansicht behält in App, A/B-Vergleich und Screenshot immer 16:9; freie Ränder füllen den restlichen Platz.
So zeigt ein hohes App-Fenster nicht plötzlich mehr Arm als die geprüfte Vorschau.
Andere Ansichten untersuchen die gewählte Variante; Werkzeugwechsel erhalten die FPS-Auswahl.
Modellversatz und Werkzeuggröße sind im Asset gebacken; `tool_scale` passt die ursprünglich 150-%-FPS-Geometrie
je Werkzeug an. `first_person.py` setzt nach dem Autorenclip die
Haltung aus `data/viewmodels.json`, löst die tatsächliche Mündungsachse auf das Ziel und ergänzt die Handbaugruppe.
`Viewmodel_Hold` trägt die statische Haltung, `Viewmodel_Motion` die gebackene Sekundärbewegung. Der Kamerasockel
und der Exportroot bleiben am Ursprung. Weltmodelle enthalten keine Ego-Arme.

## Hände und Bewegungsgefühl

Robogens Mitt-Stil (`scripts/robogen/body.py`, `rig.py`, Revision/Quellhashes in `data/viewmodels.json`) liefert
die Formensprache: dunkle Gelenke, Daumen und weiße Verkleidung. Jede Ego-Hand hat wie Robogens Mitt
**drei Greiffinger und einen gegenüberliegenden Daumen** (`GRIPPING_FINGERS = 3`; die Zughand des Bogens bildet einen
flachen Haken aus drei Fingern). Die Finger mit ihren starren Gliedern werden hier erzeugt.
`Hand_L/R`, `Fingers_*`, `Thumb_L/R`, `LowerArm_L/R` sowie
`GripContact_L/R` sind exportierte Knoten, keine Kopie des vollständigen Robogen-Skeletts oder dessen Clips.
Robogen muss zur Generierung nicht installiert sein; sein Repository bleibt unverändert.
Der untere linke Ego-Ausschnitt des Bogenkonzepts bestimmt die Verkleidung: weiße Handrückenplatten, orange
Einlagen, dunkle Gelenkspalte, Schrauben und konische Unterarmschalen. Einlagen und Schrauben folgen der
geneigten Schalenfläche und sitzen auf ihr. Die gemeinsamen Kontakt-/Gelenk-IDs bleiben davon unabhängig.

**Verbindlicher Ego-Bildausschnitt:** Hände vollständig zeigen, von den Unterarmen höchstens die griffseitige
Hälfte. Oberarme, Ellenbogenräder und Schulterpanzer gehören nicht in das Ego-Mesh. Der Bogen bleibt das
Hauptmotiv; seine Größe, Neigung und Halteposition werden zusammen mit den Händen abgestimmt. Genau drei
gegliederte Greiffinger und ein Daumen müssen pro Hand erkennbar sein (`finger_count_per_hand` 4, `gripping_fingers_per_hand` 3,
`thumb_count_per_hand` 1). Fingerglieder sind keine zusätzlichen Finger. Keine kastenförmige Ersatzhand oder durchgehende
Stange als Arm.

Jeder Arm hat die starren Rig-Knoten `UpperArm_*` → `LowerArm_*`. Ihre Längen und Schulterpositionen sind feste
Maße unter `arm` in `data/viewmodels.json`; sie werden niemals aus dem Abstand zum Werkzeug verlängert. Ein Werkzeug
kann die Schulterpositionen mit `shoulders` überschreiben (derzeit nutzt keines davon Gebrauch).
Der analytische Zwei-Glied-IK in `solve_elbow()` hält diese Maße und den Griffkontakt konstant. Unreichbare Ziele
brechen den Bau ab. Die Lösung wird pro Frame gebacken; der Viewer braucht keinen IK-Solver. Die QA misst
Gelenkkontakt und Gliedlänge an allen Frames (`max_arm_link_error_m`), der Reimport prüft beide Rig-Knoten mit.
Nur der Unterarm wird als zusammenhängendes Mesh bis zum außerhalb des Bildes liegenden Ellenbogen gebaut:
Schale, dunkler Kern und Servos reichen über den unteren Bildrand hinaus. Das Mesh an der halben Länge abzuschneiden
verursacht sichtbare Schnittkanten und ist kein Ersatz für korrektes Framing. Die griffseitige Hälfte darf ins
Bild; die Ellenbogenhälfte samt Abschluss muss über den gesamten Clip außerhalb liegen. Eine konservative Hüllbox
um die proximale Hälfte prüft dies an jedem Frame (`proximal_forearm_max_screen_y < 0`), einschließlich Flächen,
die den Bildrand überqueren, obwohl ihre Eckpunkte außerhalb liegen. Geometrie, Handdrehung
und Bildausschnitt immer gemeinsam in Ruhe, gespannt, nach dem Schuss und beim Nachgreifen ansehen.

Die Handfläche liegt in der lokalen Y/Z-Ebene: Finger zeigen nach −Y, die Reihe der beiden Finger liegt entlang Z.
Die Handwurzel sitzt daher hinter der Handfläche bei +Y, mittig in X und Z (`arm.wrist_offset_m`), nicht unter dem
kleinen Finger bei −Z. Kugel-/Drehgelenk, Handwurzel und Unterarm treffen sich in diesem Punkt. Die QA misst dies am tatsächlichen
Palm-/Gelenk-Mesh (`centered_wrist_max_error_m`).

Haltungsdaten je Werkzeug (`tools` in `data/viewmodels.json`): `hand`, `roll_degrees`, `tool_scale`, `grip_radius`,
`support_offset` und `support_roll_degrees` für die Stützhand, `aim_target_m` (Zielpunkt, auf den die Mündungsachse zeigt;
ohne Angabe 4 m geradeaus) sowie `head` (Anker und Teile des Werkzeugkopfs für die Kopfprüfung). Die Stützhand dreht sich
um den Lauf, damit ihre Finger den Werkzeugkopf freilassen.

Der Bogen verwendet ein eigenes `tool_scale`, `hand_rotation_degrees` und `draw_roll_degrees`. Skalierung wird in
Mesh-, Morph- und Translationsdaten gebacken, die Objekt-Skalierung bleibt 1. Handdrehungen erfolgen um den
Griffkontakt; sie dürfen weder Griff noch Nocke versetzen. Linke Handfläche/Handgelenk liegen auf der linken
Seite des Griffs, die rechte Zughand auf der rechten Seite der Nocke. Eine Drehung um 180° nur zum Sichtbarmachen
der Finger vertauscht diese Seiten und ist falsch. Die Zughand gleicht die Bogenschräglage aus, statt mit einem
verdrehten Handgelenk die volle Werkzeugrotation zu übernehmen. `min_hand_side_clearance_m` prüft die
korrekte Handgelenkseite an jedem Frame und verwirft die frühere verdrehte Haltung. Die Zugfinger bilden einen
flachen, dreigliedrigen Haken an der Sehne; sie übernehmen nicht die tiefe Umschlingung eines Werkzeuggriffs.
Änderungen am FPS-Bogen ändern das Weltmodell nicht.

### Viewmodel-Sichtfeld und Ego-QA

Hände und Werkzeug werden im Spiel mit einer eigenen Kamera gezeichnet. Ihr Sichtfeld steht unter `camera` in
`data/viewmodels.json`: vertikal 46,69° (Unitys `Camera.fieldOfView`), das entspricht dem früheren 75° horizontal bei 16:9;
`first_person.py` prüft beim Laden, dass beide Werte zusammenpassen. Ein Werkzeug darf `vertical_fov_degrees` überschreiben.
In Unity gehört der Wert in ein eigenes Viewmodel-FOV (zum Beispiel ein URP-Render-Objects-Kameraüberschreiben auf der
Viewmodel-Ebene); das Sichtfeld der Spielwelt bleibt eine Spielereinstellung. Jedes Ego-Paket nennt den Wert in
`viewmodel_camera.json` (vertikal, horizontal je Seitenverhältnis, Near Clip, Unity-Hinweis, geprüfter Bereich) und an der
Wurzel in den Eigenschaften `ce_viewmodel_vertical_fov_degrees`, `ce_viewmodel_horizontal_fov_degrees`,
`ce_viewmodel_reference_aspect` und `ce_viewmodel_near_clip_m`; der Reimport vergleicht den vertikalen Wert mit der QA.

Die Ego-Vorschau und die QA projizieren dieselbe Kamera (die Prüfung vergleicht beide an Stichpunkten). Verbindlich ist die
QA beim eingestellten Sichtfeld für 16:9 und 16:10: Hände im Bild (Rand `hand_margin`), Zielpunkt frei, proximaler Unterarm
außerhalb. Der Bereich um den Wert herum (±8° in fünf Stufen) wird gemessen und in `fov_range` berichtet, ohne den Lauf zu
verwerfen. Die Bogen-Zughand muss nur in Ruhe im Bild liegen; Griff- und Stützhand bleiben über den ganzen Clip im Bild.

Die Kopfprüfung (`head`, nicht für den Bogen) belegt, dass der Werkzeugkopf unverdeckt zu sehen ist: Ankerrand, Anteil des
unverdeckten Kopfs auf dem Bildschirm (Grenze 0,5) und Bildschirmanteil. Gemessen: Portalkanone 63 %, Magnetgreifer 74 %,
Taschenlampe 56 % unverdeckt. Die Ego-Modelle sind deterministisch: `create_uvsphere` der Handgelenkkugel lieferte
dieselben Flächen in wechselnder Reihenfolge, `ball()` sortiert sie jetzt kanonisch. Diese Ego-Ansicht soll künftig die
Ego-Sicht in Cube Escape werden.

### Bewegungen und Wiedergabe

Referenz für Ruhehaltung und Aktionsphasen: [Destiny-2-Bogenvideo](https://www.youtube.com/watch?v=wKaneSqfzo4).
Die linke Bogenhand bleibt am Griff, die rechte an der Nocke bis zum Lösen (Frame 43), bewegt sich zum Nachgreifen
nach unten und liegt ab Frame 79 wieder an. Bogen und linke Griffhand folgen gemeinsam einer Bewegung um den Griff: beim Spannen richtet sich der Bogen auf,
beim Schuss federt er zurück. Die Nocke und rechte Hand folgen anschließend demselben bewegten Bezugssystem.
Die QA verlangt am tatsächlichen Griffanker beim Spannen mindestens 2 cm Ortsänderung und 5° Drehung; der
Griffkontakt bleibt dabei erhalten. Dadurch wird ein nur an der Sehne bewegter, sonst statischer Bogen verworfen.
Minimum-Jerk-Kurven (Quintik mit verschwindender Anfangs-/Endgeschwindigkeit)
und endliches Nachfedern stehen in `motion_profiles.py`. Greifer-Kurven verwenden geklemmte Bézier-Handles.
Die bestehenden Clipnamen, 97 Frames und Abschuss-/Sichtbarkeitsereignisse bleiben erhalten.
Portal-/Lampen-Egomodelle bieten eigene Anwendungsvorschauen; daraus entstehen keine Gameplay-Ereignisse.

Der Viewer blendet pro Zeitposition zwischen zwei gebackenen Frames: linear für Position/Skalierung/Morphs, Slerp
für Quaternionen. Diskrete Skalierung (Pfeilsichtbarkeit) bleibt durch `stepScale` im Knoten ein Ereignis;
der Pfeil schrumpft beim Zwischenbild-Blenden nicht. Aktive Wiedergabe und Darstellung laufen mit 60 Hz,
der Ruhemodus benötigt weiterhin keinen Timer. `qa_viewmodel.json` prüft alle Frames auf Kontakt,
Near Clip, freie Bildmitte, den unsichtbaren proximalen Unterarm und Ende = Anfang; `qa_viewmodel_roundtrip.json`
vergleicht unabhängige Reimporte an neun Posen.
Hand- und Haltungsquellen gehören zum Paketcache. Die Bilder und QA der alten Referenzpakete unter `outputs/`
beschreiben weiterhin deren historischen Stand.
Der CLI-Einstieg `--sequence <Bildordner> --model bow/fps --rate 60` rendert die tatsächliche Viewer-Wiedergabe
als 960×540-PNG-Folge für Bewegungsabnahmen. Daraus entsteht mit FFmpeg ein teilbares MP4:

```bash
output/ToolGenViewer.app/Contents/MacOS/ToolGenViewer --data output --sequence output/QA/Bogen-Frames --model bow/fps --rate 60
ffmpeg -framerate 60 -i output/QA/Bogen-Frames/frame-%04d.png -c:v libx264 -crf 18 -pix_fmt yuv420p -movflags +faststart output/QA/Bogen.mp4
```

Neue Vorschauen immer mit `--data` auf den frisch geprüften Katalog richten. Eine ältere App kann sonst ihre
gebündelten alten Modelle rendern. Nach einem fehlgeschlagenen Bau ist das vorherige Paket weiterhin intakt,
belegt aber keine neue Änderung. Movie mit `ffprobe` auf Bildrate, Auflösung und Framezahl prüfen und mindestens
Ruhe, Zug, Schuss und Nachgreifen aus der tatsächlichen Sequenz ansehen.

## Spiel-Export

Die Stufe `game` (`toolgen/game_export.py`, Eintrag in `STAGES`) macht aus dem Weltmodell ein Modell für Unity 6 (URP).
Sie liest `<Asset>.blend` und `data/game_palette.json` und schreibt `<Asset>_Game.blend/.fbx/.glb`, `unity_contract.json`
und `qa_game.json` (in Render-Stufen zusätzlich `preview_game.png`: Weltmodell, LOD0, LOD1 und Kollisionsboxen nebeneinander).
Der Viewer zeigt das Ergebnis als Variante „Spielmodell“ (Datei `<Asset>_Game`, Wurzelobjekt `<Asset>`, Clip des Weltmodells; nur LOD0 – `export_viewer.py` lässt `_LOD1…`-Teile aus). Das Weltmodell
und die Ego-Modelle bleiben unverändert.

**Renderer.** Alle statischen Teile werden zu einem Mesh mit Materialslots verbunden (`<Asset>_Static_LOD0`). Getrennt bleiben
nur Teile unter einem animierten Objekt (je Besitzer ein Renderer, zum Beispiel `…Jaw…_Mesh_LOD0` beim Greifer) und Meshes mit
Shape Keys (je Elternteil und gleiche Key-Animation, `…_Morph_LOD0`, beim Bogen). Höchstens vier Renderer je Werkzeug.
Jeder Empty, auch jedes `Socket_*`, behält Elternteil und Weltmatrix; Clipname, Länge und Ereignisbilder bleiben gleich.
Der Greifer-Clip `MG_Apply` heißt im Export `MagnetGripper_Use` (der Vertrag nennt beide Namen). Ein Mesh mit eigener Objektanimation
ist nicht zulässig (der Export bricht ab: Empty animieren).

**Materialien.** `data/game_palette.json` bildet jedes Quellmaterial (`PG_`/`MG_`/`BW_`-Präfix des Generators, `FPS_Robot_*`)
auf ein Material mit dem Namen eines Cube-Escape-Materials ab: `M_RobotBody`, `M_RobotDark`, `M_Metal`, `M_HazardOrange`,
`M_GlowCyan`, `M_GlowOrange` (Farbwerte in sRGB aus Cube Escapes `generate_assets.py`). Die Abbildung muss vollständig sein; ein
unbekanntes Quellmaterial bricht den Export ab. Matt wie Station und Spielerroboter: Nicht-Leuchtmaterialien Metallic höchstens 0,35 und
Roughness mindestens 0,55 (Prüfgrenze `finish` in der Palettendatei), nur `M_Glow*` leuchtet.
Höchstens sechs Materialien je Werkzeug; tatsächlich sind es fünf.

**LOD und Kollision.** Jeder Renderer hat ein Geschwister `<Teil>_LOD1` mit etwa 30 % der Dreiecke (Prüfbereich 25–40 %, Silhouette
innerhalb 2 % der Teildiagonale, gleiche Materialien und Shape Keys); die Namen folgen der Cubegen-Konvention, aus der
Unity beim FBX-Import eine LODGroup baut. Kollisionsboxen werden am tatsächlichen LOD0-Mesh gefittet (konvexe Hülle,
orientierte Boxen, Zusammenführen solange die Box mindestens halb gefüllt bleibt; höchstens 6 am Wurzelobjekt und 3 je beweglichem Teil)
und stehen in `unity_contract.json` › `colliders` im Feldformat des Cubegen-Sidecars (`type`, `center`, `size`, `rotation`, Unity-Achsen,
relativ zum Teil). Leuchtteile, Kleinteile unter 12 mm und der geladene Pfeil (sichtbarkeitsanimiert) bekommen keine Box. Die Öffnungen (Mündung,
Greifraum, beim Bogen der Raum zwischen Griff und Nocke) werden mit Testpunkten auf Freiheit geprüft; eine Gesamtbox, die sie blockiert, fällt durch.

**Achsen.** Blender (Z oben, vorn −Y) wird zu Unity (Y oben, vorn +Z) mit Position `(−x, z, −y)`. FBX: `axis_forward −Z`,
`axis_up Y`, ohne `bake_space_transform` (das bricht Objektanimation). In Unity den FBX-Import mit `bakeAxisConversion`
einstellen; der Vertrag (`axes.fbx.unity_import`) nennt das. GLB (+Y oben) ergibt über Unitys X-Spiegelung dieselbe Abbildung.

**Vertrag.** `unity_contract.json` enthält Renderer (Rolle, LOD, Materialien, Dreiecke, Blend Shapes, `MeshRenderer` oder
`SkinnedMeshRenderer`), Anker und Knoten mit lokaler Blender- und Unity-Transformation, Palette, LOD-Gruppen, Kollisionsboxen,
Clip mit Ereignissen, Quellhashes (Weltmodell, Palette) und Hashes der drei Dateien.

**QA** (`qa_game.json`, Pflicht im Paketmanifest `required_qa`): `palette`, `renderers_in_target`, `materials_in_target`,
`bounds_lod0` (LOD0 gegen das Weltmodell in jedem Clipbild, 1 mm), `anchors_identical`, `clip_blend`, `lod1`, `collision` sowie
`roundtrip_glb` und `roundtrip_fbx` (frischer Import: Namen, Materialslots, Clip, Anker- und Teilgrenzen an neun Bildern, 2 mm).

| Werkzeug | Renderer | Dreiecke LOD0 / LOD1 | Boxen |
|---|---|---|---|
| Portalkanone | 1 | 32 468 / 9 740 | 4 |
| Magnetgreifer | 3 | 25 928 / 7 774 | 7 |
| Taschenlampe | 1 | 10 628 / 3 188 | 2 |
| Bogen | 3 | 12 036 / 3 610 | 6 |

Offen bleibt der Einbau in Unity (siehe Grenzen).

## Cache und Worker

**Stufen.** Die Liste `STAGES` in `generate_tools.py` beschreibt die Bauschritte jedes Werkzeugs deklarativ (Skript, Läufer
Blender oder Python, Argumente, gelesene Dateien, zusätzliche Quellen, Bilder ja/nein, Stufen, QA-Dateien, Viewer-Varianten):
Welt, FPS, Animation, Animations-GIF, Ego-Hände, Ego-Reimport, Spiel-Export; dazu je Viewer-Variante ein Export und in
Standard/Voll die Reimport-Prüfungen. Eine neue Stufe ist ein Eintrag; Manifest, Cache und Viewer-Variante folgen daraus.

**Schlüssel.** Jede Stufe hat einen Inhaltsschlüssel aus: Stufendeklaration, Werkzeugeintrag, Blender-Version, Fingerabdruck der
laufbestimmenden Pipelinefunktionen (`STAGE_CACHE_FUNCTIONS`), dem Hash ihres Skripts samt allem, was es importiert oder
beim Namen nennt (Quellen-Closure), den Hashes der gelesenen Vorstufen-Dateien und bei Bildern Samples, Prozent und Gerät.
Dateizeiten und Pfade sind nie Teil des Schlüssels. Stufen lesen standardmäßig keine Bilder früherer Stufen; Geometrie
und Bilder werden getrennt gespeichert, so teilen quick, standard und full dieselbe Geometrie und rendern nur die Bilder.
Eine Änderung nur an `first_person.py` baut in quick nur `first_person` und `viewer_fps` neu, in standard/full zusätzlich die
Reimport-Prüfungen, die deren Dateien lesen.
Das Paket (`manifest.json`) trägt die Stufenschlüssel; ein installiertes Paket mit passendem Schlüssel und gültigen Hashes
ist ein Paket-Treffer („CACHE_HIT“) und wird nicht angefasst.

**Geteilter Speicher** (`toolgen/toolcache.py`): `~/Library/Caches/CubeEscapeToolgen/cache` (`$XDG_CACHE_HOME/…` außerhalb von
macOS), umstellbar mit `TOOLGEN_CACHE`; Grenze `TOOLGEN_CACHE_LIMIT_GB` (Standard 4). Hauptcheckout, Worktrees und jede Ausgabe
teilen ihn, ein frischer Ausgabeordner ist sofort warm. Regeln (wie bei Robogen): Einträge entstehen atomar unter Temp-Namen
und werden in einem Schritt umbenannt, zwei Schreiber desselben Schlüssels speichern genau einmal; Kopien sind APFS-Klone;
jeder Treffer prüft die Datei-Hashes vor dem Ersetzen, ein beschädigter Eintrag wird verworfen und zählt als Fehlschlag;
`prune()` entfernt nach der letzten Nutzung die ältesten Einträge über der Grenze, nie einen Eintrag der letzten zwei Stunden
(Schonfrist) und veraltete Temp-Ordner nach 24 Stunden. Ein neuerer Eintrag löscht keinen älteren.
Gemessen am 15.10.2026: frischer Ausgabeordner `standard` 0,48 s (46 Stufen aus dem Cache) gegenüber 157 s kalt in 0.3.0; zweiter
`quick` 0,21 s. Der Bericht `logs/toolgen_report.json` nennt je Stufe Treffer, Bau oder Rendern, Dauer und Log.

**Sperre.** Der Lauf `--tier full` und `scripts/check_output.sh` laufen nacheinander mit Robogen, Cube Escape und Cubegen
(`scripts/heavy_lock.py`, Sperrdatei `~/Library/Caches/CubeEscape/heavy-run.lock`, Besitzer als JSON-Zeile, `CE_HEAVY_LOCK=0`
überspringt, `CE_HEAVY_HELD=1` kennzeichnet Kindprozesse des Halters). Der Vertrag ist eine Kopie von Robogens Skript und wird nur
gemeinsam geändert. Der Bericht nennt den Zustand unter `heavy_lock`. `scripts/testplan.py` ordnet geänderte Dateien Bereichen zu
(Doku, Daten, Generator, Pipeline/Cache, Viewer, Tests), nennt den kleinsten Prüfweg samt Zeitschätzung und die betroffenen
Werkzeuge aus der Quellen-Closure; `--run` führt ihn aus.

**Worker.** Jeder Worker arbeitet in einer isolierten Kopie der Autorenskripte, die Zusammenführung folgt der Katalogreihenfolge.
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
Der Spiel-Export (Renderer, LODGroup, Kollision, Clip, Materialien) und die Ego-Kamera sind in Blender, GLB und FBX geprüft,
aber noch nicht in Unity abgenommen. Die Taschenlampen-Linse ist im Spielexport `M_GlowOrange` und damit kräftiger als das warme
Weiß des Weltmodells. Die Cube-Escape-Materialien gleichen Namens sind glänzender als die Palette; was gilt, wird beim Import
entschieden (Palettenwerte oder Materialien des Spiels).

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.

Die Pipeline erfasst die ASTs der Funktionen, die bestimmen, was eine Stufe schreibt (`STAGE_CACHE_FUNCTIONS`), und der
Paketzusammenstellung (`PIPELINE_CACHE_FUNCTIONS`). Render-/Autoren-/Exporterquellen werden vollständig über die
Quellen-Closure erfasst; reine Berichts- und Orchestrierungsänderungen lösen keinen Modell-Neubau aus. Neue Helfer, die
Stufenergebnisse oder Pakete schreiben, gehören in diese Listen. Dieses Verhalten ist mit Cache-Regressionsfällen geprüft.
