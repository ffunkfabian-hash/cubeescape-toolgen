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
`validated_vertical_fov_degrees` (für das gestaltete Ego-Modell; Werte, bei denen der Bildausschnitt für alle geprüften Seitenverhältnisse hält: Portalkanone,
Magnetgreifer, Bogen und Waffen nur 46,69°, Taschenlampe 46,69/50,69°; vor 0.15 Portalkanone und Magnetgreifer 46,69/50,69°, Taschenlampe
bis 54,69° – der schräg nach vorn steigende Griffunterarm aus `arm_pose` kommt bei weiterem Sichtfeld ins Bild) und einem `runtime`-Hinweis; derselbe Block steht als
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
Die Use-Clips der Ego-Werkzeuge tragen seit 0.15 ein Ereignis wie `Fire` der Waffen (`use_event` in `data/viewmodels.json`, Marker in
`first_person.py`): Portalwerfer `Fire` und Taschenlampe `Switch` bei Bild 14 (Stoß der Anwendungsbewegung), Magnetgreifer `Grab` bei
Bild 13 (Backen geschlossen, `animate_magnet_gripper.py`).

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

Die Ego-Clips (ab Bild 101) spielt der Viewer nicht ab; ihren Bewegungsbeleg rendert `scripts/ego_video.py <Ausgabe> <Videoordner>
[--tool …]` (0.15.0) aus dem gestalteten `<Asset>_FPS.blend` durch dessen Viewmodel-Kamera: Eevee, 1280×720, 24 fps, Clipname und
Bild im Stempel, unter `heavy_lock`; dazu `<tool>_contact.png` mit Anfang, Mitte und Ende jedes Clips. Ablage außerhalb des Repos
(`~/Library/Caches/CubeEscapeToolgen/videos/<Version>/`).

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

**Dreiecksbudget.** `data/game_budget.json` nennt je Werkzeug ein LOD0-Budget (seit 0.18 alle +25 %, Entscheidung des Nutzers
20.10.2026; Welt: Portalkanone und Magnetgreifer 10 000, Bogen 7 500, Taschenlampe 6 500; Ego: 20 000 / 20 000 / 17 500 / 15 000;
Waffen und Roboter: [versions/0.18.md](versions/0.18.md)). Ein Modell unter dem Budget wird nicht dezimiert. Nach dem Zusammenführen wird LOD0 mit dem
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

**Umbenennen (0.17.0 Retrace).** Werkzeug-IDs sind dauerhaft; ein Umbenennen ist eine Entscheidung des Nutzers
([ENTSCHEIDUNGEN](ENTSCHEIDUNGEN.md), 19.10.2026: Spurgewehr `scout_rifle` → `trace_rifle`). Der Eintrag behält die alten Namen in
`renamed_from` (`id`, `asset`, `robot`, `clip_stem`, `since`); `game_export.renamed_block` schreibt sie in jeden Vertrag (Welt, Ego, Roboter,
jedes Format) samt `map` alt → neu für den Umzug beim Abnehmer, `generate_tools.py --tool <alte ID>` baut mit Warnung das neue Werkzeug.
Beides endet, sobald ein Werkzeug die alte ID wieder trägt (KG11 Scout-Gewehr): dann `renamed_from` entfernen, `tests/test_rename.py`
erzwingt es. Jeder Vertrag trägt ab 0.17 den Block `minimum_consumer` mit beiden Paketanforderungen getrennt (`first_person_maps_2048`:
Cube Escape 0.96; `renamed_tool_ids`: Cube Escape 0.98 „Recast“ mit der Migration; Konstanten `surface.EGO_MAPS_CONSUMER`,
`game_export.RENAMED_CONSUMER`). Pakete in einem Ausgabeordner, die der Katalog nicht mehr nennt (`scout_rifle/` aus älteren Läufen), bleiben liegen;
`generate_tools.py` nennt sie in einer Warnung (`foreign_packages`). Ordner, Label und Geometrie bleiben; Modell-, Clip- und
Vertragsdateien ändern nur die Namen; die Kartenpixel bleiben bytegleich bis auf einzelne kippende Texel der Roboter-Normalkarten
(siehe Erfahrungen).

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
| 1 Pistole | solar | 0.24 | 6 076 → 3 498 / 1 048 | 2 | 12 808 → 10 996 | 0.0 mm |
| 2 Sturmgewehr | arc | 0.93 | 13 636 → 5 998 / 1 798 | 2 | 27 100 → 13 996 | 0.0 mm / 0.1 mm |
| 3 Impulsgewehr | void | 0.86 | 8 924 → 5 998 / 1 796 | 2 | 22 388 → 13 998 | 0.0 mm / 0.1 mm |
| 4 Schrotflinte | solar | 0.90 | 10 508 → 5 998 / 1 798 | 2 | 23 972 → 13 994 | 0.0 mm / 0.0 mm |
| 5 Scharfschützengewehr | energy | 1.13 | 15 168 → 6 998 / 2 098 | 2 | 28 632 → 14 998 | 0.1 mm / 0.0 mm |
| 6 Maschinenpistole | energy | 0.62 | 10 392 → 4 998 / 1 498 | 2 | 23 856 → 12 996 | 0.0 mm / 0.0 mm |
| 7 Fusionsgewehr | void | 0.96 | 11 524 → 6 996 / 2 096 | 4 | 24 988 → 14 994 | 0.1 mm / 0.0 mm |
| 8 Spurgewehr | arc | 1.04 | 13 784 → 5 998 / 1 798 | 2 | 27 248 → 13 998 | 0.0 mm / 0.2 mm |
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
- Ego-Werkzeuge (0.15.0, Wunsch Cube Escape 0.85: in CE gemessen 82°/84°/89° in Ruhe, CE kann flache Knoten unter `Viewmodel_Motion`
  nicht nachstellen): Griffarm mit `forearm` absolut, ≈ 35–40° steigend und zur Knöchelrichtung gedreht (Portalwerfer
  [0,454, −0,617, 0,643], Magnetgreifer [0,4, −0,653, 0,643], Taschenlampe [0,436, −0,693, 0,574], `upper` wie die Waffen); die Stützarme
  von Portalwerfer und Magnetgreifer haben nur `max_wrist_bend_degrees` (eine `arm_pose` ohne Unterarmangabe behält Schulter und
  Ellbogenebene aus `arm` und setzt nur die Grenze; ihr Winkel lag schon bei 41/46°). Gemessen über alle Bilder: Portalwerfer 45,6/45,2°,
  Magnetgreifer 48,7/50,0°, Taschenlampe 46,7° (rechts/links). Gewählt aus einer Abtastung der Unterarmrichtungen (Winkel ≤ 45° in Ruhe,
  Ellbogen auf der Handflächenseite mit Abstand, proximale Hälfte bei 1,7× unter dem Bildrand), mit der kleinsten Abweichung von der alten
  Richtung. Mit dem Unterarm ändert sich die Achse von `twist` (vorher fast senkrecht = Gieren, jetzt nach vorn = Kanten wie bei den Waffen).
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
- Ego-Werkzeuge (0.15.0): `Inspect_B` (kantet entgegen `Inspect_A`, `except_tools` nimmt den Bogen aus), Klassen `portal_emitter`,
  `magnet_gripper`, `flashlight` mit kleineren Drehungen (Inspect 18°/−14°, Sprint des Portalwerfers 10° und 1,5 cm statt 14° und 3 cm:
  sonst verdeckt `SM_PG_UpperArmSpine` das Fadenkreuz) und deutlichem `lowered` (1 cm tiefer, 5° Mündung hoch, 12° Kanten). Gemessen
  `qa_viewmodel.json` › `ego_clips.lowered`: `Socket_Hand` sinkt 14,0/14,0/17,2 mm (vorher ≈ 2 mm; Waffen 1–4 mm in derselben Messung),
  Weg 21–25 mm. Prüfung `verify_output.py`: Senkung ≥ 6 mm, Handgelenk ≤ 55° je Clip und Arm, Use-Ereignis, Inspect_B.
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
  eigenes Raster (Texelmitte, erstes Dreieck gewinnt, Dilatation in fester Nachbarreihenfolge: 8 Schritte bei 512², 16 bei 2048² – `dilation_at`); Cycles auf der CPU mit Seed 0:
  AO-Bake (Welt 16, Ego 32 Samples, 0,08 m), EMIT-Bake für Kante/oben/Höhe und NORMAL-Bake (Tangentenraum UV1) mit je 4 Samples. Kante =
  12 × (1 − Bevel-Normale · Schattierungsnormale), Bevel 4 mm, mal Konvexität aus lokalem AO (16 mm; unter 0,35 Falte = 0, über 0,7 voll).
  `render_init`-Handler von `run_asset.py` werden geleert, damit Samples und Gerät der Teststufe nicht greifen (standard = full).
  PNG-Schreiber eigen (`png_encode`: Filter None/Sub/Up, zlib 9, nur IHDR/IDAT/IEND). Laufzeit Pistole bei Ego 1024²: Welt 5 s, Ego 42 s (AO 31 s), 4 Threads;
  bei Ego 2048² (0.16) viermal so viele Texel: Stufe `surface_bake` 100–460 s je Werkzeug (Pistole 332 s; Mac 18.10.2026, zwei Worker gleichzeitig, andere Sitzungen liefen,
  kein Zeitband).
