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
Varianten im Viewer: `world`, `fps`, `arrow`, `game` („Spielmodell“) und `fps_game` („Ego-Spielmodell“, Datei `<Asset>_FPS_Game`, Wurzel
`<Asset>_FPS`, nur LOD0, Clip des Ego-Modells). Beide Spielvarianten sind optional; fehlen sie im Katalog, arbeitet der Viewer wie
zuvor. „Ego“ öffnet aus dem Spielmodell das Ego-Spielmodell (sonst das gestaltete Ego-Modell); Werkzeugwechsel in der Ego-Ansicht behalten die Variante.
Die Viewmodel-Kamera (Sichtfeld, Regler, A/B) gilt für beide Ego-Varianten, sie liest `viewmodel_camera.json` des Werkzeugs.
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

Das Ego-Modell ist nicht an das Spieler-FOV gebunden: Es liegt im Kameraraum und wird mit einer eigenen Kamera gezeichnet. Den
Wert nennt `viewmodel_camera.json` zusammen mit `player_fov_dependency: "none"`, `aspect_policy`, `camera_offset_m`,
`validated_vertical_fov_degrees` (für das gestaltete Ego-Modell; Werte, bei denen der Bildausschnitt für alle geprüften Seitenverhältnisse hält: Portalkanone und
Magnetgreifer 46,69/50,69°, Taschenlampe 42,69–54,69°, Bogen nur 46,69°) und einem `runtime`-Hinweis; derselbe Block steht als
`viewmodel` in `unity_contract_fps.json` (dort `authored_model_validated_vertical_fov_degrees` und `game_model_validated_vertical_fov_degrees`). Das reduzierte Spielmodell ist nur beim Datenwert geprüft (`qa_game_fps.json` › `viewmodel_framing`: Bildschirmausdehnung je Renderer gegen das gestaltete Modell in jedem Clipbild für 16:9 und 16:10 innerhalb 0,3 % der Bildgröße, Fadenkreuz frei – vertexbasiert); eine Viewmodel-FOV-Einstellung des Spiels braucht für das Spielmodell eine neue Prüfung. Einbau:
[UNITY_EINBAU](UNITY_EINBAU.md).

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

Die Stufe `game` (`toolgen/game_export.py`, Eintrag in `STAGES`) macht aus dem Weltmodell ein Modell für Unity 6 (URP); die
Stufe `game_fps` (`--viewmodel`) tut dasselbe für das Ego-Modell. Einbau-Vorbereitung: [UNITY_EINBAU](UNITY_EINBAU.md).
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
auf ein Palettenmaterial ab. Nicht-Leuchtmaterialien sind **matte Varianten** der Cube-Escape-Materialien
(`M_RobotBody_Matte`, `M_RobotDark_Matte`, `M_Metal_Matte`, `M_HazardOrange_Matte`; `ce_base` nennt das Original, Farbwerte in
sRGB aus Cube Escapes `generate_assets.py`): Die gleichnamigen Materialien des Spiels glänzen stärker, deshalb legt der Import
wie beim matten Spielerroboter eigene matte Varianten an. Leuchtmaterialien behalten ihre Namen (`M_GlowCyan`, `M_GlowOrange`);
neu ist `M_GlowWarm` für die warmweiße Linse der Taschenlampe. Die Abbildung muss vollständig sein; ein
unbekanntes Quellmaterial bricht den Export ab. Matt wie Station und Spielerroboter: Nicht-Leuchtmaterialien Metallic höchstens 0,35 und
Roughness mindestens 0,55 (Prüfgrenze `finish` in der Palettendatei), nur `M_Glow*` leuchtet.
Höchstens sechs Materialien je Werkzeug (Taschenlampe sechs, die anderen fünf).

**LOD und Kollision.** Jeder Renderer hat ein Geschwister `<Teil>_LOD1` mit etwa 30 % der Dreiecke (Prüfbereich 25–40 %, Silhouette
innerhalb 2 % der Teildiagonale, gleiche Materialien und Shape Keys); die Namen folgen der Cubegen-Konvention, aus der
Unity beim FBX-Import eine LODGroup baut. Kollisionsboxen werden am tatsächlichen LOD0-Mesh gefittet (konvexe Hülle,
orientierte Boxen, Zusammenführen solange die Box mindestens halb gefüllt bleibt; höchstens 6 am Wurzelobjekt und 3 je beweglichem Teil)
und stehen in `unity_contract.json` › `colliders` im Feldformat des Cubegen-Sidecars (`type`, `center`, `size`, `rotation`, Unity-Achsen,
relativ zum Teil). Leuchtteile, Kleinteile unter 12 mm und der geladene Pfeil (sichtbarkeitsanimiert) bekommen keine Box. Die Öffnungen (Mündung,
Greifraum, beim Bogen der Raum zwischen Griff und Nocke) werden mit Testpunkten auf Freiheit geprüft; eine Gesamtbox, die sie blockiert, fällt durch.

**Dreiecksbudget.** `data/game_budget.json` nennt je Werkzeug ein LOD0-Budget (Welt: Portalkanone und Magnetgreifer 8 000,
Bogen 6 000, Taschenlampe 5 000; Ego: 16 000 / 16 000 / 14 000 / 12 000). Nach dem Zusammenführen wird LOD0 mit dem
Collapse-Decimate-Modifier gleichmäßig auf das Budget verkleinert (Shape Keys des Bogens folgen wie bei LOD1 über das nächste
Dreieck; Iteration bis auf 4 % genau); LOD1 entsteht danach aus dem reduzierten LOD0. Die Maßprüfung `bounds_lod0` (1 mm gegen das
Quellmodell in jedem Clipbild) gilt unverändert, `triangle_budget` prüft das Budget. Das Budget ist ein Datenwert: Ändern baut
neu, ohne Änderung am Generator. Das Weltmodell vor dem Export bleibt unverändert, Viewer-Varianten „Welt“ und „Ego“ zeigen
weiter das volle Modell; die Varianten „Spielmodell“ und „Ego-Spielmodell“ zeigen das reduzierte.

