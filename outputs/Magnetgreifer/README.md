## Autorenquellen und aktuelle Ausgabe

Die Generatorquellen liegen in `scripts/tool_assets/Magnetgreifer/`.
Der gemeinsame Einstieg ist `python3 toolgen/generate_tools.py --tier full`; neue Pakete liegen in `output/`.
Die hier liegenden Dateien sind historische Referenzen.

# Magnetgreifer – kleines und großes Modell

Aus Feld 3 der bereitgestellten Cube-Escape-Werkzeugtafel entwickelt. Das längliche Gehäuse übernimmt die Formensprache der Portalkanone und des weißen Classic-Roboters. Zwei kräftige gebogene Backen mit dunkler Mechanik, weißen Verkleidungen, silbernen inneren Kontaktleisten und dunklen Greifpolstern umschließen einen kurzen Magnetkopf. Sein eingelassener blauer Kern und die kleinen Coil-Leuchten unterscheiden ihn vom großen Portalring. Keine schwebenden Gegenstände oder dauerhaften Strahlen gehören zur Exportgeometrie.

## Varianten

- `CubeEscape_MagnetGripper.blend`, `.fbx`, `.glb`: kompakte Variante für Roboterhand und Weltansichten.
- `CubeEscape_MagnetGripper_FPS.blend`, `.fbx`, `.glb`: separate große Egoperspektiv-Version mit gleichmäßig 150 % Geometriegröße, Skalierung aller Objekte 1 und Kameramontage-Root am Ursprung.
- `preview_white.png`: Studioansicht des kompakten Modells.
- `preview_first_person.png`: große Version in der abgestimmten tiefen Egoperspektiv-Haltung.
- `preview_large.png`: freigestellte große Version.
- `preview_concept_colors.png`: dieselbe Geometrie mit orangefarbenen Konzeptakzenten.
- `view_side.png`, `view_front.png`, `view_top.png`: orthografische Prüfansichten.

Die FPS-Kamera entspricht der abgesenkten Portalkanone: Ursprung `(0,0,0)`, Blick −Y, Welt-Z oben; rechts im Bild liegt auf −X. 75° horizontales Sichtfeld, 16:9, 1600 × 900, Near Clip 3 cm. Handanker bei `(-0,26; -0,66; -0,50)` m. Der Magnetkopf zielt auf `(0; -4; 0)` m. Größe, Versatz und Ausrichtung sind in die Bauteile eingerechnet. Keine zusätzliche 150-%-Skalierung oder doppelte Offset-Anwendung bei der Montage.

Die Blender-Datei enthält eine einfache Vorschauumgebung, Studiolicht und Kameras. Diese Präsentationsobjekte sind von den Exporten ausgeschlossen. Unity-Händigkeit, Importachsen und die Kameramontage müssen im tatsächlichen Spiel abgeglichen werden. Die Vorschau ist eine Blender-Abnahme, keine getestete Unity-Szene.

## Bauteil- und Montagevertrag

Kategorie **Interactive**; Tags `tool`, `magnet-gripper`, `handheld`, `robot-classic`, `white-shell`, bei FPS zusätzlich `first-person-large`. Metermaßstab, Geräteachse −Y, Z oben. Maße und Bounds beider Varianten stehen in ihren `qa_geometry*.json`.

`Pivot_Upper` und `Pivot_Lower` besitzen eigene Backenhierarchien und liegen an den Gelenken. `Pivot_MagnetAxis` richtet die Längsachse aus; `Pivot_HeadSpin` dreht beide Backen gemeinsam um diese Achse. Der Magnetkern bleibt fest. `Socket_Hand` liegt im Griffzentrum, `Socket_SupportHand` unter dem Korpus, `Socket_Muzzle` bezeichnet die Achse des Magnet-Emitters, `Socket_Grab` das Zentrum zwischen den Greifspitzen. Bei der großen Variante gibt es zusätzlich `Socket_Camera` am Kameraursprung. Leuchtteile, Kontaktpolster und Anzeigen sind eigenständige Meshes.

## Aktionsanimation – nur bei Anwendung

Beide Varianten besitzen eine echte exportierte Animation. **Kein Autoplay, keine Dauerschleife:** Die Dateien sind in der offenen, stillstehenden Ruhepose gespeichert. Der vorgesehene Ablauf `MG_Apply` dauert 4 Sekunden bei 24 fps (Frames 1–97):

- 0–0,5 s: obere/untere Backe schließen an ihren Gelenken um jeweils 5° gegensinnig.
- 0,5–3 s: die geschlossenen Backen drehen sich gemeinsam einmal um 360° um die Geräte-Längsachse.
- 3–3,5 s: Backen öffnen wieder.
- 3,5–4 s: Ruhepose; danach keine weitere Bewegung ohne neuen Aktionsaufruf.

