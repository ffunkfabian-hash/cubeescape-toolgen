# Lehren (Kurzzeitgedächtnis für Agenten)
Nur wiederkehrende Dauer-Fallen, eine Zeile je Lehre. Einmalfälle und Versionsgeschichte: Langform [LESSONS-lang.md](LESSONS-lang.md) (Suche mit `rg -n`); neue Lehren dort zuerst, wiederkehrende hierher; Langform sonst in TECHNIK.md.

## Blender/Export und Bytegleichheit
- **Golden-Fehler nach reinem Versionswechsel** → mit frischem Bau des alten Tags gegenprüfen; seit 0.23 trägt die Fingerabdruck-Toleranz Rauschen, `alternates` werden nicht mehr geschrieben, Golden nie blind neu schreiben ([Quelle](TECHNIK.md#erfahrungen))
- **Normal-Bake kippt einzelne Texel (1 von 3 Läufen, jede Thread-Zahl)** → vor Golden-Änderung 3–5× nachbacken; zwei gleiche Bauten beweisen nichts ([Quelle](TECHNIK.md#erfahrungen))
- **FBX und .blend tragen Exportzeit und absoluten Pfad** → Bytegleichheit nur für GLB und Viewer-Daten behaupten ([Quelle](TECHNIK.md#grenzen))

## UV/Bake/Oberflächen
- **Blatt-Kanal ≠ Blattbild (KG02-Schiene: dunkelgrau gezeichnet, `MT_Secondary` = beige)** → Kanal des Blatts ist Vertrag; Abweichung an formgen melden, nicht in Toolgen korrigieren ([Quelle](ENTSCHEIDUNGEN.md))
- **Gemeinsame Daten in `viewmodels.json`/`game_budget.json` ändern alle Schlüssel** → neue Daten für wenige Werkzeuge in eigene Datei (`data/ego_arms.json`) ([Quelle](TECHNIK.md#erfahrungen))

## Cache, Zeiten, Sperren
- **Neue Stufe mitten in `STAGES` ändert bestehende Schlüssel** → neue Stufen ans Ende; zwei standard-Läufe gingen so verloren ([Quelle](TECHNIK.md#erfahrungen))
- **Dateizeiten/Pfade im Schlüssel entwerten den Cache** → Inhaltshashes samt Quellen-Closure; neue Schreib-Helfer in `STAGE_CACHE_FUNCTIONS` eintragen ([Quelle](TECHNIK.md#cache-und-worker))
- **Schwere Läufe warten hinter Robogen/Cube Escape/Cubegen (Stunden)** → `heavy_lock` nicht umgehen, Zeiten unter Fremdlast nie als Zeitband werten ([Quelle](TECHNIK.md#cache-und-worker))
- **`version.py` ändern baut alle Spielstufen neu** → Version zuerst heben, dann den großen Lauf starten ([Quelle](TECHNIK.md#erfahrungen))

## Ego-Rig/Clips und Roboter-Variante
- **Wurzelkurven im Clip drehte der Unity-Import mit** → `clip_root_free`: nie Kurven auf die Wurzel ([Quelle](ENTSCHEIDUNGEN.md))

## Viewer und Determinismus
- **Stauchen schrumpft Dekor-Abstände → Z-Fighting (1,4–1,6 px)** → Koplanar-Regel auf verformten Flächen, feine Zonen 1:1 lassen, danach `test_determinism.py --runs 16` ([Quelle](TECHNIK.md#erfahrungen))
- **Navigationsprüfung lief vom Arm-Paket in die Ego-Ansicht** → Viewer-Tests nie nur in der Cloud annehmen, Mac-Lauf nötig ([Quelle](versions/0.19.md))

## Verträge mit dem Spiel
- **Unity-Import dreht das Modell um 180° um Y** → Korrektur genau einmal im Einbau, Generator nie vorspiegeln ([Quelle](UNITY_EINBAU.md))
- **Unity liest aus FBX nur UV0-Tangenten** → FBX ohne Tangenten, GLB mit `TANGENT` auf UV1 ([Quelle](ENTSCHEIDUNGEN.md))
- **Umbenennen verschiebt GUIDs beim Abnehmer** → `renamed_from` im Vertrag mitliefern, kein Doppelbau ([Quelle](UNITY_EINBAU.md))
- **Vertragsformate nur additiv, Mindestfassung des Abnehmers nennen** → z. B. `minimum_consumer`, CE 0.94 für Ego 2048² ([Quelle](versions/0.16.md))
- **Blender-Reimport/SceneKit ersetzen keine Unity-Abnahme** → Offenes im Bericht nennen, Spielpassung prüft Cube Escape ([Quelle](TECHNIK.md#grenzen))