- QA `qa_surface.json`: `channel_map`, `uv1_shared` (Hash der Welt-UV1 in beiden Exporten gleich), je Modell `uv1_<variant>` (Layout wie oben)
  und `maps_<variant>`: Gewichte one-hot 255 in den Inseln, nichts jenseits der Dilatation, jeder vorkommende Kanal hat Texel, AO-Mittel
  0,3–0,95, Kantenanteil (G > 0,5) 2–25 %, Satz ≤ 2,5 MB (512²) bzw. ≤ 10 MB (2048², `set_bytes_limit`). Unabhängige Abnahme aus GLB und PNG:
  `scripts/verify_surface.py` (Blender); Golden-Einträge mit `stale`-Markierung (0.16) sind rot, bis `--update-golden` sie neu schreibt.
- Cache: `surface_bake` liest die beiden Spielmodelle, Verträge und QA-Dateien; der Bake-Schlüssel im Vertrag (`surface.bake.key`) hasht
  Positionen, Topologie, UV0/UV1, Eckennormalen, Slots, `channel_map`, Einstellungen und Blender-Version (Tangenten folgen daraus).
  Neue Stufenfelder (`heavy`, `min_contract`) stehen nur gesetzt in der Deklaration, damit bestehende Stufen ihren Schlüssel behalten.
- Ältere Abnehmer: `--contract 3` (und 2, 1) erzeugt weder UV1 noch GLB-Tangenten noch die Stufe `surface_bake`.
- **Auflösungen (0.16 Finegrain):** `MAP_RESOLUTION` Welt 512², Roboter-Variante 512², Ego **2048²** (Entscheidung des Nutzers 18.10.2026; Cube Escape 0.96
  streamt die volle Größe nur für das gehaltene Gerät). Der UV1-Atlas ist für alle Auflösungen derselbe, deshalb sind alle Abstände UV-Größen:
  Randregel 4/1024 (`margin_px_at`: 2 px bei 512, 8 px bei 2048), Packabstand 8/1024, freier Rand 16/1024, Dilatation 8 px bei 512 und 16 px bei 2048
  (= 8/1024 wie bisher bei 1024, damit die Mip-Stufen den Rand genauso spät verlieren; `CORNER_CHECKS` prüft die freie Ecke je Karte: die Dilatation (in UV-Raum) darf das Eck-Texel
  der Karte nicht erreichen, 16 px bei 1024 für Welt/Roboter, 8 px für Ego; Band 16 + Packabstand 8 = 24 px trägt genau das, mehr bräuchte ein breiteres `RESERVED_LOW`, also ein neues UV1-Layout). Bei 2048 berühren sich die Dilatationen benachbarter Inseln nicht mehr (Abstand 16 px gepackt, 16 px Dilatation je Seite überlappen
  sich nur im Gleichstand), bei 1024 lagen 8 + 8 px Dilatation in 8 px Abstand. Bake-Schlüssel enthält `resolution` und `dilation_px` – Welt und
  Roboter bleiben bytegleich, nur die Ego-Sätze werden neu gebacken.