**Ego-Modell (`game_fps`).** Dieselbe Pipeline für `<Asset>_FPS` (Hände, Arme, Werkzeug): `<Asset>_FPS_Game.blend/.fbx/.glb`,
`unity_contract_fps.json`, `qa_game_fps.json`, `preview_game_fps.png` (ab Standard: Quelle, LOD0, LOD1). Unterschiede: eigenes
Budget, **keine Kollision** (der Vertrag nennt `collision: none` und `colliders: []`), höchstens 14 Renderer (Arme, Hände und
Finger sind bewegte Teile, je animiertem Besitzer ein Renderer; Taschenlampe 2, Portalkanone 3, Magnetgreifer 5, Bogen 9),
höchstens 7 Materialien (die Hand bringt `M_HazardOrange_Matte` hinzu) und der Block `viewmodel` mit der Kameradaten aus
`viewmodel_camera.json`. Die Ego-Hierarchie (`Viewmodel_Motion`, `UpperArm_*`, `LowerArm_*`, `Hand_*`, `Fingers_*`,
`Socket_*`) und der Clip (97 Frames) bleiben erhalten; QA wie beim Weltmodell (Bounds in jedem Clipbild, Anker, Reimport).

**Achsen.** Blender (Z oben, vorn −Y) wird zu Unity (Y oben, vorn +Z) mit Position `(−x, z, −y)`. FBX: `axis_forward −Z`,
`axis_up Y`, ohne `bake_space_transform` (das bricht Objektanimation). In Unity den FBX-Import mit `bakeAxisConversion`
einstellen; der Vertrag (`axes.fbx.unity_import`) nennt das. GLB (+Y oben) ergibt über Unitys X-Spiegelung dieselbe Abbildung.

**Vertrag.** `unity_contract.json` enthält Renderer (Rolle, LOD, Materialien, Dreiecke, Blend Shapes, `MeshRenderer` oder
`SkinnedMeshRenderer`), Anker und Knoten mit lokaler Blender- und Unity-Transformation, Palette, LOD-Gruppen, Kollisionsboxen,
Clip mit Ereignissen, Quellhashes (Weltmodell, Palette) und Hashes der drei Dateien.

**QA** (`qa_game.json`, Pflicht im Paketmanifest `required_qa`): `palette`, `renderers_in_target`, `materials_in_target`,
`bounds_lod0` (LOD0 gegen das Weltmodell in jedem Clipbild, 1 mm), `anchors_identical`, `clip_blend`, `lod1`, `collision` sowie
`roundtrip_glb` und `roundtrip_fbx` (frischer Import: Namen, Materialslots, Clip, Anker- und Teilgrenzen an neun Bildern, 2 mm).

Werte (0.5.0, `unity_contract*.json`; „Quelle“ = Dreiecke und Knoten vor dem Export):

| Werkzeug | Variante | Quelle: Dreiecke / Knoten | Spielmodell: Renderer | Dreiecke LOD0 / LOD1 | Materialien | Boxen |
|---|---|---|---|---|---|---|
| Portalkanone | Welt | 32 468 / 113 | 1 | 8 000 / 2 383 | 5 | 4 |
| Portalkanone | Ego | 45 932 / 232 | 3 | 15 996 / 4 771 | 6 | – |
| Magnetgreifer | Welt | 25 928 / 122 | 3 | 7 998 / 2 383 | 5 | 7 |
| Magnetgreifer | Ego | 39 392 / 241 | 5 | 15 992 / 4 770 | 6 | – |
| Taschenlampe | Welt | 10 628 / 37 | 1 | 5 000 / 1 500 | 6 | 2 |
| Taschenlampe | Ego | 17 360 / 98 | 2 | 11 998 / 3 594 | 7 | – |
| Bogen | Welt | 12 036 / 71 | 3 | 5 996 / 1 793 | 5 | 6 |
| Bogen | Ego | 25 500 / 190 | 9 | 13 992 / 4 181 | 6 | – |

Die Spielmodelle haben je Modell nur noch 3–39 Knoten (Leerknoten, Anker, Renderer samt LOD1) statt 37–241, und ausschließlich
matte Palettenmaterialien statt der 8–14 glänzenden Generatormaterialien (Metallic 0,6–0,7, Roughness 0,35).

Offen bleibt der Einbau in Unity (siehe Grenzen).

## Waffen 1–9 (0.7.0 Ironsight)

Neun Handwaffen als Werkzeuge in der Roboterhand (Auftrag des Nutzers vom 15.10.2026: Waffen 1–9 der Konzepttafel, der Bogen
ausdrücklich nicht): Pistole, Sturmgewehr, Impulsgewehr, Schrotflinte, Scharfschützengewehr, Maschinenpistole, Fusionsgewehr,
Spurgewehr und Raketenwerfer. Stil wie die anderen Werkzeuge (weiße Schalen, Graphitmechanik, Metall); Farbe trägt nur das Element
(Destiny-2-angelehnt): KINETIC grau/weiß, ENERGY cyan, SOLAR orange, VOID violett, ARC blau. Es sind Cube-Escape-Werkzeuge in der
Hand: keine Munition, kein Schaden, keine Regeln, kein Projektil im Asset. Die Verteilung der Elemente ist eine Wahl dieser Arbeit
(das Konzeptbild war beim Bau nicht lesbar): `element` je Eintrag in `data/tools.json` und `DESIGNS` (`weapon_designs.py`).

**Aufbau.** Ein Baukasten statt neun Kopien: `scripts/tool_assets/weapon_kit.py` (Welt, FPS-Kopie, Use-Clip, Reimport-Prüfung),
`weapon_designs.py` (Geometrie und Clip-Daten je Waffe, ohne bpy) und `weapon_gif.py` (Animations-GIF, Systempython). Die Primitive
kommen aus dem Portalkanonen-Helfer wie bei der Taschenlampe. Jede Waffe hat wie jedes Werkzeug einen eigenen Ordner
(`Pistole/`, `Sturmgewehr/`, `Impulsgewehr/`, `Schrotflinte/`, `Scharfschuetzengewehr/`, `Maschinenpistole/`, `Fusionsgewehr/`,
`Spurgewehr/`, `Raketenwerfer/`; die Pipeline arbeitet je Ordner) mit fünf Starter-Dateien von drei Zeilen. Der Autoren-Kopierordner
enthält kein `data/`; Asset, Clip, Element und Griffneigung stehen deshalb in `DESIGNS`, `tools.json` spiegelt sie, ein Test
(`tests/test_weapons.py`) hält beide gleich. Eine zehnte Waffe ist ein Eintrag in `DESIGNS`, in `tools.json`, `viewmodels.json` und
`game_budget.json` plus ein Ordner mit den fünf Startern.

