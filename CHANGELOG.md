# Änderungen

## 0.6.2 – Sightline (15.10.2026)

Werkzeug-/Doku-Patch: gemeinsamer Standard der vier Repos.

- `.ce-repo.json` (Version aus `toolgen/version.py`, Prüfbefehle, Grenzen) und eingebettete Kopie der gemeinsamen Werkzeuge
  in `scripts/ce_tools/` (`ce_sync.py` aus `ce-agent-tools`); `scripts/heavy_lock.py` leitet an die geteilte Sperre weiter.
- Wrapper `./check` (`--full`) und `./release` (Trockenlauf); `AGENTS.md` in der Standard-Gliederung, `report.md` ungetrackt.
- Neu: `docs/ENTSCHEIDUNGEN.md` (Entscheidungen vom 15.10.2026). Keine Versionsberichte als eigene Dateien: `CHANGELOG.md` bleibt die Übersicht.
- Keine Änderung an Pipeline, Modellen oder Viewer; kein Blender-Lauf.

## 0.6.1 – Sightline (15.10.2026)

Patch nach dem Codex-Review von 0.5.0/0.6.0.

- Ego-Spielmodell: neue Prüfung `viewmodel_framing` in `qa_game_fps.json`: Bildschirmausdehnung jedes reduzierten Renderers gegen das
  gestaltete Modell in jedem Clipbild bei 16:9 und 16:10 (Toleranz 0,3 % der Bildgröße) und freies Fadenkreuz (vertexbasiert).
  Die FOV-Freigaben im Vertrag gelten getrennt: `authored_model_validated_vertical_fov_degrees` (aus `qa_viewmodel.json`) und
  `game_model_validated_vertical_fov_degrees` (nur der Datenwert); vorher wurde die Reihe des Originals für das Spielmodell übernommen.
- Viewer-Test: das Ego-Spielmodell hat höchstens so viele Dreiecke wie das gestaltete (bei Budget über der Quellzahl entfällt die Reduktion).
- Prüfung: 109 Unit-Tests, `check_output.sh` 117 Prüfungen (17 Modelle), Viewer-Test 64 Prüfungen (`--tier full`).
- Test `GameFpsStageTest` stand hinter dem `unittest.main()`-Block und lief bei direktem Aufruf nicht; verschoben.

## 0.6.0 – Sightline (15.10.2026)

- Viewer: neue Variante „Ego-Spielmodell“ (`fps_game`, Datei `<Asset>_FPS_Game`, nur LOD0) für jedes Werkzeug, optional wie das
  „Spielmodell“. Sie nutzt dieselbe Ego-Kamera (`viewmodel_camera.json`, Regler „Sichtfeld“, A/B, PNG) und dieselbe Animation wie das
  gestaltete Ego-Modell. Die Ego-Taste öffnet aus dem „Spielmodell“ das Ego-Spielmodell, sonst das gestaltete Ego-Modell;
  Werkzeugwechsel und Ansichtswechsel behalten die Variante. Neue Stufen-Variante an `game_fps` (`variants` in `STAGES`).
- Viewer-Tests: Ego-Spielmodell weniger Dreiecke als das gestaltete, gleiche Frames, nur LOD0, Rig-Knoten (`Viewmodel_Motion`,
  `Socket_Camera`), Wahl der Ego-Taste, Rückfall ohne die Variante, Bildabweichung gegen das gestaltete Ego-Modell unter 10 %, Seitenleiste bei 360 pt.
- Prüfung: 108 Unit-Tests, `check_output.sh` mit 117 Prüfungen für 17 Modelle, Viewer-Test mit 64 Prüfungen (`--tier full`).
- Grenzen: Unity-Abnahme und die Dreiecksbudgets des Spiels stehen aus (Budgets unverändert, Schätzwerte).

## 0.5.0 – Trimline (15.10.2026)

Behebt die Integrationslücken aus dem Review vom 15.10.2026 (Material- und Knotenzahl, Dreiecksbudget, Ego-Sichtfeld).

- Ego-Spielmodell (neue Stufe `game_fps`, `game_export.py --viewmodel`): Hände, Arme und Werkzeug als `<Asset>_FPS_Game.blend/.fbx/.glb`
  mit `unity_contract_fps.json`, `qa_game_fps.json`, `preview_game_fps.png`. Matte Palette statt 12–14 glänzender Materialien
  (6–7 Palettenmaterialien), 15–39 Knoten statt 98–241 (je Renderer ein Mesh je animiertem Besitzer, Anker und Clip unverändert),
  LOD0/LOD1, keine Kollision. Weltmodelle hatten das seit 0.4.0, das Ego-Modell nicht.