### Relief, Decals und Rezept der Waffen (0.13.0 Enamel)

Zielbild: Cube Escape `Docs/EQUIPMENT.md` › Zielbild › Texturen 1–9 (Konzeptblatt des Nutzers). Toolgen liefert nur, was die Geometrie
kennt; Farbe, Werkstoffart, Glätte, Abnutzung, Schmutz, Kratzer, Rauschen und Glühen rechnet Cube Escape (`SurfaceGenerator1`, Shader).

- **Teil je Dreieck:** `surface_bake` sucht für jedes LOD0-Dreieck (Mittelpunkt) das nächste Dreieck desselben Kanals unter den
  `SM_PG_*`-Teilen des Quellmodells (`<asset>.blend` bzw. `<asset>_FPS.blend`, BVH), beides im Werkzeugrahmen von `Socket_Hand` bei Bild 1.
  Grenze 1,5 mm (`PART_MATCH_MM`); gemessen 0 ungelabelte Dreiecke, höchstens 0,39 mm Abstand (Dezimierung).
- **Relief** (`data/surface_recipes.json` › `weapons.<id>.relief`, `toolgen/surface_relief.py`): Schlüssel = Glob auf den Teilnamen ohne
  `SM_PG_` oder `@<Kanal>`, erster Treffer gewinnt; Wert = ein Muster oder eine Liste (Summe der Stärken ≤ 1). Muster als Shader-Nodes über
  der Position im Werkzeugrahmen (mm; im Ego geteilt durch `tool_scale`, damit Welt und Ego gleich aussehen): `knurl` (Rautenrändel, zwei
  Kosinus-Scharen ±45°), `grooves` (Rillen), `lamellae` (Rippen), `seams` (Panel-Fugen, eingedrückt), `brushed` (gestreckte Noise längs
  der Richtung), `grain` (Keramik-/Gusskorn). Höhe 0..1 × Stärke treibt einen Bump-Node mit 0,3 mm Abstand (`limits.max_height_mm`) auf der
  Bevel-Normale, je Fläche über das Attribut `ce_relief` gewählt. Der Bump hängt erst vor dem NORMAL-Bake am Material (AO und EMIT sehen ihn
  nie: Fields bytegleich) und ändert weder Silhouette noch Kollision. NORMAL-Bake mit Relief 16 Samples (`RELIEF_SAMPLES`), sonst 4.
- **Decals** (`data/decals.json`, `toolgen/decals.py`, Anker `DECALS` in `scripts/tool_assets/weapon_designs.py`): einfarbige Masken
  (Linien, Flächen, Kreise, Text in der mitgelieferten Strichschrift `glyphs`, kein Systemfont), ImageMagick zeichnet sie geglättet und
  schneidet bei 50 % (PGM, ein Thread; IM 6 und 7 nur an Randpixeln verschieden, Golden-Masken `tests/golden/decals`). Anker: Teil,
  Fläche (`+x` = die Seite, die die Ego-Kamera sieht), Rechteck als Anteil der Teil-Box auf dieser Fläche (u nach rechts, v nach oben,
  von außen gesehen), Bild, Kanal, Drehung. Box-Projektion auf die Texel des Teils, deren Fläche zu mindestens 0,7 zur Achse zeigt
  (baryzentrisch aus dem Dreiecksraster); der Decal-Texel überschreibt im Kanalraster den Kanal **vor** der Dilatation, die Gewichte
  bleiben one-hot 255. QA je Decal in `qa_surface.json` › `design_<variante>`: nur Zielteil (`foreign_texels` 0), genau eine UV-Insel
  (keine Naht), 0,5–6 % der Insel, Seitenverhältnis Rechteck/Bild ≤ 25 %.
- **Rezept** (`surface.recipe`, siehe [UNITY_EINBAU](UNITY_EINBAU.md) › Maskenkarten): Palette, Leuchtfarbe/Element des Blatts, Abnutzung
  (subtil 0,2, mittel 0,5, stark 0,8), je Kanal Werkstoffart und Glätte (≤ 0,45 = 1 − `finish.min_roughness`), Decals mit Texelzahl, Relief.
  `glow.element` folgt der Leuchtfarbe des Blatts, `model_element` dem Modell (`weapon_designs.py`); seit 0.13 gleich, weil die Modelle
  die Farbe des Blatts übernehmen (Entscheidung des Nutzers 17.10.2026).
- **Bake-Schlüssel:** `BAKE_SCHEMA` 2; `settings.design` (Relief, Decal-Anker, Hash des Katalogs, ImageMagick-Version, Samples,
  `pattern_scale`) gehört zum Schlüssel; die Stufe liest zusätzlich die Quellmodelle und hat `magick` im Programmschlüssel.
  Ohne Rezept und Decals (Portalwerfer, Magnetgreifer, Taschenlampe, Bogen) bleiben alle Karten bytegleich zu 0.12.
- **Abnahme:** `verify_surface.py` zählt Decal-Texel getrennt (höchstens die im Rezept gemeldeten, nur in Decal-Kanälen) und vergleicht die
  Karten der Waffen mit `tests/golden/surface/manifest.json` (sha256 aller 72 Karten, keine Referenzbilder – Entscheidung des Nutzers;
  jede geänderte Karte fällt durch, bis sie mit `--update-golden` bestätigt ist). Determinismus: `verify_surface.py --determinism` backt bei 1 und 8 Threads.
- **Sichtprüfung ohne Unity:** `blender -b --factory-startup --python scripts/surface_preview.py -- <output> [--tool <id>]` →
  `<output>/Previews/surface_<id>.png` (Seite +x, Dreiviertel, Ego-Ausschnitt durch die Viewmodel-Kamera, je Modell Regionen farbcodiert,
  Fields, Normal) und `surface_contact.png`. Das Vorschau-Material ahmt den Masken-Modus nur nach (Palette des Rezepts, Kantenabnutzung aus
  Fields G × Abnutzung, AO, Normalkarte, Glühen; Eevee, nicht bytegleich, kein Vertrag).

## Roboter-Variante der Waffen (0.14.0 Fieldfit)