**Koordinaten und Anker.** Blender: vorn −Y, oben +Z, Meter, Wurzel am Ursprung; der Ursprung ist die Mitte des Pistolengriffs
(`Socket_Hand`). Jede Waffe hat `Socket_Hand` (Griffmitte), `Socket_SupportHand` (Mitte des Handschutzes bzw. Vorderschafts,
bei der Pistole am Rahmen), `Socket_Muzzle` und `Socket_CenterOfMass`. Die Anker liegen im jeweiligen Griffteil: `weapon_kit.py`
bricht den Bau ab, wenn `Socket_Hand` oder `Socket_SupportHand` mehr als 4 mm außerhalb des Teils liegen (`grip_part`/`support_part`),
der Spiel-Export misst dasselbe am Netz (`grip_sockets_on_tool` in `qa_game.json`, `surface_distance_m` je Anker im Vertrag;
negativ = im Teil, Grenze +4 mm). Der Griff ist um `grip_tilt_degrees` nach vorn geneigt (Pistole 14°, Maschinenpistole 18° …);
`Socket_Hand` bleibt unrotiert (Lauf = −Y), die Hand folgt der Neigung über `hand_rotation_degrees` im Ego-Profil.

**Haltung im Vertrag (`hold`).** `unity_contract.json` und `unity_contract_fps.json` enthalten für jede Waffe den Block `hold`:
Anker (`hand_socket`, `support_socket`, `muzzle_socket`), `two_handed`, `grip_tilt_degrees`, `grip_axis` (Griffunterkante → Griffoberkante),
`muzzle_axis` (−Y bzw. +Z in Unity), `grip_to_muzzle_degrees` (90° − Neigung), `element` und eine Anleitung. Damit richtet das Spiel
die Roboterhand an der Griffachse aus und lässt den Lauf entlang der Zielrichtung zeigen; der Lauf zeigt im Modell nie nach oben oder
unten. Die Vektoren stehen im Wurzelraum wie die Anker: die 180°-Drehung des FBX-Imports (`axes.fbx.export_yaw_degrees`) gilt für sie
genauso und wird genau einmal angewendet ([UNITY_EINBAU](UNITY_EINBAU.md) › Waffen in der Hand).

**Stützhand.** Das Ego-Profil einer Waffe nennt `support_socket` (`Socket_SupportHand`) und `support_radius` (halbe Höhe und
Breite des Handschutzes): `first_person.py` legt die linke Hand an den Anker des Werkzeugs und schließt die Finger um dessen
Querschnitt. Die älteren Werkzeuge setzen die Stützhand weiter mit festem Versatz (`support_offset`) und festem Radius an den Griffanker. Die QA misst den Abstand der Finger-, Daumen- und Handflächenpunkte zur Werkzeugoberfläche
(`hand_touch_m`, Grenze `touch_tolerance_m` = 8 mm) und verwirft eine Hand in der Luft. Beide Hände hängen starr am Werkzeug (der
Rückstoß bewegt Werkzeug und Hände gemeinsam), die Messung im Ruhebild gilt daher für den ganzen Clip. Gemessen an den vier älteren
Werkzeugen berührt die Stützhand der Portalkanone und des Magnetgreifers die Oberfläche (0,1 mm); ihr Weltanker `Socket_SupportHand`
lag bis 0.7.0 dagegen 37 mm außerhalb des Gehäuses (Vertrag `surface_distance_m`; Magnetgreifer 37 mm, Taschenlampe 35 mm); 0.7.1 legt ihn ans Gehäuse (+1 mm bzw. 15 mm innen).

**Use-Clip.** Ein Einzelclip `<Name>_Use`, 97 Bilder bei 24 fps, keine Wiederholung, kein Autoplay, Ruhepose am Ende. Der Clip
schreibt **keine Kurve auf die Wurzel**: bewegt werden nur Kind-Knoten (`Anim_Slide`, `Anim_Bolt`, `Anim_Cell`, `Anim_Fin*`, `Anim_Coil`,
`Anim_Hatch`). Der Unity-Import dreht das Modell um 180° um Y; eine Wurzelkurve müsste mitgedreht werden, ohne sie ist der Clip
unabhängig vom Yaw. `clip_root_free` in `qa_game*.json` verlangt das für die Waffen, `clips[0].root_curves` im Vertrag nennt die
Kurven der Wurzel (leer). Bewegungen: Pistole der Schlitten (Bild 14–30), Sturmgewehr/Maschinenpistole/Spurgewehr der Verschluss,
Impulsgewehr die Zelle (drei Impulse), Schrotflinte der Repetierschieber (Bild 36–56), Scharfschützengewehr der Kammerstängel
(drehen, zurück, vor, drehen), Fusionsgewehr zwei Flossen und ein Spulenring beim Aufladen (Bild 10–47), Raketenwerfer die
Ladeklappe. Der Ego-Clip `<Name>_Use` fügt den Rückstoß hinzu.

**Rückstoß (Ego).** `motion` im Ego-Profil (`fire_frame`, `kick_m`, `pitch_degrees`, `recovery_frames`, optional `charge_m`,
`yaw_degrees`): `Viewmodel_Motion` schiebt Waffe und Hände ruckartig zum Spieler und hebt die Mündung um die Hand (nicht um die
Kamera), danach Abklingen bis in die Ruhe (`recoil_pose`, Impulskurve in `motion_profiles.recoil_impulse`). Fusionsgewehr: Schuss bei Bild 46
nach dem Aufladen. Ohne `motion` bleibt die alte Anwendungsbewegung der Werkzeuge.

**Kopfprüfung.** Bei schlanken Läufen unter der Stützhand ist der Mündungskopf klein; `head.limits` im Profil lockert beim
Impulsgewehr, Scharfschützengewehr, bei der Maschinenpistole und beim Spurgewehr `head_min_unoccluded_fraction` auf 0,3 und
`head_min_screen_fraction` auf 0,001; die wirksamen Werte stehen in `qa_viewmodel.json` › `head.limits` und werden von
`verify_output.py` erneut geprüft.

**Materialien und Budgets.** Neue Palettenmaterialien `M_GlowVoid`, `M_GlowArc`, `M_GlowKinetic` (neu in Cube Escape, beim Import
anlegen; ENERGY und SOLAR nutzen die vorhandenen `M_GlowCyan`/`M_GlowOrange`). Eine Waffe braucht 4–5 Palettenmaterialien (Ego 5–6).
Budgets: Welt 3 500–7 000, Ego 11 000–15 000 Dreiecke LOD0 (Datenwerte, Schätzungen wie die übrigen).

Werte (0.7.0, `output/_standard`; Dreiecke LOD0 / LOD1, Quelle = vor dem Export):