- Dreiecksbudgets (`data/game_budget.json`): LOD0 wird nach dem Zusammenführen auf das Budget reduziert (Collapse-Decimate, Shape Keys
  des Bogens folgen). Welt: 32 468 → 8 000 (Portalkanone), 25 928 → 7 998 (Magnetgreifer), 10 628 → 5 000 (Taschenlampe),
  12 036 → 5 996 (Bogen); Ego: 45 932 → 15 996, 39 392 → 15 992, 17 360 → 11 998, 25 500 → 13 992; LOD1 etwa 30 % davon.
  Maße gegen das Quellmodell weiter 1 mm in jedem Clipbild; neue Prüfung `triangle_budget`.
- Viewmodel-Kamera als Vertrag: `viewmodel_camera.json` und der Block `viewmodel` im Ego-Vertrag nennen jetzt `player_fov_dependency`
  (`none`), `aspect_policy`, `camera_offset_m`, `runtime` und `validated_vertical_fov_degrees` (aus der gemessenen FOV-Reihe: Portalkanone
  und Magnetgreifer 46,69/50,69°, Taschenlampe 42,69–54,69°, Bogen nur 46,69°). Das Ego-Modell liegt im Kameraraum und ist nicht an das
  Spieler-FOV gebunden; das Spiel zeichnet es mit eigener Kamera. Kein fester 75°-Wert mehr im Asset.
- Doku: [docs/UNITY_EINBAU.md](docs/UNITY_EINBAU.md) (Dateien, Materialien, Viewmodel-Kamera mit URP-Overlay und Skizze, offene
  Unity-Punkte).
- Palette: `max_materials_per_viewmodel` 7 (die Hand bringt `M_HazardOrange_Matte` hinzu, die Taschenlampe braucht 7).
- Prüfung: 108 Unit-Tests (4 neue für Budget, Limits und Stufe `game_fps`), `check_output.sh` 117 Prüfungen, Viewer-Test 47 Prüfungen; `verify_output.py` prüft den Ego-Vertrag (Budget, Knoten, Materialien,
  keine Kollision, FOV-Wert).
- Grenzen: Unity-Abnahme steht aus; Viewer zeigt das Ego-Spielmodell nicht als eigene Variante (nur das Bild `preview_game_fps.png`).

## 0.4.0 – Fieldstrip (15.10.2026)

- Spiel-Export der Weltmodelle (Stufe `game`, `toolgen/game_export.py`): Statische Teile werden in einen Renderer
  zusammengeführt, bewegliche Teile bleiben getrennt (Greiferbacken, Bogen-Morph, Pfeilträger); Anker, Hierarchie und
  Clip (Name, Länge, Ereignisse) bleiben unverändert. Der Greifer-Clip `MG_Apply` wird als `MagnetGripper_Use` exportiert.
  Werte: Portalkanone 1 Renderer, 32 468 / 9 740 Dreiecke (LOD0 / LOD1), 4 Kollisionsboxen; Magnetgreifer 3 Renderer,
  25 928 / 7 774, 7 Boxen; Taschenlampe 1 Renderer, 10 628 / 3 188, 2 Boxen; Bogen 3 Renderer, 12 036 / 3 610, 6 Boxen.
- Matte Palette `data/game_palette.json`: matte Varianten der Cube-Escape-Materialien wie beim matten Spielerroboter
  (`M_RobotBody_Matte`, `M_RobotDark_Matte`, `M_Metal_Matte`, `M_HazardOrange_Matte`, je mit `ce_base`), die
  Leuchtmaterialien `M_GlowCyan`, `M_GlowOrange` und neu `M_GlowWarm` (warmweiße Linse der Taschenlampe); Metallic
  höchstens 0,35, Roughness mindestens 0,55 bei den matten Materialien, je Werkzeug höchstens 6 Materialien.
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
  Der Befehl läuft in einer eigenen Prozessgruppe; TERM/HUP/INT gehen an die ganze Gruppe, und die Sperre wird erst frei,
  wenn die Gruppe leer ist – ein Enkelprozess (Blender unter `check_output.sh`) hält sie auch, wenn sein Elternprozess
  vorher starb (Befund des Codex-Reviews, gemeinsam mit Robogen 1.20.5, Cube Escape 0.61.3 und Cubegen 0.27.0).
  `scripts/testplan.py` nennt aus dem Diff den kleinsten Prüfweg.
- Prüfung: 104 Unit-Tests, `check_output.sh` mit 97 Prüfungen für 13 Modelle, Viewer-Test mit 47 Prüfungen.
- Grenzen: Die Unity-Abnahme steht aus. Die Spielmodelle kommen noch nicht in Cube Escape; beim Einbau legt Cube Escape
  die `_Matte`-Varianten und `M_GlowWarm` an, statt die glänzenderen gleichnamigen Materialien zu verwenden.

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