Cube Escape hält in der Außenansicht das **Weltmodell** in der Roboterhand (`HeldToolModels`) und skaliert es seit CE 0.82 je
Waffe (`heldScale`). Skalieren löst zwei Befunde nicht (CE `Docs/versions/0.82.md` › Befunde): Die Stützhand erreicht bei den
acht Unterhand-Waffen `Socket_SupportHand` nicht (0,30–0,43 m daneben; erreichbar ist höchstens etwa 0,10 m vor `Socket_Hand`), und
die Gewehre wirken neben dem rundlichen Roboter schlank. Deshalb gibt es je Gewehr ein **zusätzliches** Weltmodell `<Asset>_Robot`
(`tools.json` › `robot`); Ego-Modell, Clips, ADS und das bisherige Weltmodell bleiben unverändert, die Pistole hat keine Variante.

**Erzeugung als Verformung des Designs** (`weapon_designs.py` › `ROBOT`, `robot_fit`, `robot_point`; `weapon_kit.apply_robot_fit`).
Das Weltmodell wird wie immer gebaut und danach in einem Schritt verformt; Teile, Namen, Anker, Visierregel, Use-Clip, Decals und
Rezepte sind dieselben, spätere Änderungen eines Designs (Lenswork-Visiere, Enamel-Rezepte) kommen ohne Zusatzarbeit in beiden
Fassungen an. Je Waffe:

- **Querschnitt** `cross`: x und z wachsen um diesen Faktor um `Socket_Hand` (Lauf ≥ 3 cm, Gehäuse ≥ 8 cm hoch, helle Flächen größer).
- **Bohrungsachse** `knots`: y läuft stückweise linear durch Stützpunkte (Lebensgröße → Roboter). Die Griffzone ±0,04 m behält genau
  die Steigung `cross`, so bleibt die Griffneigung (`hold.grip_tilt_degrees`) exakt; der Schaft wird an den Griff gedrückt (Ende
  0,11 m hinter `Socket_Hand`), die Länge ist die CE-„Länge in der Hand“ (danach `heldScale` 1,0). Die Abbildung ist monoton:
  Teile, die getrennt waren, bleiben getrennt.
- **Stützhand** `support`/`support_part`: `Socket_SupportHand` rückt vor der Verformung an Magazinschacht, Gehäusefront oder
  Rohrunterseite und liegt danach 0,09 m vor `Socket_Hand`, etwa auf Griffhöhe.
- **Energiezellen** (Kern, Kappen, Käfig einer `energy_cell`) werden längs um ihre gemeinsame Mitte höchstens auf
  `RIGID_SLOPE` 0,35 gestaucht: ihre 2–3-mm-Stufen blieben sonst im Schaft unter 0,5 mm und flackerten (Viewer-Determinismus,
  Spurgewehr 1,4–1,6 px). Beim Fusionsgewehr liegt die Knickstelle so, dass der Visierpfosten (0,6 mm vor einer Schienenkerbe) fast
  1:1 bleibt; beim Spurgewehr bleibt der Handschutz 1:1 (Lüftungsschlitz und Leuchtstreifen enden 1 mm auseinander, bei Steigung
  0,82 flackerte die Kante weiter, 2 von 15 Bildern), Lauf und Mündung tragen die Stauchung (0,62). `CoplanarRobotTests` prüft die
  Dekor-Regel (≥ 0,5 mm) auf den verformten Flächen; der Viewer-Determinismus ist die zweite Hälfte der Prüfung.
- Use-Clip: Wege längs der Achse über die abgebildete verschobene Lage des Drehpunkts (exakt über Knickstellen), quer mit `cross`;
  Drehungen unverändert.
  Visierlinie: `above_m` × `cross`. Wurzel-Properties `ce_variant = robot`, `ce_held_scale = 1.0`.

| Waffe | Länge (m) | `cross` | Stützhand an | vor / Abstand (m) | Schaft hinter (m) | Lauf (cm) | Gehäuse (cm) | Dreiecke Quelle → LOD0 / LOD1 | Boxen |
|---|---|---|---|---|---|---|---|---|---|
| Sturmgewehr | 0,67 | 1,50 | `MagWell` | 0,090 / 0,108 | 0,11 | 3,3 (`Barrel`) | 12,6 | 17 240 → 11 998 / 3 598 | 8 |
| Impulsgewehr | 0,66 | 1,55 | `Chassis` | 0,090 / 0,105 | 0,11 | 3,1 (`Barrel`) | 23,6 | 12 748 → 11 998 / 3 596 | 7 |
| Schrotflinte | 0,67 | 1,35 | `Receiver` | 0,090 / 0,102 | 0,11 | 8,5 (`BarrelShroud`) | 8,4 | 14 920 → 11 998 / 3 595 | 4 |
| Scharfschützengewehr | 0,73 | 1,45 | `Chassis` | 0,090 / 0,104 | 0,11 | 3,0 (`Barrel`) | 8,3 | 20 860 → 11 998 / 3 598 | 8 |
| Maschinenpistole | 0,52 | 1,35 | `Body` | 0,090 / 0,098 | 0,11 | 7,6 (`Shroud`) | 8,2 | 12 900 → 11 998 / 3 598 | 7 |
| Fusionsgewehr | 0,67 | 1,35 | `Handguard` | 0,089 / 0,104 | 0,11 | 5,9 (`Core`) | 8,5 | 13 864 → 11 996 / 3 594 | 10 |
| Spurgewehr | 0,69 | 1,60 | `MagWell` | 0,090 / 0,107 | 0,11 | 3,0 (`Barrel`) | 9,1 | 17 028 → 11 998 / 3 598 | 8 |
| Raketenwerfer | 0,65 | 1,15 | `Tube` | 0,090 / 0,101 | 0,11 | 14,3 (`Tube`) | 14,3 | 15 352 → 11 998 / 3 596 | 4 |

Die Maschinenpistole führt ihre Trommel mit der Steigung `cross` (bleibt rund); ihr „Lauf“ ist die Laufhülle `Shroud` (der kurze
Laufstummel davor misst 2,4 cm). Das Gehäuse des Impulsgewehrs ist das ganze Bullpup-Chassis.