| Waffe | Element | Länge (m) | Welt: Quelle → LOD0 / LOD1 | Renderer | Ego: Quelle → LOD0 | Hände (Berührung) |
|---|---|---|---|---|---|---|
| 1 Pistole | kinetic | 0.24 | 6 076 → 3 498 / 1 048 | 2 | 12 808 → 10 996 | 0.0 mm |
| 2 Sturmgewehr | kinetic | 0.93 | 13 636 → 5 998 / 1 798 | 2 | 27 100 → 13 996 | 0.0 mm / 0.1 mm |
| 3 Impulsgewehr | energy | 0.86 | 8 924 → 5 998 / 1 796 | 2 | 22 388 → 13 998 | 0.0 mm / 0.1 mm |
| 4 Schrotflinte | solar | 0.90 | 10 508 → 5 998 / 1 798 | 2 | 23 972 → 13 994 | 0.0 mm / 0.0 mm |
| 5 Scharfschützengewehr | void | 1.13 | 15 168 → 6 998 / 2 098 | 2 | 28 632 → 14 998 | 0.1 mm / 0.0 mm |
| 6 Maschinenpistole | arc | 0.62 | 10 392 → 4 998 / 1 498 | 2 | 23 856 → 12 996 | 0.0 mm / 0.0 mm |
| 7 Fusionsgewehr | energy | 0.96 | 11 524 → 6 996 / 2 096 | 4 | 24 988 → 14 994 | 0.1 mm / 0.0 mm |
| 8 Spurgewehr | kinetic | 1.04 | 13 784 → 5 998 / 1 798 | 2 | 27 248 → 13 998 | 0.0 mm / 0.2 mm |
| 9 Raketenwerfer | solar | 0.72 | 11 364 → 6 998 / 2 098 | 2 | 24 828 → 14 996 | 0.0 mm / 0.0 mm |



## Waffen-Module und Ausrüstungs-Slots (0.8.0 Gunmetal)

Auftrag (über die Cube-Escape-Sitzung, 16.10.2026): die Waffen 1–9 detailreicher, Industrial-Sci-Fi nach Destiny 2, mit den
Material-Slots des Ausrüstungssystems von Cube Escape 0.64 Anodize. Anker, Knoten, Pivots, Clips und Maßstab bleiben wie in 0.7.1
(verglichen mit den in Cube Escape 0.63 importierten Verträgen: Anker, Knoten und Clips gleich).

**Module.** `weapon_designs.py` hat gemeinsame Hard-Surface-Bausteine: `panel` (Verkleidung mit dunkler Fuge), `side_armor`
(abgeschrägte Seitenplatten beidseitig), `display` (Rahmen, dunkles Glas, leuchtende Segmentbalken; Normale +X oder zum Spieler +Y),
`energy_cell` (Elementkern zwischen Metallkappen im Käfig), `heat_sink` (Kühlrippen), `accent`. Jede Waffe ruft nach ihrem 0.7-Körper
`<name>_modules(k)` auf; die Module liegen außerhalb der Griff- und Stützhandzone. Lesbar aus der Ego-Ansicht sind vor allem die
Anzeigen auf der +X-Seite und auf der Rückseite der Visiere (die Kamera sieht die +X-Seite und die Oberseite). Der Griff bekommt
Griffsporn (`GripTail`) und Schrauben. Kennzeichen je Klasse: Pistole Kompensator und Munitionsanzeige hinten am Schlitten,
Sturmgewehr Seiten- und Visieranzeige, Kühlrippen, Akzentkappe; Impulsgewehr Bugpanzer, zwei Zellen am Schaft; Schrotflinte
Patronenträger mit zwei Patronen; Scharfschützengewehr Sonnenblende, Zielfernrohranzeige, Laufrippen; Maschinenpistole Arc-Zelle oben,
Trommelschrauben; Fusionsgewehr Ladeanzeige, Kühlrippen, Akzentspitzen an den beweglichen Flossen; Spurgewehr Laufrücken,
Mündungsring; Raketenwerfer Zielbildschirm, Antenne, Rohrpanzer, Abgasstreben.

**Materialien = Kanäle.** Der Baukasten hat je Kanal ein Quellmaterial: `PG_Primary`, `PG_Secondary`, `PG_Accent`, `PG_Metal`,
`PG_Detail`, `PG_Display` und die Elementleuchte (`PG_Kinetic`/`Cyan`/`Amber`/`Void`/`Arc`). `data/game_palette.json` › `channels`
bildet sie auf `MT_Primary` … `MT_Detail` ab (Elementleuchte → `MT_Energy`, Anzeige → `MT_Emission`); `map` behält die Abbildung
auf die `M_*`-Palette für Vertrag 1. `game_export.tool_palette` wählt je Werkzeug: `"materials": "equipment_channels"` in
`data/tools.json` (nur die Waffen) und Vertrag ≥ 2 → Slots; `MT_Energy` bekommt Farbe und Leuchtstärke des Elements. Quellen ohne
Kanal (die Roboterhände im Ego-Modell) behalten die Palette. Grenzen: 7 Materialien je Weltmodell, 12 je Ego-Modell (7 Slots plus
Handmaterialien); im Vertrag 1 bleibt es bei 6/7.

**Hände und Arme (Befund Cube Escape 0.65 „Holdfast“).** Die Ego-Hände hielten die Waffen verdreht: rechts stand der Unterarm
senkrecht unter dem Griff (Handgelenk ≈ 105° abgeknickt), links lag die Hand oben auf dem Handschutz, die Finger zeigten zum Ellbogen
(≈ 160°). Anker und Greifen waren richtig, falsch war die Armpose. Jetzt:

- `support_grip: "underhand"`: die Stützhand liegt unter dem Handschutz (Handfläche unten, Zeigefinger vorn, Daumen zur Kamera +X,
  Finger um die ferne Seite).
- `arm_pose` je Seite (Kameraraum: rechts = −X, vorn = −Y, oben = +Z): `upper` = Ellbogen → Schulter; der Unterarm entweder
  absolut (`forearm`, Ellbogen → Handgelenk; links) oder relativ zur Hand (`forearm_rise_degrees` über der Knöchelrichtung,
  `forearm_yaw_degrees` zum Handflächenrand hin; rechts 27°/6°, Pistole 31°). `aim_arm` setzt Ellbogen und Schulter aus der Ruhepose;
  die starre Zweigliederkette folgt der Hand durch den Clip. `shoulders` entfällt bei den Waffen.
- Läufe in der Ego-Pose fast waagerecht (`aim_target_m` 0–3° unter der Hand statt 12–14°), Stützhand 35° zur Kameraseite gerollt
  (`support_roll_degrees`): beides lässt die Knöchel weniger nach unten bzw. zur fernen Seite zeigen.
