# Lehren (Kurzzeitgedächtnis für Agenten)
≤60 Zeilen, eine Zeile je Lehre, Langform nur per Link; neue Lehren hier zuerst, dann ggf. in TECHNIK.md.

## Blender/Export und Bytegleichheit
- **Golden-Fehler nach reinem Versionswechsel** → mit frischem Bau des alten Tags gegenprüfen; seit 0.23 trägt die Fingerabdruck-Toleranz Rauschen, `alternates` werden nicht mehr geschrieben, Golden nie blind neu schreiben ([Quelle](TECHNIK.md#erfahrungen))
- **Normal-Bake kippt einzelne Texel (1 von 3 Läufen, jede Thread-Zahl)** → vor Golden-Änderung 3–5× nachbacken; zwei gleiche Bauten beweisen nichts ([Quelle](TECHNIK.md#erfahrungen))
- **`*_FPS_Game.glb`/`*_Robot_Game.glb` schwanken um 1e-4 (Tangenten)** → getrennt vergleichen, nicht als Inhaltsfehler werten ([Quelle](TECHNIK.md#grenzen))
- **FBX und .blend tragen Exportzeit und absoluten Pfad** → Bytegleichheit nur für GLB und Viewer-Daten behaupten ([Quelle](TECHNIK.md#grenzen))
- **Dezimierung triangulierte und setzte UV-Markierungen nebenbei** → unter Budget macht `reduce_to_budget` beides selbst, sonst fehlen Tangenten und UV1 ([Quelle](TECHNIK.md#erfahrungen))
- **Objektsuche kappte Namen am ersten Punkt** → Millimeterzahlen im Namen, volle Namen, nur numerische Blender-Suffixe ([Quelle](TECHNIK.md#gestaltung-und-bogen-fix))
- **Render-Limits gingen bei `open_mainfile` verloren** → Sample-/Thread-Vorgaben als persistente Handler setzen ([Quelle](TECHNIK.md#cache-und-worker))

## UV/Bake/Oberflächen
- **Pixelkonstanten sind in Wahrheit UV- oder Kartengrößen** → vor jeder Auflösungsänderung jede Konstante einer Klasse zuordnen; ungebackene Golden als `stale` markieren, nie raten ([Quelle](versions/0.16.md))
- **Eck-Texel-Prüfung mit falschem 16-px-Band ließ elf Spielexporte scheitern** → Dilatation je Kartenauflösung gegen das Eck-Texel prüfen ([Quelle](versions/0.16.md))
- **Strenges Re-Raster verfehlt Randtexel (Epsilon 1e-7)** → für die Dilatationsgrenze 1e-5, Innenprüfung streng lassen ([Quelle](versions/0.16.md))
- **`surface_bake` 2048² kostet 100–460 s je Werkzeug (2 Worker)** → Standard backt 1024² (`bake_scale`), Abgabe an Cube Escape nur aus `full` ([Quelle](versions/0.22.md))
- **Golden nur als Hash kannte bei 1 Texel Rauschen nur „Ausnahme pflegen“** → Fingerabdruck je Karte (Blockmittel + Histogramm, 2–17 KB) mit Toleranz aus gemessenem Rauschen; Neuschrift nur für rote Karten, sonst wandert die Referenz ([Quelle](versions/0.23.md))
- **Verformung bewegt nur Eckpunkte, Dreiecke bleiben linear** → Texel über die zurückgebildeten Dreiecksecken baryzentrisch abbilden, nie je Texel über die stückweise Achse ([Quelle](versions/0.23.md))
- **Paletten stehen im Weapon-Spec, nicht im Geo-Blatt** → `import_concepts.py --spec` mit Golden-Hash aus formgen; Formatversion des Specs (2) prüfen, nicht raten ([Quelle](versions/0.23.md))
- **Blatt-Kanal ≠ Blattbild (KG02-Schiene: dunkelgrau gezeichnet, `MT_Secondary` = beige)** → Kanal des Blatts ist Vertrag; Abweichung an formgen melden, nicht in Toolgen korrigieren ([Quelle](ENTSCHEIDUNGEN.md))
- **Gemeinsame Daten in `viewmodels.json`/`game_budget.json` ändern alle Schlüssel** → neue Daten für wenige Werkzeuge in eigene Datei (`data/ego_arms.json`) ([Quelle](TECHNIK.md#erfahrungen))
- **Rechtecke als Teil-Box-Bruchteile verzerren bei Verformung** → Mitte abbilden, Größe gleichmäßig skalieren (`decals.refit_rect`) ([Quelle](TECHNIK.md#erfahrungen))
- **Ein Hüllquader je Ring schließt Visierfenster** → Öffnungen per Probe prüfen, rahmende Teile ohne Kollider ([Quelle](TECHNIK.md#erfahrungen))

## Cache, Zeiten, Sperren
- **`standard` aller 13 Werkzeuge: 43,5 min (2 Worker), `full` rund 52 min** → vor großem Lauf Version heben und `tools.json` finalisieren; Warm-Lauf nur 0,5–2 s ([Quelle](TECHNIK.md#cache-und-worker))
- **Neue Stufe mitten in `STAGES` ändert bestehende Schlüssel** → neue Stufen ans Ende; zwei standard-Läufe gingen so verloren ([Quelle](TECHNIK.md#erfahrungen))
- **Dateizeiten/Pfade im Schlüssel entwerten den Cache** → Inhaltshashes samt Quellen-Closure; neue Schreib-Helfer in `STAGE_CACHE_FUNCTIONS` eintragen ([Quelle](TECHNIK.md#cache-und-worker))
- **Schwere Läufe warten hinter Robogen/Cube Escape/Cubegen (Stunden)** → `heavy_lock` nicht umgehen, Zeiten unter Fremdlast nie als Zeitband werten ([Quelle](TECHNIK.md#cache-und-worker))
- **`version.py` ändern baut alle Spielstufen neu** → Version zuerst heben, dann den großen Lauf starten ([Quelle](TECHNIK.md#erfahrungen))

## Ego-Rig/Clips und Roboter-Variante
- **Strahl vom Griffmittelpunkt trifft Innenteile (Hand 2 cm im Gehäuse)** → Kontaktstrahlen von außen nach innen ([Quelle](TECHNIK.md#erfahrungen))
- **Gleich schnelles Beugen lässt Finger gestreckt hängen** → körpernahe Gelenke voraus, nur das berührende Glied sperren ([Quelle](TECHNIK.md#erfahrungen))
- **Ein Teilmitten-Anker (Handschutzmitte) ist kein Haltungspunkt** → erst Ego-Prüfung, dann über Anker entscheiden ([Quelle](TECHNIK.md#erfahrungen))
- **Wurzelkurven im Clip drehte der Unity-Import mit** → `clip_root_free`: nie Kurven auf die Wurzel ([Quelle](ENTSCHEIDUNGEN.md))
- **Handgelenk ≤ 55° verlangt schmaleres Sichtfeld** → Gerätegrenzen aus der Messung, nicht aus dem Wunsch ([Quelle](ENTSCHEIDUNGEN.md))
- **Stützhand des Roboters reicht nur 0,10 m vor `Socket_Hand`** → eigene Form statt Maßstab; Verformung des fertigen Designs statt Neumodell ([Quelle](TECHNIK.md#erfahrungen))
- **Clip-Wege über Knickstellen der Verformung falsch skaliert (94,5 statt 58,8 mm)** → verschobene Position abbilden, nicht die Steigung ([Quelle](TECHNIK.md#erfahrungen))

## Viewer und Determinismus
- **Stauchen schrumpft Dekor-Abstände → Z-Fighting (1,4–1,6 px)** → Koplanar-Regel auf verformten Flächen, feine Zonen 1:1 lassen, danach `test_determinism.py --runs 16` ([Quelle](TECHNIK.md#erfahrungen))
- **`pistol/world` und `portal_emitter/world` flackern 1,3–1,8 px unter Fremdlast** → bei Last wiederholen (unter `heavy_lock`), Grenze nicht lockern ([Quelle](versions/0.17.md))
- **Navigationsprüfung lief vom Arm-Paket in die Ego-Ansicht** → Viewer-Tests nie nur in der Cloud annehmen, Mac-Lauf nötig ([Quelle](versions/0.19.md))

## Verträge mit dem Spiel
- **Unity-Import dreht das Modell um 180° um Y** → Korrektur genau einmal im Einbau, Generator nie vorspiegeln ([Quelle](UNITY_EINBAU.md))
- **Anker-Leerobjekt-Drehung ist kein Vertrag** → Achsen aus `hold.muzzle_axis`/`grip_axis`; Reimport kann das nicht prüfen ([Quelle](TECHNIK.md#grenzen))
- **Unity liest aus FBX nur UV0-Tangenten** → FBX ohne Tangenten, GLB mit `TANGENT` auf UV1 ([Quelle](ENTSCHEIDUNGEN.md))
- **Umbenennen verschiebt GUIDs beim Abnehmer** → `renamed_from` im Vertrag mitliefern, kein Doppelbau ([Quelle](UNITY_EINBAU.md))
- **Vertragsformate nur additiv, Mindestfassung des Abnehmers nennen** → z. B. `minimum_consumer`, CE 0.94 für Ego 2048² ([Quelle](versions/0.16.md))
- **Blender-Reimport/SceneKit ersetzen keine Unity-Abnahme** → Offenes im Bericht nennen, Spielpassung prüft Cube Escape ([Quelle](TECHNIK.md#grenzen))