`preview_apply_once.gif` zeigt einen einzelnen Durchlauf in groben Vorschauschritten; die Modellexporte enthalten die kontinuierlich gesampelte Animation. `animation_frames/` enthält die dafür gerenderten Bilder. `action_contract.json` dokumentiert den Aufrufvertrag. glTF/FBX speichern die Bewegung; die spätere Anwendung muss deren einmaligen Aufruf steuern. Ein beliebiger externer Viewer kann eigene Wiedergabe-Voreinstellungen besitzen.

Als separater Unity-Anschluss liegt `MagnetGripperActionPlayer.cs` bei. Er verwendet eine Legacy-`Animation` auf dem importierten Asset-Root und einen im Inspector zugewiesenen Clip. `ApplyGrab()` bzw. `TryApplyGrab()` startet den Ablauf ausdrücklich durch die Spielinteraktion, z. B. das Greifen einer Kiste. `Awake` startet nichts, Autoplay ist deaktiviert, der Clip wird auf einer eigenen Instanz mit `WrapMode.Once` abgespielt; eine laufende Aktion wird nicht gestapelt. Nach dem Ende wird die ruhende offene Pose gesampelt. `onGripClosed` nach 0,5 s und `onApplicationFinished` sind Anschlusspunkte für die Interaktion. `CancelAction()` bricht ab und setzt zurück. Den Player mit dem tatsächlichen Import-Clip und dessen Bindung im Zielprojekt prüfen; er ist keine implementierte Kistenphysik.

Der Player wurde separat gegen die lokal installierten Unity-6000.6.2f1-Assemblies kompiliert. Die Inspector-Zuweisung des Clips, Animation-Bindings und Laufzeitereignisse sind noch nicht in einer Unity-Szene getestet. `qa_action_player.json` hält diese Grenze ausdrücklich fest.

Einfarbige Principled-PBR-Materialien nach dem weißen Classic-Look. Boxprojektion mit absichtlich überlappenden UV-Inseln; kein gepackter Paint- oder Lightmap-Atlas. FBX-Emission hängt von der Zielanwendung ab; GLB enthält PBR-Materialien und Emission. Keine URP-/HDRP-Darstellung geprüft.

Dies sind visuelle Modelle: noch keine Magnetkräfte, Objektbewegung, Physik, Kollisionen, Gameplay-Steuerung oder Unity-Prefabs. Die vorhandenen Generatorprojekte und der Roboter-Viewer werden durch diesen Stand nicht verändert.

## Lokaler Build und Prüfung

Blender 5.2.2 LTS. Im Ordner ausführen:

```bash
bash build_cube_escape_assets.sh
```

Der kompakte Generator `create_magnet_gripper.py` ist vollständig lokal; `create_magnet_gripper_fps.py` leitet die große Variante aus der frisch erzeugten Basisdatei ab. `animate_magnet_gripper.py` ergänzt anschließend die Aktionsanimation beider Varianten und exportiert sie neu. `make_animation_preview.py` erzeugt mit dem lokal installierten ImageMagick die GIF-Vorschau. Für eine andere Blender-Installation `BLENDER_BIN` setzen. Die CLI läuft in eigenen Hintergrundinstanzen. Der große Generator und der Animationsschritt laden ihre Quelldateien und sind für diesen CLI-Ablauf vorgesehen; bestehende interaktive Sitzungen werden durch den CLI-Aufruf nicht ersetzt.

Der Build prüft endliche Geometrie, geschlossene Meshes, positives Volumen, UV-Flächen, Materialien, Einheits-Skalierung und Polygonbudget. Die Bewegung wird an allen 97 Frames geprüft: positive Kontaktpolster-Abstände, feststehender Magnetkern, Rückkehr in die Ruhepose; in FPS zusätzlich freies Zielfeld und Near Clipping. `qa_animation*.json` enthält acht Referenzposen für den Reimport. `verify_magnet_gripper.py` öffnet beide Varianten erneut und importiert FBX/GLB unabhängig; Meshzahl, Metermaße, Anker, Backenhierarchien, UVs, Materialbindungen und die acht Animationsposen müssen erhalten bleiben. Die FPS-Prüfung kontrolliert außerdem rechten Bildbereich und die Richtung des Magnetkopfs. Die Abschlussmarker `build_complete.json` und `build_complete_fps.json` bestätigen ausschließlich die tatsächlich erfolgreich geprüften Assets dieses Laufs.