- Prüfung je Bild des Clips (`qa_viewmodel.json` › `wrist_bend`): Winkel Unterarm ↔ Knöchelrichtung höchstens `max_wrist_bend_degrees`
  (Entscheidung des Nutzers 16.10.2026: Ziel 45°, harte Grenze 55°, als Test festgehalten) und Ellbogen auf der Handflächenseite.
  Gemessen (`output/_standard`): rechts 45,7–52,1° (Pistole 52,1, MP 52,0, Sturmgewehr 50,7, Scharfschützen-/Spurgewehr 45,9/45,7),
  links 30,3–30,6°; vorher 105°/160°. Rechts liegt über dem Ziel, weil die Griffneigung (12–18°) die Knöchel nach unten kippt und der
  Unterarm für den Bildausschnitt ≈ 27° steigen muss; flacher ginge nur mit flacheren Griffen (Vertrag `hold.grip_axis`).
- Bildausschnitt auch bei 1,7× um `Socket_Hand` (`GAME_ENLARGEMENT_MAX`, so vergrößert Cube Escape 0.65 die Waffen), verbindlich:
  `proximal_forearm_max_screen_y_enlarged` < 0.

Anker, `hold`, Vertragsformat unverändert; geändert sind nur Hand- und Armknoten (Ruhe und Clip) der Ego-Modelle.

**Vertrag 2.** `format` 2, `material_convention`, bei den Waffen Block `equipment` ([UNITY_EINBAU](UNITY_EINBAU.md) › Ausrüstungs-Slots).
`generate_tools.py --contract 1` (oder `game_export.py --contract 1`) schreibt das 0.7-Layout; die Wahl steckt im Stufenschlüssel
(Eintrag `game_contract` im Werkzeug, nur bei 1).

Werte (0.8.0, `output/_standard`; Dreiecke LOD0 / LOD1, Quelle = vor dem Export; Budgets in `data/game_budget.json` um 1 000–2 000 angehoben):

| Waffe | Welt: Quelle → LOD0 / LOD1 | Renderer | Ego: Quelle → LOD0 | Hände (Berührung) |
|---|---|---|---|---|
| 1 Pistole | 8 764 → 4 498 / 1 348 | 2 | 15 496 → 12 996 | 0.0 mm |
| 2 Sturmgewehr | 17 240 → 6 998 / 2 098 | 2 | 30 704 → 15 994 | 0.0 mm / 0.0 mm |
| 3 Impulsgewehr | 12 748 → 6 998 / 2 096 | 2 | 26 212 → 15 996 | 0.0 mm / 0.1 mm |
| 4 Schrotflinte | 14 920 → 6 998 / 2 098 | 2 | 28 384 → 15 996 | 0.0 mm / 0.0 mm |
| 5 Scharfschützengewehr | 20 284 → 7 998 / 2 394 | 2 | 33 748 → 15 996 | 0.1 mm / 0.0 mm |
| 6 Maschinenpistole | 12 900 → 5 998 / 1 792 | 2 | 26 364 → 14 994 | 0.0 mm / 0.0 mm |
| 7 Fusionsgewehr | 13 864 → 7 994 / 2 394 | 4 | 27 328 → 15 996 | 0.1 mm / 0.0 mm |
| 8 Spurgewehr | 16 452 → 6 998 / 2 098 | 2 | 29 916 → 15 994 | 0.0 mm / 0.2 mm |
| 9 Raketenwerfer | 15 352 → 7 998 / 2 393 | 2 | 28 816 → 15 994 | 0.0 mm / 0.0 mm |

## Ego-Clips (0.9.0 Cadence)

Zustandsclips der Ego-Modelle nach dem Muster der Destiny-2-Ego-Waffen; Einbau: [UNITY_EINBAU](UNITY_EINBAU.md) › Ego-Clips,
Tabelle: [EGO_CLIPS](EGO_CLIPS.md).

- Daten: `data/ego_clips.json` (Clipliste mit Länge, Loop, Start-/Endpose, Fadenkreuz frei, unterbrechbar, Events; `defaults` und
  `classes` je Waffe; `wrist`). Bewegung: `scripts/tool_assets/ego_clips.py` (reines Python, je Clip eine Funktion Frame → Pose),
  Inspect und Reload je Klasse in `ego_weapon_motions.py`. Die Pose zählt gegen die Ruhepose (Frame 1 von Use) in Kameraachsen:
  `pitch` (Mündung hoch), `yaw` (Mündung links), `roll`, `twist` (Drehung um die Unterarmachse des Griffarms, kippt die Waffe ohne
  das Handgelenk zu beugen), `right`/`up`/`back`, `aim` (Anteil der Visierpose), `follow`, `support`/`detached` (Stützhand), `part`
  (Nachladeteil `Anim_<Teil>` in Waffenachsen).
- `first_person.py` keyt die Clips hinter Use auf derselben Zeitleiste (ab Frame 101, drei Frames Abstand) an `Viewmodel_Motion`,
  der Stützhand und dem Nachladeteil; die Szene und die Hauptexporte behalten 1–97. Visierpose: Waffenachse parallel zur Blickrichtung
  ohne Rollen, Visierlinie (Oberkante der Visierteile + `eye_above_m`, Optiken durch die Mitte) auf der Bildmitte in der Tiefe der Ruhepose
  abzüglich `pull_back_m`.
- Arme: Der Unterarm behält in den Clips seine Bildrichtung aus der Ruhepose (nur um `follow` des Waffendrehens mitgedreht); beugt das
  Handgelenk über max(45°, Ruhewert + 4°) (höchstens Grenze − 1°), schwenkt der Unterarm erst seitlich zur Knöchelrichtung (Ellbogen bleibt
  unter dem Bild, Ellbogen auf der Handflächenseite), dann um den Rest hoch. Grund: Die Ruhepose aus 0.8.0 liegt schon nahe an allen
  Grenzen (Unterarm-Rand der Pistole −0,009 Bildhöhe, Handgelenk 48,5°); frei sind Drehen um die Unterarmachse, Verschieben zur Bildmitte und
  Mündung hoch; Absenken kostet Handrand, Heben und Wegschieben kosten den Unterarm-Rand, Mündung runter und Gieren das Handgelenk.
- Unterarm-Rahmen: Käme die Ellbogenhälfte ins Bild, dreht `plan_corrections` den Unterarm um den kleinsten Winkel um EINE
  Achse je Arm (aus zwölf, für die ganze Zeitleiste) und glättet die Winkel je Clip (höchstens 1,5° Zunahme je Frame, Clipenden
  exakt); das Handgelenk darf dafür bis Grenze − 0,5°. Ausnahme: Stützarm in den Ziel-Clips (`support_forearm_visible`,
  Entscheidung des Nutzers), dort wird nur gemessen (`support_forearm_visible_max_screen_y`). Zucken prüft
  `ego_forearm_max_twitch_degrees` (Änderung der Drehrate je Frame ≤ 2°, Clips unter 16 Frames halb gewichtet).