**Stufen** (am Ende von `STAGES`, nur Vertrag 4, `when: robot`; keine frühere Stufe liest Roboterdateien): `robot` (Weltskript mit
`--variant robot`: Bau, Verformung, Use-Clip, Export, `qa_geometry_robot.json` mit Block `robot` (Maße, Grenzen, Stützpunkte,
Lebensgröße-Grenzen), `qa_animation_robot.json`, Bilder `robot_*.png`), `game_robot` (`game_export.py --robot`: `<Asset>_Robot_Game.*`,
`unity_contract_robot.json`, `qa_game_robot.json`, `preview_game_robot.png`; Budget `game_budget.json` › `robot`, 12 000) und
`surface_bake_robot` (standard/full, `heavy_lock`: eigene Karten 512², eigenes UV1-Atlas, `qa_surface_robot.json`; Relief folgt den
verformten Teilen, Muster in Millimetern wie am Weltmodell). **Decals** (`decals.refit_rect`, `surface_bake.robot_refit`): die
Rechtecke der Designs sind Bruchteile der Teil-Box und kämen verzerrt an; für die Variante folgt die Mitte der Verformung, die Größe
wächst gleichmäßig um `cross` (Seitenverhältnis in mm bleibt), in gestauchten Zonen rückt das Decal erst nach innen und schrumpft dann.
Liegt es auf einer UV-Naht des eigenen Atlas, gelten der Reihe nach kleinere Vergrößerung und feste kleine Verschiebungen
(`ROBOT_DECAL_SHIFTS`); der erste bestehende Kandidat zählt (`qa_surface_robot.json` › `decals[].candidate`, `rect`; Vertrag
`surface.recipe.decals[].rect`). Gemessen 17.10.: 14 von 15 Decals mit voller Vergrößerung, die Warnstreifen der Schrotflinte ohne
Vergrößerung (Kandidat 2, Naht des eigenen Atlas); Kartensatz je Variante 0,70–0,74 MB. Viewer-Varianten „Roboter-Weltmodell“ (`robot`) und
„Roboter-Spielmodell“ (`robot_game`); Reimport-Prüfung `roundtrip_robot` (standard/full).

**Prüfung.** `weapon_kit.robot_report` bricht den Bau ab, wenn eine Grenze verletzt ist (`ROBOT_LIMITS`: Länge ± 5 mm, Stützhand
höchstens 0,10 m vor, Schaft höchstens 0,12 m hinter, Lauf ≥ 3 cm, Gehäuse ≥ 8 cm, `Socket_Muzzle` vorn); `tests/test_robot_variant.py`
rechnet dieselben Maße aus den Primitiven nach und prüft Griffneigung, Stufen und Namen; `verify_output.py` prüft Vertrag, Anker, Hold,
Clip, Kollision, Budget und Karten; `scripts/compare_models.py <alt> <neu>` belegt, dass die bestehenden Modelle (GLB, Viewer-Daten)
bytegleich bleiben. Sichtprüfung: `blender -b --factory-startup --python scripts/robot_preview.py -- <Ausgabe>` →
`Previews/robot_variant.png` (Variante neben einer Roboter-Referenz: Schulter 0,82 m, Brustfront, Arm 0,42 m, Fäuste 0,09 m; Haltung nur
fürs Bild) und `robot_contact.png` (altes Weltmodell mit CE-`heldScale` gegen die Variante, Seite/oben/hinten, ein Maßstab).

## Konzeptmodelle (0.18.0 Bedrock, TG-A)

Seit 0.18 kann eine Waffe ihre Geometrie aus einem Konzeptblatt von cubeescape-formgen beziehen (geometry-spec 1, `KXnn.geo.json`;
Format: formgen `claude/docs/geometry-spec.md`). Pilot: Sturmgewehr = KG02 „Kantenläufer“, Variante G (formgen-Plan Entscheidung 1).
Alles nach der Geometrie (Ego-Kopie, Clips, Ego-Hände, Spiel-Export, Karten, Roboter-Variante) ist der bestehende Waffenweg.

- **Leseweg.** `scripts/import_concepts.py` übernimmt einzelne Blätter aus einer lokalen Kopie des Release-Zips (`gh release download
  claude-vX -R ffunkfabian-hash/cubeescape-formgen -p 'claude-geo-*.zip'`) nach `data/concepts/` und schreibt `provenance.json`:
  je Release Repository, Commit, Zip-Name, Zip-sha256 und alle Datei-Hashes aus formgen `claude/tests/golden.json` › `geo`; je importiertem
  Blatt sein Release, sha256, Bytes, `toolgen_id`, Variante, Datum (Blätter verschiedener Releases nebeneinander, z. B. KG02 aus einem
  neueren). Geprüft wird vor dem Schreiben, für alle angeforderten Blätter: Zip-sha256, Datei-sha256 gegen die Golden-Liste,
  `format`/`format_version`. `--check` prüft den Ordner. Der Bau greift nie aufs Netz: `generate_tools.py` kopiert `data/concepts/` als
  `concepts/` in die Autorenkopie und nimmt die Dateien in die Quellen-Closure (`weapon_designs.py` nennt das Blatt, `concept_spec.py`
  die Herkunftsdatei) – aber nur beim Werkzeug, das aus dem Blatt gebaut wird (`concept_sources`), und von `provenance.json` und
  `corrections.json` zählt nur dessen eigener Eintrag (`source_digest`). Ein weiterer Import oder eine Korrektur an einem anderen Blatt
  ändert also keinen fremden Stufenschlüssel; `.blend`-Dateien sind nicht bytegleich zwischen Bauten, ein unnötiger Weltbau würde sonst
  bis zum Karten-Bake durchschlagen (Codex-Befund 20.10.2026). Stand: KG02 aus claude-v0.15 (formgen 143e542, mit Ladehebel p32).
