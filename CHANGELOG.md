# Änderungen

## 0.4.0 – Fieldstrip (15.10.2026)

- Spiel-Export der Weltmodelle (Stufe `game`, `toolgen/game_export.py`): Statische Teile werden in einen Renderer
  zusammengeführt, bewegliche Teile bleiben getrennt (Greiferbacken, Bogen-Morph, Pfeilträger); Anker, Hierarchie und
  Clip (Name, Länge, Ereignisse) bleiben unverändert. Der Greifer-Clip `MG_Apply` wird als `MagnetGripper_Use` exportiert.
  Werte: Portalkanone 1 Renderer, 32 468 / 9 740 Dreiecke (LOD0 / LOD1), 4 Kollisionsboxen; Magnetgreifer 3 Renderer,
  25 928 / 7 774, 7 Boxen; Taschenlampe 1 Renderer, 10 628 / 3 188, 2 Boxen; Bogen 3 Renderer, 12 036 / 3 610, 6 Boxen.
- Matte Palette `data/game_palette.json` auf Cube-Escape-Materialnamen (`M_RobotBody`, `M_RobotDark`, `M_Metal`,
  `M_HazardOrange`, `M_GlowCyan`, `M_GlowOrange`); Metallic höchstens 0,35, Roughness mindestens 0,55 bei den
  matten Materialien, je Werkzeug 5 Materialien.
- LOD0/LOD1 nach der Cubegen-Namenskonvention (`<Teil>_LOD0`/`_LOD1`, LOD1 etwa 30 % der Dreiecke); Kollisionsboxen im
  Cubegen-Sidecar-Format, Öffnungen (Mündung, Greifraum, Bogenfenster) bleiben frei. Ergebnisdateien: `<Asset>_Game.blend/.fbx/.glb`,
  `unity_contract.json`, `qa_game.json` (Prüfung nach Blend-, GLB- und FBX-Reimport). Für Unity den FBX-Import mit
  `bakeAxisConversion` einstellen; der Vertrag nennt das.
- Ego-Hände: drei Greiffinger plus Daumen wie Robogens Mitt (vorher zwei Greiffinger). Haltungen mit Zielpunkt
  (`aim_target_m`), Rollwinkel der Stützhand (`support_roll_degrees`) und je Werkzeug überschreibbaren Schultern.
- Viewmodel-Sichtfeld als Daten (`data/viewmodels.json` › `camera`): vertikal 46,69° (entspricht dem bisherigen 75°
  horizontal bei 16:9), Near Clip 3 cm. Für Unity als eigenes Viewmodel-FOV (URP Render Objects); das Spielsichtfeld bleibt
  eine Spielereinstellung. Neu je Ego-Paket: `viewmodel_camera.json` und Root-Properties `ce_viewmodel_*`.
- Ego-QA verbindlich beim eingestellten Sichtfeld für 16:9 und 16:10; ±8° werden nur berichtet (`fov_range`). Der Bogen-Zughand-Ausschnitt
  wird nur in Ruhe geprüft. Neue Kopfprüfung (`head`): Werkzeugkopf unverdeckt, Portalkanone 63 %, Greifer 74 %, Taschenlampe 56 %.
- Ego-Modelle sind deterministisch (Ursache der Abweichungen: die Fläche der Handgelenkkugel aus `create_uvsphere`).
- Viewer: Regler „Sichtfeld“ (35–75°, Zurücksetzen auf den Datenwert, gilt für A/B und PNG), Kommandozeile `--fov`,
  Variante „Spielmodell“ (optional, der Viewer läuft auch ohne).
- Geteilter Stufen-Cache (`~/Library/Caches/CubeEscapeToolgen/cache`, `TOOLGEN_CACHE`, `TOOLGEN_CACHE_LIMIT_GB`, Standard 4):
  atomare Einträge, APFS-Klone, Hash-Prüfung bei jedem Treffer, Aufräumen nach letzter Nutzung mit Schonfrist.
  Deklarative Stufenliste `STAGES`: eine neue Stufe ist ein Eintrag. Schlüssel je Stufe aus Quellen-Closure, Hashes der
  Vorstufen, Blender-Version und bei Bildern Samples/Prozent/Gerät; Geometrie und Bilder werden getrennt gecacht.
  Gemessen am 15.10.2026: frischer Ausgabeordner `standard` 0,48 s (46 Stufen aus dem Cache) gegenüber 157 s kalt in 0.3.0;
  zweiter `quick` 0,21 s; eine Änderung nur an `first_person.py` baut nur `first_person` und `viewer_fps` neu.