- Prüfung je Frame (`validate`, `ego_clip_report`): alle bisherigen Ego-Prüfungen über Use und alle Clips, Clipgrenzen exakt in der
  benannten Pose (1e-4), Kontakt außer im `detached`-Fenster, Fadenkreuz nur bei `reticle_free`, Visierlinie in AimIdle auf der Mitte
  (±0,002) und Visier zu 90 % frei von Händen, keine Material- oder Farbanimation. `qa_viewmodel.json` › `ego_clips` nennt je Clip den
  größten Handgelenkwert und die Unterarm-Nachführung.
- Fire/AimFire beginnen ein Frame vor dem Schuss des Use-Clips und laufen bis Rückstoß und Mechanik ruhen (`fire_end_frame`), auf
  `fire_cooldown_s` zeitgerafft (`fire_scale`, Abstimmung mit CE 0.66); Teile, die beim Schuss nicht ruhen (Aufladen des
  Fusionsgewehrs), bleiben in Fire in Ruhe.
- Pistole beidhändig (0.10.0): `support_grip` `cup` in `data/viewmodels.json` – die linke Hand nimmt die Drehung des Griffankers
  (plus `hand_rotation_degrees.L`) und `support_radius` [0,017, 0,036] legt ihre Finger ohne Überschneidung vor die der rechten Hand; `arm_pose.L` relativ
  (Anstieg 18°, seitlich 10°). Die Pistolen-Clips nutzen kleinere Drehungen um den Unterarm (die linke Hand liegt nah am unteren Bildrand).
- Spiel-Export (`game_export.py`, Vertrag 3): Clips-Datei `<Asset>_FPS_Game_Clips.fbx/.glb` (Szenenbereich und manuelle Aktionsbereiche
  vorübergehend auf die Ego-Zeitleiste). Teile, die die Clips nicht selbst stellen (Mechanik, Leuchten), bekommen in Fire/AimFire die Werte des Use-Clips ab dem Schuss (Schlitten, Verschluss, Pumpe; `fire_end_frame` verlängert Fire bis zur Ruhe), sonst Ruhekeys an jedem Clipende (`clip_keys`); ohne Keys im Clipbereich ließe glTF sie
  fallen. Reimport beider Clips-Dateien an Clipenden, -mitten und Events; Bildausschnitt des reduzierten Modells an denselben Frames.

## Oberflächenkarten (0.11.0 Primer, Vertrag 4)

UV1 und Maskenkarten für den Masken-Modus von Cube Escape 0.71; Einbau und Belegung: [UNITY_EINBAU](UNITY_EINBAU.md) › Maskenkarten.
Code: `toolgen/surface.py` (reine Helfer und UV1), `toolgen/surface_bake.py` (Stufe), Tabelle Slot → Kanal in `data/game_palette.json` › `channel_map`.

- UV1 (`game_export.py`, ab Vertrag 4, vor dem Zusammenführen): je Modell alle Teile im Mehrobjekt-Editmodus, `smart_project` (66°),
  `average_islands_scale`, `pack_islands` ohne Drehung (FRACTION 0,008, konkav), danach in [16/1024, 1] geschoben; Teile mit
  `FPS_*`-Materialien (Hände, Arme) bleiben auf (0, 0). Gemessen wird die größte Drehung je Fläche beim Packen (Pistole 0,013°, Gleitkomma der
  Skalierung; Grenze 0,5° – seit 0.12.0 statt 0,1°, weil das Gleitkomma-Rauschen des Packers je Plattform schwankt: Magnetgreifer Mac 0,097°, Linux 0,1015°, Entscheidung des Nutzers 16.10.2026; echte Drehungen des Packers fängt die Grenze weiter). Das Ego-Modell öffnet zuerst das Weltmodell, macht dort dieselbe UV1 und überträgt sie je Teil (Name, Schleifenzahl,
  Flächenaufbau); fehlt ein Zwilling, bekommt es ein eigenes Atlas (`shared_with_world` false, `parts_without_world_twin`). `game_fps` liest
  deshalb `<Asset>.blend` mit.
- Dezimierung: Kollaps auf das Budget und LOD1 behält UV1, faltet aber Dreiecke (Portalwerfer 250 auf LOD0) und legt Inselränder über die
  Insel selbst. `untangle` schiebt danach die betroffenen UV-Ecken (Ecke = Vertex + UV in der Insel) auf den Mittelpunkt ihrer Nachbarn, einen
  Nachbarn oder die halbe Strecke, wenn das Falten bzw. die Überlappungsfläche (Polygon-Clipping) um die Ecke sinkt; feste Reihenfolge.
  Ein Zug auf einen Nachbarn hinterlässt ein Dreieck ohne Fläche (keine Texel, keine Überlappung; seine Normalkarte und Tangente kommen
  vom Nachbarn); `zero_area_triangles` in `uv1_lod0` zählt sie.
- QA im Spiel-Export (`qa_game*.json`): `uv1_layers` (UVMap Index 0 und Render-Map, UV1 Index 1), `uv1_lod0` (Bereich, Überlappung 0 bei 2048,
  Abstand ≥ 4 px bei 1024, Ecke frei), `uv1_lod1` (wie LOD0, Überlappung nur berichtet), `uv1_source` (Drehung, Hash, Übertragung,
  `decimation_folds`); Reimport: UV1 auf allen Renderern, im GLB `TEXCOORD_1` und `TANGENT` je Primitive.
- Stufe `surface_bake` (standard/full, nach `game_fps`, `heavy`, `min_contract` 4): je Modell LOD0 bei Frame 1, Hände entfernt; Gewichte als
  eigenes Raster (Texelmitte, erstes Dreieck gewinnt, 8 Schritte Dilatation in fester Nachbarreihenfolge); Cycles auf der CPU mit Seed 0:
  AO-Bake (Welt 16, Ego 32 Samples, 0,08 m), EMIT-Bake für Kante/oben/Höhe und NORMAL-Bake (Tangentenraum UV1) mit je 4 Samples. Kante =
  12 × (1 − Bevel-Normale · Schattierungsnormale), Bevel 4 mm, mal Konvexität aus lokalem AO (16 mm; unter 0,35 Falte = 0, über 0,7 voll).
  `render_init`-Handler von `run_asset.py` werden geleert, damit Samples und Gerät der Teststufe nicht greifen (standard = full).
  PNG-Schreiber eigen (`png_encode`: Filter None/Sub/Up, zlib 9, nur IHDR/IDAT/IEND). Laufzeit Pistole: Welt 5 s, Ego 42 s (AO 31 s), 4 Threads.