- **Lader** (`scripts/tool_assets/concept_spec.py`, reines Python): verweigert eine Datei, deren sha256 nicht der Herkunft entspricht,
  oder ein anderes Format; unbekannte Felder werden ignoriert. `plan()` liefert die Netze mit Toolgens Regeln:
  Visierglas wird nicht gebaut (Entscheidung des Nutzers 20.10.2026, Weg A „offen“; das Glas des Specs ist eine gewollte Doppelfläche).
  Offene Teile (nicht jede Kante an genau zwei Flächen, z. B. die vier Flächen eines Visierrahmens) werden mit den Teilen gleichen Aussehens
  (Bezeichnung, Kanal, Material, Leuchten, Visier, Knoten) zu einem geschlossenen Netz verschweißt (Name des ersten Teils, `ids` aller).
  Koplanare Flächen (Toolgen-Regel: verschiedene Netze, Normalen ≤ 1°, Abstand < 0,5 mm, Überdeckung ≥ 1 mm²) setzt der Lader beim kleineren
  Netz um 0,5 mm entlang der Normale zurück (KG02: p05 gegen p04, 6 Flächen, wie der Spec-Befund). Fasen nach Teilgröße
  (3,5 % der kleinsten Ausdehnung, 0,5–2 mm, höchstens 40 % davon; Leuchtteile ohne), 2 Segmente, auf Kanten > 0,7 rad an einer harten Fläche.
  Ein Visierteil, dessen Hülle die Fenstermitte enthält, bekommt `ce_collision` „none“: seine Kollisionsbox würde das Fenster schließen
  (Öffnungsprobe an `Socket_Reticle` im Spiel-Export).
- **Bau** (`concept_kit.py`, Blender): ein Objekt je Netz `SM_PG_<Bezeichnung>_<id>`, Ursprung in der Hüllmitte, Material über den
  Kanal (`MT_Primary` → Primary … `MT_Emission` → Display, `MT_Energy` → Elementleuchten), Glättung nach `hard`, n-Ecken als Dreiecke
  (Tangenten auf UV1 brauchen Drei- und Vierecke; ein Modell unter dem Budget wird nicht dezimiert), UV wie die Kit-Primitive.
  Das Magazin hängt unter `Anim_Magazine` (Nachladeclip), Teile mit `moving.toolgen_node` hängen unter diesem Knoten (KG02:
  Ladehebel p32 unter `Anim_Bolt`), Use-Clip-Knoten ohne Teil wären leere Knoten (`empty_clip_nodes` in der QA). Die Design-Funktion ruft `k.concept(...)`
  (`weapon_designs.concept_build`), Ersatz-Kits der Tests bekommen dieselben Teile über `concept_spec.layout()`.
- **Anker.** `Socket_Hand`, `Socket_Muzzle`, `Socket_CenterOfMass` aus `anchors`; `Socket_Sight` aus `sight.socket_sight_rear_m`
  (`anchors.Socket_Sight` des Specs ist die Schienenoberkante), gesetzt auf der AimIdle-Linie durch die Mitte des Fensterrahmens
  (`sight_mode` „center“) und gegen den Spec geprüft (≤ 0,5 mm, `qa_geometry.json` › `sight.concept`); `Socket_Reticle` neu (Fenstermitte,
  additiv, `hold.reticle_socket`); `Socket_Eye` nur bei Zielfernrohren. `Socket_SupportHand` und alle übrigen: Spec-Anker, außer
  `data/concepts/corrections.json` nennt eine **benannte Toolgen-Korrektur** (je Blatt und Anker: Spec-Wert, Toolgen-Wert, Grund,
  Entscheidung). Der Lader wendet sie an und verweigert sie, sobald der Spec einen anderen Wert trägt (erneute Prüfung nötig).
  KG02: `Socket_SupportHand` 10 cm weiter hinten auf dem Handschutz p11 (y −0,25 statt −0,351, gleiche Höhe), weil am Spec-Anker keine
  Ego-Haltung die Bildregel erfüllt (Entscheidung des Nutzers 20.10.2026). Wiederholt sich das bei weiteren Gewehren, zieht formgen die
  Anker gesammelt nach.
- **Haltung aus dem Blatt.** `hold.grip_tilt_degrees` = `grip.grip_tilt_degrees` (KG02 10,27°), `hold.sight_kind` = Visierart des
  Specs (holo), `grip_radius` = halbe Breite, halbe Tiefe des Griffquerschnitts, `support_radius` = halbe Höhe, halbe Breite des
  Handschutzquerschnitts (`concept_spec.hold`, Test gegen `data/viewmodels.json`).
