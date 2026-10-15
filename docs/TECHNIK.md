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
die Formensprache: dunkle Gelenke, Daumen und weiße Verkleidung. Die Ego-Version verwendet auf Nutzerwunsch
**drei Finger insgesamt: zwei Greiffinger und einen gegenüberliegenden Daumen**; Robogens Mitt hat ursprünglich
drei Greiffinger plus Daumen. Die Ego-Version wird mit
zusätzlichen starren Fingersegmenten hier erzeugt. `Hand_L/R`, `Fingers_*`, `Thumb_L/R`, `LowerArm_L/R` sowie
`GripContact_L/R` sind exportierte Knoten, keine Kopie des vollständigen Robogen-Skeletts oder dessen Clips.
Robogen muss zur Generierung nicht installiert sein; sein Repository bleibt unverändert.
Der untere linke Ego-Ausschnitt des Bogenkonzepts bestimmt die Verkleidung: weiße Handrückenplatten, orange
Einlagen, dunkle Gelenkspalte, Schrauben und konische Unterarmschalen. Einlagen und Schrauben folgen der
geneigten Schalenfläche und sitzen auf ihr. Die gemeinsamen Kontakt-/Gelenk-IDs bleiben davon unabhängig.

**Verbindlicher Ego-Bildausschnitt:** Hände vollständig zeigen, von den Unterarmen höchstens die griffseitige
Hälfte. Oberarme, Ellenbogenräder und Schulterpanzer gehören nicht in das Ego-Mesh. Der Bogen bleibt das
Hauptmotiv; seine Größe, Neigung und Halteposition werden zusammen mit den Händen abgestimmt. Genau zwei
gegliederte Greiffinger und ein Daumen müssen pro Hand erkennbar sein. Fingerglieder sind keine zusätzlichen Finger. Keine
kastenförmige Ersatzhand oder durchgehende Stange als Arm.

Jeder Arm hat die starren Rig-Knoten `UpperArm_*` → `LowerArm_*`. Ihre Längen und Schulterpositionen sind feste
Maße unter `arm` in `data/viewmodels.json`; sie werden niemals aus dem Abstand zum Werkzeug verlängert.
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

Der Bogen verwendet ein eigenes `tool_scale`, `hand_rotation_degrees` und `draw_roll_degrees`. Skalierung wird in
Mesh-, Morph- und Translationsdaten gebacken, die Objekt-Skalierung bleibt 1. Handdrehungen erfolgen um den
Griffkontakt; sie dürfen weder Griff noch Nocke versetzen. Linke Handfläche/Handgelenk liegen auf der linken
Seite des Griffs, die rechte Zughand auf der rechten Seite der Nocke. Eine Drehung um 180° nur zum Sichtbarmachen
der Finger vertauscht diese Seiten und ist falsch. Die Zughand gleicht die Bogenschräglage aus, statt mit einem
verdrehten Handgelenk die volle Werkzeugrotation zu übernehmen. `min_hand_side_clearance_m` prüft die
korrekte Handgelenkseite an jedem Frame und verwirft die frühere verdrehte Haltung. Die Zugfinger bilden einen
flachen, dreigliedrigen Haken an der Sehne; sie übernehmen nicht die tiefe Umschlingung eines Werkzeuggriffs.
Änderungen am FPS-Bogen ändern das Weltmodell nicht.

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