- QA `qa_surface.json`: `channel_map`, `uv1_shared` (Hash der Welt-UV1 in beiden Exporten gleich), je Modell `uv1_<variant>` (Layout wie oben)
  und `maps_<variant>`: Gewichte one-hot 255 in den Inseln, nichts jenseits der Dilatation, jeder vorkommende Kanal hat Texel, AO-Mittel
  0,3–0,95, Kantenanteil (G > 0,5) 2–25 %, Satz ≤ 2,5 MB. Unabhängige Abnahme aus GLB und PNG: `scripts/verify_surface.py` (Blender).
- Cache: `surface_bake` liest die beiden Spielmodelle, Verträge und QA-Dateien; der Bake-Schlüssel im Vertrag (`surface.bake.key`) hasht
  Positionen, Topologie, UV0/UV1, Eckennormalen, Slots, `channel_map`, Einstellungen und Blender-Version (Tangenten folgen daraus).
  Neue Stufenfelder (`heavy`, `min_contract`) stehen nur gesetzt in der Deklaration, damit bestehende Stufen ihren Schlüssel behalten.
- Ältere Abnehmer: `--contract 3` (und 2, 1) erzeugt weder UV1 noch GLB-Tangenten noch die Stufe `surface_bake`.

## Visier und Zielen (0.12.0 Sightline)

Zulieferung T1, T2, T3, T5 und T6 für Cube Escape 0.72 „Sightline“ (vormals 0.66 „Deadeye“) (`Docs/FIRST_PERSON_EQUIPMENT.md` › 20 im Spielrepo); Einbau:
[UNITY_EINBAU](UNITY_EINBAU.md) › Visier und Zielen.

- **`Socket_Sight` / `Socket_Eye` (T1).** `weapon_kit.world` legt die Anker aus `DESIGNS[key]['sight']` (`sight.py`, reines Python)
  in das Weltmodell; das Ego-Modell übernimmt sie mit der übrigen Waffe. Die Visierlinie ist die der AimIdle-Pose
  (`data/ego_clips.json` › `ads`): bei Kimme/Korn, Reflex, Holo und Energie über die Oberkante der Visierteile plus `eye_above_m`
  (`sight_mode` „top“; Sturmgewehr, Impulsgewehr, Raketenwerfer seit 0.12.0 mit 4 mm über dem Gehäuse statt durch dessen Mitte –
  Befund der Unity-Abnahme Cube Escape 0.72: ein geschlossenes Gehäuse verdeckte die Bildmitte), bei Scopes durch die Rohrmitte
  („center“). `eye_above_m` gilt im Ego-Modell; das Weltmodell bekommt ihn durch `tool_scale` geteilt, so tragen beide dieselbe Linie.
  Der Anker liegt am hinteren Ende des Visiers (Kimme, Rückseite der Optik, Okular), Drehung wie die Waffe (Unity +Z = Blick entlang
  des Laufs, +Y = oben). Scopes (Scharfschützen- und Spurgewehr) haben ein offenes Okular (`ScopeEyepiece` als Ring) mit der Linse
  `ScopeEyeLens` 8 mm innen (Radius 0,9 × Rohrradius, Material Detail); `Socket_Eye` sitzt in ihrer Mitte auf der Linie, ihr Radius im
  Ego-Modell steht als `hold.eye_radius_m` im Vertrag (Cube Escape zeichnet dort sein Scope-Bild). Visierart: `hold.sight_kind` in
  `data/tools.json` (Pistole, Schrotflinte, Raketenwerfer `iron`; Sturmgewehr, Maschinenpistole `reflex`; Impulsgewehr `holo`;
  Fusionsgewehr `energy`; Scharfschützen-, Spurgewehr `scope`). Der Autoren-Kopierordner hat kein `data/`: Regel und Schussbild stehen
  deshalb in `DESIGNS`, `tests/test_weapons.py` hält sie gleich mit `tools.json`, `viewmodels.json` und `ego_clips.json`;
  `first_person.py` prüft den gebauten Anker gegen die Visierlinie der AimIdle-Pose (≤ 0,1 mm, `qa_viewmodel.json` ›
  `ego_clips.sight_socket`).
- **Ereignisse (T2).** Der Use-Clip beider Modelle trägt den Marker `Fire` am Schussbild (`DESIGNS[key]['fire_frame']` =
  `motion.fire_frame` in `data/viewmodels.json`: Bild 14, Fusionsgewehr 46); der Vertrag nennt ihn in `clips[0].events`,
  `action_contract.json` in `events`. Fire und AimFire der Ego-Clips tragen zusätzlich zu `Shot` das gleichbedeutende `Fire` (Bild 0).
- **Prüfung je Clipbild (T6).** `hand_touch_m` jetzt in jedem Bild jedes Ego-Clips (`ego_clips.clips[].hand_touch_max_m`, Grenze
  `touch_tolerance_m` = 8 mm; die Stützhand im Reload-Fenster `detached` zählt nicht); Handgelenk ≤ 55° je Bild wie seit 0.8.0.
- **ADS-Zielpose (T6).** Toolgen rechnet die Zielpose von Cube Escape selbst (Konzept › 5.3): das ganze Ego-Modell in der Ruhepose
  (Bild 1) starr so bewegt, dass `Socket_Sight` auf der Kameraachse im Abstand `hold.eye_distance_m` liegt (Cube-Escape-Profilklassen:
  sidearm 0,30, rifle 0,26, submachine_gun 0,24, shotgun 0,28, sniper 0,22, heavy 0,30, Spurgewehr 0,20 m) und entlang des Blicks
  zeigt, Maßstab 1. Geprüft beim eingestellten Viewmodel-Sichtfeld für 16:9 und 16:10: Visier in der Bildmitte, die drei Greiffinger und
  der Daumen jeder Hand im Bild, proximale Unterarmhälften unter dem Bild (der Stützarm wird wie in den Ziel-Clips nur gemessen,
  Entscheidung des Nutzers), kein sichtbarer Punkt vor der Near-Clip-Ebene. Ergebnis: `qa_viewmodel.json` › `ads_target`, im Spiel-Export
  `qa_game_fps.json` › `ads` mit den Prüfungen `sight_anchors` und `ads_target_pose`. Zusätzlich sucht die Prüfung den Bereich der
  Augenabstände (0,10–0,80 m, 5 mm Schritt), in dem der Bildausschnitt hält (`eye_distance_range_m`). Beim Profilabstand zusätzlich
  (Cube Escape 0.72): der Strahl durch die Bildmitte trifft kein Teil (`centre_clear`; bei Scopes nur die Okularlinse) und das Modell
  reicht höchstens 25 % der Bildhöhe über die Mitte (`model_top_above_centre`). Verbindlich ist: Visier auf der Linie, Anker im Vertrag,
  Bildmitte frei, 25-%-Grenze, ein Bereich existiert. Ob die Finger beim Profilabstand im Bild bleiben (`ads.passed`), ist ein Befund
  für Cube Escape (Werte: [UNITY_EINBAU](UNITY_EINBAU.md) › Visier und Zielen), kein Abbruch.