- **Vertrag** 4 additiv: Block `concept` (Blatt, Release, Hashes, Fenster offen) und `minimum_consumer.concept_models` (CE-Version „offen“,
  CE-A; älteres Modell: `v0.17.2`).

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
  `data/tools.json` (Pistole, Schrotflinte, Raketenwerfer `iron`; Maschinenpistole `reflex`; Impulsgewehr und seit 0.18 das
  Sturmgewehr (KG02, Linie durch das offene Fenster, › Konzeptmodelle) `holo`;
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

Blender-Reimport und SceneKit-Bilder belegen keine Unity- oder Gameplay-Abnahme. Die Drehung der Anker-Leerobjekte ist kein
Vertrag (FBX: Blender-Achsen bleiben im Import, Befund Cube Escape 0.75); Achsen aus `hold.muzzle_axis`/`grip_axis`. Der Blender-Reimport
kann das nicht prüfen (er macht die Achsenumrechnung rückgängig), nur Cube Escapes Anker-Test in Unity.
`*_FPS_Game.glb` ist zwischen zwei Läufen derselben Quellen nicht immer bytegleich (gemessen 0.13: eine Tangente um 1e-4, gegenüber dem
0.12-Lauf die Handnetze in anderer Reihenfolge); Werkzeug-UV1, Geometrie-QA und die Maskenkarten sind davon nicht betroffen (der Bake
entfernt die Hände). Grund nicht festgehalten. Ebenso `*_Robot_Game.glb` (gemessen 0.15: je Waffe zwei Werte um 1e-4 verschieden, wenn in
einem anderen Ordner gebaut, im selben Ordner gleich; JSON-Teil gleich). `compare_models.py` führt beide getrennt. Anker unter anderem Socket_Hand,
Socket_Muzzle, beim Bogen Socket_Nock/Socket_ArrowTip, beim Magnetgreifer Socket_Grab. Ältere Contract-Zielnamen
sind keine geprüfte Unity-Montage. Der unveränderte Magnetgreifer-Player behält seinen historischen Quellhash und die
Kompilierungsherkunft. Licht, Schussereignis, Projektil und Greifphysik werden beim Einbau separat geprüft.
Roboter-Variante (0.14): die Passung am echten Roboter (Handfläche zu `Socket_SupportHand`, Schaft an der Schulter) prüft erst Cube
Escape (`HeldWeaponReelTests`); die Roboter-Referenz in `Previews/robot_variant.png` ist eine angenommene Haltung. Die Verformung
staucht den Schaft (Steigung 0,13–0,4) samt seiner Kleinteile (Zellenfenster, Okular der Zielfernrohre) zu einer Schulterplatte und
den Bereich zwischen Abzug und Stützhand (0,45–0,6); Rundteile quer zur Achse werden dort oval. Der `hold`-Block ist absichtlich
derselbe wie im Weltmodell; sein Satz „`Socket_SupportHand` in der Mitte des Handschutzes“ gilt für die Variante nicht (Block `robot`).
FBX und .blend tragen Exportzeit und den absoluten Pfad des Bauordners, Bytegleichheit gilt nur für GLB und Viewer-Daten.
Der Cycles-Normal-Bake ist zwischen Läufen nicht immer bitgleich: Bei den Roboter-Varianten von Spur- und Scharfschützengewehr kippt je ein
Texel um eine Stufe (0.15.1); das Golden führt dafür belegte Ausweich-Hashes (`tests/golden/surface/manifest.json` › `alternates`).
Der Spiel-Export (Renderer, LODGroup, Kollision, Clip, Materialien) und die Ego-Kamera sind in Blender, GLB und FBX geprüft,
aber noch nicht in Unity abgenommen. Die Spielmodelle kommen erst später in Cube Escape; dann entstehen dort die `_Matte`-Varianten
und `M_GlowWarm` aus den Palettenwerten (`ce_status` im Vertrag).

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.

Die Pipeline erfasst die ASTs der Funktionen, die bestimmen, was eine Stufe schreibt (`STAGE_CACHE_FUNCTIONS`), und der
Paketzusammenstellung (`PIPELINE_CACHE_FUNCTIONS`). Render-/Autoren-/Exporterquellen werden vollständig über die
Quellen-Closure erfasst; reine Berichts- und Orchestrierungsänderungen lösen keinen Modell-Neubau aus. Neue Helfer, die
Stufenergebnisse oder Pakete schreiben, gehören in diese Listen. Dieses Verhalten ist mit Cache-Regressionsfällen geprüft.

## Erfahrungen

Format: Datum · Thema – Lehre in 1–3 Sätzen. Beleg. Gilt auch für.

- 20.10.2026 · Modell unter dem Dreiecksbudget – Bis 0.17 lag jedes Spielmodell über dem Budget und wurde dezimiert; die Dezimierung hat
  nebenbei n-Ecken trianguliert und die UV-Markierungen (Render, aktiv) neu gesetzt, die das Zusammenfügen in ein leeres Netz verliert.
  Das erste Modell darunter (KG02, 5 872 von 7 000) zeigte beides: glTF ohne Tangenten, `uv1_layers` rot; nach dem Anheben aller
  Budgets um 25 % auch Ego-Hände/-Arme und Roboter-Gehäuse. `reduce_to_budget` trianguliert und setzt die Markierungen jetzt selbst,
  wenn nichts dezimiert wird. Beleg: 0.18 Bedrock (`reduce_to_budget`, `concept_kit.make`). Gilt auch für: jede Budgetänderung, jede
  neue Geometriequelle, kleine Werkzeuge.
- 20.10.2026 · Anker aus einem Konzeptblatt – Ein Anker, der als Teilmitte gemessen ist (Stützhand = Mitte des Handschutzes), ist kein
  Haltungspunkt: am KG02-Anker (35 cm vor dem Griff, 12 cm hoch) gibt es keine Ego-Haltung mit Griffhand im Bild und Stützarm draußen.
  Erst die Ego-Prüfung laufen lassen, dann über Lage, Unterarm und Anker entscheiden (Nutzer). Beleg: 0.18, `data/concepts/corrections.json`. Gilt auch für:
  die übrigen acht Konzeptwaffen.
- 20.10.2026 · Kollision von Ringen – Eine Hüllbox je Teil schließt jede Öffnung, die das Teil umrahmt (Visierfenster). Öffnungen bekommen
  eine Probe im Spiel-Export, umrahmende Teile keinen eigenen Kollider. Beleg: 0.18, `OPENING_PROBES`, `ce_collision`.

- 19.10.2026 · Golden und Versionsnummer – Schon die geänderte Versionszeichenkette in `version.py` verschiebt einzelne Tangenten der
  Spiel-GLB um 1e-4 und kippt im Cycles-Normal-Bake einen Texel einer Roboter-Normalkarte um eine Stufe, reproduzierbar je Zeichenkette.
  Ein solcher Golden-Fehler bei unveränderter Geometrie ist kein Inhaltsfehler: mit einem frischen Bau des alten Tags gegenprüfen, dann den
  Hash als `alternates` eintragen, nie das Golden blind neu schreiben. Beleg: 0.17 Retrace (SMG, `docs/versions/0.17.md` › Befunde).
  Gilt auch für: jede Version, deren Bake-Schlüssel sich ändert.
- 19.10.2026 · Werkzeug umbenennen – IDs, Asset- und Clipnamen hängen an Daten (`tools.json`, `viewmodels.json`, `ego_clips.json`,
  `surface_recipes.json`, `game_budget.json`), Golden-Manifest, Tests und Design-Funktionen; der Generator leitet keine Zufallswerte aus
  Namen ab, deshalb bleiben Kartenpixel gleich. Alte Namen nicht als zweites Werkzeug weiterbauen, sondern im Vertrag als `renamed_from`
  mitliefern, damit der Abnehmer seine Dateien samt GUID verschieben kann. Beleg: 0.17 Retrace (`tests/test_rename.py`). Gilt auch für:
  Robogen-/Cubegen-Teile-IDs.
- 18.10.2026 · Kartenauflösung ändern – Alles, was in Pixeln formuliert ist (Randregel, Packabstand, freier Rand, Dilatation, Satzgrenze), ist in
  Wahrheit eine UV-Größe oder eine Größe je Karte; vor dem Umstellen jede Konstante einer der beiden Klassen zuordnen und je Auflösung ausweisen,
  sonst prüft die QA bei der neuen Größe etwas anderes als bei der alten. Golden-Hashes einer nicht gebackenen Auflösung nie raten: als `stale`
  markieren, damit die Abnahme rot bleibt, bis der Mac sie schreibt. Beleg: 0.16 Finegrain (`surface.py` › `dilation_at`, `margin_px_at`,
  `set_bytes_limit`; `verify_surface.py` › `golden_stale`). Gilt auch für: Welt-Karten, Roboter-Variante, Robogen-Masken.
- 17.10.2026 · Waffe in der Roboterhand – Ein gleichmäßiger Maßstab löst Griff- und Stützhandlage nicht: Die Stützhand des
  Roboters (Arm 0,42 m, Schultern 0,56 m auseinander) erreicht nur etwa 0,10 m vor `Socket_Hand`, ein Gewehr mit Handschutz
  hat sie 0,18–0,28 m davor. Nötig ist eine eigene Form: Stützanker an Magazinschacht oder Gehäusefront, Schaft an den Griff,
  Querschnitt kräftiger. Beleg: CE `Docs/versions/0.82.md` › Befunde, `qa_geometry_robot.json` (0,09 m bei allen acht). Gilt auch
  für: jedes Werkzeug, das ein anders proportionierter Körper hält.
- 17.10.2026 · Umformen statt neu modellieren – Eine monotone, achsweise Abbildung (Querschnittsfaktor, stückweise lineare
  Längsachse) über dem fertigen Design hält Teile, Namen, Anker, Clips, Decals und Rezepte gültig und erzeugt keine neuen
  Durchdringungen; die Griffzone braucht dieselbe Steigung längs und quer, sonst ändert sich die Griffneigung (Vertragswert).
  Beleg: `weapon_designs.py` › `ROBOT`, `tests/test_robot_variant.py`; Robogen `docs/TECHNIK.md` › 15 (gleicher Weg für Körper).
  Gilt auch für: weitere Körper- oder Größenvarianten.
- 17.10.2026 · Wege im Clip über Knickstellen – Clip-Wege mit der Steigung am Ruhepunkt zu skalieren ist falsch, sobald der Weg eine
  Knickstelle der Abbildung überquert (Schrotflinten-Verschluss 94,5 statt 58,8 mm); die verschobene Position selbst abbilden.
  Beleg: Codex-Prüfung `sol` 17.10.2026, Test `test_bolt_travel_follows_the_map_across_the_grip_zone`. Gilt auch für: Anker,
  Drehpunkte und Grenzen, die nach einer nichtlinearen Verformung gebraucht werden.
- 17.10.2026 · Decals auf verformten Teilen – Rechtecke als Bruchteile der Teil-Box verzerren unter nicht gleichmäßiger Verformung
  (Seitenverhältnis 0,36–0,54 daneben, im gestauchten Schaft 4 Texel); die Mitte abbilden, die Größe gleichmäßig skalieren, am Rand
  erst verschieben, dann schrumpfen. Ein eigenes UV1-Atlas hat eigene Nähte: Ausweich-Kandidaten fest und der Reihe nach prüfen.
  Beleg: `decals.refit_rect`, `qa_surface_robot.json`. Gilt auch für: Decals auf jeder Größen- oder Formvariante.
- 17.10.2026 · Stauchen erzeugt Z-Fighting – Eine Verformung, die längs auf 0,13–0,4 staucht, schrumpft auch die
  0,5-mm-Abstände der Dekore: die Koplanar-Regel muss auf den verformten Flächen gelten, nicht nur am Design. Kleine Baugruppen
  (Energiezellen) mit Mindeststeigung um ihre Mitte abbilden, Knickstellen nicht unter Dekore legen. Beleg: Viewer-Determinismus
  `trace_rifle/robot` 1,4–1,6 px vor, Test `CoplanarRobotTests`. Auch 0,8 mm statt 1 mm an einer Kante flackerte noch (2 von 15
  Bildern): Zonen mit feinen Dekoren 1:1 lassen, die Stauchung in schlichte Teile (Lauf, Schaft) legen; nach jeder Achsenänderung
  `viewer/test_determinism.py --model <tool>/robot --runs 16`. Gilt auch für: jede nicht gleichmäßige Skalierung.
- 18.10.2026 · Golden als sha256 und Bake-Rauschen – Ein einziger Texel auf der Rundungsgrenze macht eine Karte zwischen Läufen
  verschieden, obwohl Eingabe und Einstellungen gleich sind (Normal-Bake, 1 von 3 Läufen, jede Thread-Zahl). Vor dem Umschreiben eines
  Golden die Karte drei- bis fünfmal aus denselben Dateien nachbacken; zwei Bauten mit gleichem Ergebnis beweisen keine Stabilität.
  Belegte Varianten als Ausweich-Hash führen, nicht den Hauptwert hin- und herschreiben. Beleg: 0.15.1, `GoldenAlternatesTests`.
  Gilt auch für: jede Bild- oder Kartenprüfung über Hashes.
- 17.10.2026 · Bytegleichheit belegen – GLB und Viewer-Daten sind zwischen Läufen bytegleich, FBX und .blend nicht (Exportzeit und
  absoluter Pfad des Bauordners, Länge je Worktree verschieden); Ego-Spiel-GLB bleibt die bekannte Ausnahme aus 0.13. Beleg:
  `scripts/compare_models.py` gegen die 0.13-Ausgabe (205 Dateien gleich). Gilt auch für: jede Zusatzvariante, die bestehende
  Modelle nicht ändern darf.
- 17.10.2026 · Neue Stufen ans Ende – Stufen lesen standardmäßig alle bisher erzeugten Dateien; neue Zusatzstufen gehören ans Ende
  von `STAGES`, sonst hängen bestehende Schlüssel an den neuen Dateien. Jede Änderung an `tools.json` (neuer Schlüssel) baut die
  betroffenen Werkzeuge ganz neu, ebenso `version.py` alle Spielstufen: Version vor dem ersten großen Lauf heben. Beleg: dieser
  Auftrag (zwei abgebrochene standard-Läufe). Gilt auch für: Lenswork und spätere Varianten.