- `scripts/heavy_lock.py`: gemeinsame Sperre mit Robogen, Cube Escape und Cubegen; `full` und `check_output.sh` warten darauf.
  `scripts/testplan.py` nennt aus dem Diff den kleinsten Prüfweg.
- Prüfung: 100 Unit-Tests, `check_output.sh` mit 97 Prüfungen für 13 Modelle, Viewer-Test mit 47 Prüfungen.
- Grenzen: Die Unity-Abnahme steht aus. Die Taschenlampen-Linse ist im Spielexport `M_GlowOrange` und damit kräftiger
  als das warme Weiß im Weltmodell; die Cube-Escape-Materialien gleichen Namens sind glänzender als die Palette. Beides wird beim Import entschieden.

## 0.3.0 – Flowstate (15.10.2026)

- Ego-Modelle mit artikulierten Roboterhänden und Unterarmen im Mitt-Stil von Robogen und mit dessen Gelenknamen.
  Zwei Hände für Portalkanone, Magnetgreifer und Bogen; eine Hand für die Taschenlampe.
  Jede Hand hat insgesamt drei Finger (zwei Greiffinger und einen Daumen); mittiger Anschluss an der Handwurzel.
- Weiße Handrücken- und Unterarmplatten, orange Einsätze, dunkle Fingergelenke und Schrauben nach dem unteren
  linken Ego-Ausschnitt des Bogenkonzepts; modulare, leicht konische Unterarmschalen.
- Ego-Bildausschnitt mit vollständigen Dreifingerhänden und höchstens halben Unterarmen; Ellenbogen und Oberarm bleiben außerhalb.
  Zusammenhängende Unterarmgeometrie läuft über den Bildrand hinaus;
  gebackene Zwei-Glied-IK hält Schulterposition, Gliedlängen und Griffkontakt während der Bewegung zusammen.
- Datenbasierte Haltepositionen und feste Armlängen; Bogen-/Handgröße und Griffdrehung sind gemeinsam abgestimmt.
  Bogen-Zughand folgt der Nocke, öffnet beim Lösen und greift beim Nachladen erneut an.
- Weiche Beschleunigung, verzögerte Rückführung und gebackenes Nachfedern. Bogen-/Greiferaktionen behalten IDs,
  97 Frames und Ereigniszeitpunkte; die zuvor statischen Ego-Modelle bekommen explizit startbare Anwendungsvorschauen.
- Viewer interpoliert Positionen, Skalierungen, Morphs und Quaternionen zwischen den gebackenen Frames.
  Ego-Vorschau, A/B und Screenshot behalten unabhängig von der Fensterform denselben Bildausschnitt in 16:9.
- Eigene Kontakt-, Sichtfeld-, Ruhepose- und Reimportprüfung für die Handbaugruppen; gemeinsame Quellen im Cache.

## 0.2.0 – Slipforge (15.10.2026)

- Native SwiftUI-/SceneKit-Oberfläche nach Robogen: alle vier Werkzeuge, Welt/FPS/Pfeil, feste Ansichten,
  Material-Looks, A/B, Aktionssteuerung und PNG-Export.
- Gemeinsame Autoren-Pipeline statt Portal-Prototyp; Quick/Standard/Full, begrenzte Worker/Threads,
  Inhaltscache, sichere Paketübernahme, Schrittlogs und Zeitband.
- Bogenanimation repariert: vollständige Namen, numerische Blender-Suffixe, Morph-/Ankerprüfung und Reimport.
- Portalkanone/Magnetgreifer: kürzere, schmalere Gehäuse und offene Zuführung; Werkzeugkopf besser sichtbar.
- Bogen: schlankerer Griff/Riser, kleinere Verkleidungen und Gelenke, besser sichtbare Wurfarme/Sehne in FPS.
- Regeln, Test-Skill, Claude-Profile/Hooks und Cloud-Werkzeuge nach Robogen; ce-shared aus ce-agent-tools.
- Bildtests für Varianten, Bewegung/Reset, Looks, beschädigte Daten und Layout.
- Ego-Knopf lädt das passende FPS-Modell statt die Kamera in das Weltmodell zu setzen; auch im A/B-Vergleich.
  Regression prüft die echte Auswahlfunktion, Werkzeugwechsel und identische Ego-Bilder.

## 0.1.0 – Prototyp (14.10.2026)

Vier Werkzeug-Referenzpakete sowie einfacher Portal-Emitter mit separater CLI und AppKit-OBJ-Viewer;
Bogenanimation noch unvollständig.