- **Finger (T5).** Pose-Werte `trigger` und `regrip` (`ego_clips.py`, Daten `defaults.fingers` in `data/ego_clips.json`): in Fire und
  AimFire hebt der Zeigefinger der Griffhand (`Fingers_R_0`, oberste Reihe am Abzug) nach dem Schuss um `trigger_deg` (10°) ab und legt sich
  wieder an (2 Bilder hoch, 4 zurück); in Reload öffnen sich die drei Finger der Stützhand um `regrip_deg` (24°), während sie den
  Handschutz loslässt, und schließen sich beim Nachfassen (`regrip_ramp` um das `detached`-Fenster; Pistole: Stützhand bleibt am Griff,
  daher nur der Abzugfinger). Drehung um das Fingergelenk (lokal Z, Öffnen wie die Zugfinger des Bogens); jedes Clipende in Ruhe.
  Animierte Fingerknoten werden eigene Renderer im Spielmodell (Fusionsgewehr 12, Grenze 14).
- **Charge (T3).** Das Fusionsgewehr hat den Zustands-Loop `FusionRifle_Charge` (18 Bilder, `classes.fusion_rifle.charge`): feines Zittern
  ganzer Perioden, die Spule `Anim_Coil` dreht je Schleife einmal (eine volle Drehung ist die Ruhematrix), Ruhepose an beiden Enden, Ereignis
  `ChargeCycle` bei Bild 0 (je Schleife). Er steht als letzter Clip auf der Zeitleiste, die Framebereiche der übrigen Clips bleiben gleich
  (Test). Clips nur einzelner Waffen nennt `data/ego_clips.json` mit `tools`.
- **Clip-Liste.** Wurzeleigenschaft `ce_action_clips` (JSON-Liste: Use, dann die Ego-Clips in Zeitleistenreihenfolge) neben dem
  bisherigen `ce_action_clip`.

## Viewer-Prüfung und Determinismus (0.12.0)

`viewer/test_viewer.py` rendert jedes Modell, Bewegung und Rücksetzen, Looks, beschädigte Daten und die Seitenleiste.
`viewer/test_determinism.py` (macOS, in `scripts/check_output.sh` nach dem Viewer-Test) rendert dasselbe Bild je Modell achtmal
(`--runs`, Standard 8, Größe 1200×800) und vergleicht jedes mit dem ersten (`magick compare -metric AE -fuzz 2%`); über 1 Pixel
(`--limit`) gilt ein Modell als instabil, darunter liegt nur Antialiasing-Rauschen. Zweck: koplanare Flächen verschiedener Teile
(Z-Fighting) finden, die bei geänderter Zeichenreihenfolge kippen. Befund 16.10.2026: Schaft-Dekor der Schrotflinte (Ego, 57,5 px) –
sichtbar geworden, als `Socket_Sight` als neuer Knoten die Reihenfolge änderte; der Rücksetz-Test allein hätte es als Zufall gezeigt.
`KNOWN_UNSTABLE` in der Datei nennt vorbestehende Fälle mit Pixelwert: sie werden gemeldet (`EXPECTED_UNSTABLE`), nie übersprungen,
und als `KNOWN_NOW_STABLE`, sobald sie halten (dann Eintrag entfernen). Die Auswertung ist ohne Viewer getestet (`tests/test_determinism.py`).
Im Generator gilt: Dekore, Ringe und Linsen stehen ≥ 0,5 mm über der Fläche, auf der sie sitzen (`CoplanarDecorTests`; Netzprüfung
der Weltmodelle in der Sitzung vom 16.10.2026: Mündungsring/-bremse, Scope-Linse/Objektiv, Schaftkern, Abzug, Hahn, Visierpfosten,
Flossen-Dekor, Leuchtstreifen über Lüftungsschlitzen abgehoben; das Impulsgewehr-Paar Zellschacht/Energiezelle hat dasselbe Material
und blieb).

## Cache und Worker

**Stufen.** Die Liste `STAGES` in `generate_tools.py` beschreibt die Bauschritte jedes Werkzeugs deklarativ (Skript, Läufer
Blender oder Python, Argumente, gelesene Dateien, zusätzliche Quellen, Bilder ja/nein, Stufen, QA-Dateien, Viewer-Varianten):
Welt, FPS, Animation, Animations-GIF, Ego-Hände, Ego-Reimport, Spiel-Export (Welt, Ego), Oberflächenkarten (`surface_bake`, standard/full, ab
Vertrag 4; ein Bau wartet auf die gemeinsame Sperre `heavy_lock`); dazu je Viewer-Variante ein Export (`fps_game` und `game` hängen an ihren Spiel-Stufen) und in
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
gemeinsam geändert. Der Befehl läuft in einer eigenen Prozessgruppe; Signale gehen an die ganze Gruppe, die Sperre bleibt,
bis die Gruppe leer ist (auch Enkelprozesse wie Blender halten sie). Der Bericht nennt den Zustand unter `heavy_lock`. `scripts/testplan.py` ordnet geänderte Dateien Bereichen zu
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
aber noch nicht in Unity abgenommen. Die Spielmodelle kommen erst später in Cube Escape; dann entstehen dort die `_Matte`-Varianten
und `M_GlowWarm` aus den Palettenwerten (`ce_status` im Vertrag).

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.

Die Pipeline erfasst die ASTs der Funktionen, die bestimmen, was eine Stufe schreibt (`STAGE_CACHE_FUNCTIONS`), und der
Paketzusammenstellung (`PIPELINE_CACHE_FUNCTIONS`). Render-/Autoren-/Exporterquellen werden vollständig über die
Quellen-Closure erfasst; reine Berichts- und Orchestrierungsänderungen lösen keinen Modell-Neubau aus. Neue Helfer, die
Stufenergebnisse oder Pakete schreiben, gehören in diese Listen. Dieses Verhalten ist mit Cache-Regressionsfällen geprüft.
