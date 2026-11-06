# Toolgen – Regeln für KI-Agenten

Zentraler Repo-Einstieg und globale Regeln: [Nexogen](https://github.com/ffunkfabian-hash/cubeescape-nexogen) (Zuständigkeiten, Abhängigkeiten, Live-Status). Fachwissen und Prüfbelege hier.

## Harter Kern

Quelle: Nexogen `templates/kern.md`, nur dort ändern; gilt auch in Cloud-Sitzungen.

1. Kein Commit direkt auf `main`.
2. Kein Force-Push, keine überschriebenen Branches oder Tags.
3. Nichts Fremdes anfassen oder löschen: andere Sitzungen, Worktrees, Stash, Haupt-Checkout.
4. Merge nach `main` nur mit Ja des Nutzers, außer Patch bis 100 Zeilen ohne Format, Vertrag, Kernpfad bei grünem `merge-check`; Tag, Release, Repo öffentlich machen immer nur mit Ja.
5. Tests nie löschen oder abschwächen, um grün zu werden.
6. Keine Zugangsdaten, kein fremdes Material, keine großen Binärdaten nach außen (öffentliche Repos, fremde APIs).
7. Formate, Verträge und IDs nur mit Migration; IDs sind ewig.
8. Nichts als fertig melden, was nicht geprüft ist.

## Projekt

Gemeinsamer Werkzeug-Generator für Cube Escape. Code ist die Wahrheit, dann [README.md](README.md),
[docs/TECHNIK.md](docs/TECHNIK.md), [CHANGELOG.md](CHANGELOG.md). Antworten, Doku, UI und Commit-Messages auf Deutsch;
Code, Bezeichner, Kommentare und Log-Ausgaben auf Englisch.

- `data/tools.json` führt Werkzeug-IDs, Varianten und Bau-Schritte. IDs und exportierte Anker sind dauerhaft.
- Generatoren in `scripts/tool_assets/`, Pipeline in `toolgen/`, native Oberfläche in `viewer/Sources/`.
  Genau eine produktive Pipeline (`generate_tools.py`); `build_toolset.py` ist ein Kompatibilitätseinstieg.
- `output/` ist nicht versioniert und entsteht ausschließlich durch die Pipeline. Nie Modelle, Binärpuffer,
  QA oder Manifest von Hand ändern. `outputs/` enthält die historischen Referenzpakete und Shell-Einstiege;
  neue Lieferpakete entstehen in `output/`. Generatorcode gehört nicht mehr in diese Referenzpakete.
- `data/game_palette.json` bildet die Generator-Materialien auf Cube-Escape-Materialnamen ab (Spiel-Export); die Abbildung bleibt
  vollständig, Namen und Ergebnisdateien (`*_Game.*`, `unity_contract*.json`) sind Vertrag mit dem Spiel;
  Dreiecksbudgets stehen in `data/game_budget.json` (nicht im Generator verstecken).
- Roboter-Variante der acht Gewehre und des Scout-Gewehrs (`<Asset>_Robot`, 0.14/0.24): Verformung des Designs (`weapon_designs.py` › `ROBOT`), nie ein zweites
  Modellset; sie ändert Weltmodell, Ego-Modell und Clips nicht (Beleg `scripts/compare_models.py`).
- Vertrag 5 (0.19): **ein** gemeinsames Ego-Arm-Rig (`toolgen/ego_arms.py`, Paket `ego_arms`), Geräte mit `tools.json` › `game_contract` 5
  hängen ohne Arme an `Prop_R` (`ego_rig.py`, `game_export_rig.py`, Daten nur in `data/ego_arms.json`); Rig-Änderung = `rig.version` +1,
  Rückweg `--contract 4`; `first_person.py` bleibt der Weg für Vertrag 4. Vertrag: [docs/UNITY_EINBAU.md](docs/UNITY_EINBAU.md) › Vertrag 5.
- Das Spielprojekt Cube Escape wird aus diesem Repo nicht verändert. Unity-Spielverhalten bleibt dort.
- Keine Animation läuft automatisch. Aktionsclips (Use, Fire, Draw …) laufen einmal und kehren in die Ruhepose zurück; Loop ist
  eine Viewer-Prüfoption. Ausnahme (Nutzer, 16.10.2026): Ego-Zustandsclips Idle, Walk, Sprint, AimIdle (0.9.0), FusionRifle_Charge (0.11.0), SubmachineGun_AutoFire/AimAutoFire
  (0.24.0, gehaltenes Dauerfeuer, Nutzer 22.10.2026), Pistol_SlideLocked (0.27.0, Schlittenfang, nur `Anim_Slide`, Nutzer 24.10.2026; und was später
  ausdrücklich als Zustand gilt) dürfen Schleifen sein, weil Cube Escape sie per Zustandslogik startet und stoppt; Autoplay bleibt aus.
- Modellteile, Materialien, UVs, Einheiten, Hierarchie und bewegliche Anker müssen im FBX-/GLB-Reimport erhalten bleiben.


## Wahrheit und Aktualität

Code ist die Wahrheit, dann README, `docs/TECHNIK.md`, `CHANGELOG.md`. Version und Stand: `toolgen/version.py`,
`git describe --tags`, `CHANGELOG.md`. Dauerhafte Entscheidungen mit Grund: [docs/ENTSCHEIDUNGEN.md](docs/ENTSCHEIDUNGEN.md).
**Erfahrungen:** [docs/LESSONS.md](docs/LESSONS.md) wird vor Arbeit gelesen; Langform in [docs/LESSONS-lang.md](docs/LESSONS-lang.md), `docs/TECHNIK.md`, `docs/ENTSCHEIDUNGEN.md`.

## Patch und Version

Regel und Schwellen global (Patch bis 300 Zeilen ohne Format, Vertrag, Kernpfad; Version = Minor +1): Nexogen `templates/regeln-details.md` › Patch-Aufträge.
Kernpfade: `.ce-repo.json` › `core_paths`. Führend: `toolgen/version.py`, Changelog; App und Berichte übernehmen die Version daraus.

## Befehle

`./check` (schnell: Doku-/Konfigurationsprüfung und Python-Tests, kein Blender), `./check --full` (Doku plus
`scripts/check_output.sh`, schwer), `./check --nightly` (0.22: `scripts/nightly.sh` – `--tier full` aller Werkzeuge plus `check_output.sh`,
einmal täglich auf `main`, vom Nutzer oder `launchd` gestartet, nie als Workflow), `./release` (Trockenlauf: Version, CHANGELOG, Tag, Release-Branch; `--execute` nur auf
Nutzerwunsch). Konfiguration: `.ce-repo.json`. **Keine eingebettete Werkzeugkopie (0.26):** `./ce` ist der Lader (`tools_version` pinnt `ce-agent-tools`).
Eigene Skripte beziehen Werkzeugmodule über `scripts/shared_tools.py` (`use("ce_docs")`), nie über einen Pfad; `scripts/heavy_lock.py` ist nur die Weiterleitung. Aufräumen: `./ce tidy` (`.ce-repo.json` › `tidy`: Stufen-Ausgaben `output/_*`).

Arbeitsanweisung: [.agents/skills/tg-testing/SKILL.md](.agents/skills/tg-testing/SKILL.md).

| Stufe | Anlass | Ausgabe |
|---|---|---|
| `quick` | nach Code-Änderungen, **vor Commit** | `output/_quick`: Modelle, Animation, Geometrie-QA, Spiel-Export mit QA, Viewer-Daten; keine Bilder |
| `standard` | vor Merge nach `main`, **nur geänderte Werkzeuge** (`--tool`, aus `testplan.py`) | `output/_standard`: zusätzlich unabhängiger Reimport, kleine Renderings (50 %, 12 Samples), Aktions-GIFs, Bake halb (Viewmodel 1024², `preview: true`) |
| `full` | Nachtlauf auf `main`, Lieferstand, Release | `output`: dieselben Prüfungen, volle Auflösung, 40 Samples, Bake 2048² |


Rendern ist vom Commit gelöst (0.22): vor Commit nur `quick` plus gezielte Bilder der geänderten Werkzeuge; die vollen Bildstufen,
Golden-Hashes und der Determinismus-Test laufen gebündelt im Nachtlauf.
Zuerst `python3 scripts/testplan.py` (kleinster Prüfweg aus dem Diff, `--run` führt ihn aus). Dann
`python3 toolgen/generate_tools.py --tier quick`; danach unverändert wiederholen: Cache-Treffer, unveränderte Dateien. `--no-cache` erzeugt alles neu.
Cache (geteilt, je Stufe, Schlüssel aus Inhalten) und `STAGE_SCHEMA`/`CACHE_SCHEMA`: [docs/TECHNIK.md](docs/TECHNIK.md) › Cache und Worker.
Schwere Läufe (`--tier full`, Stufe `surface_bake`, `scripts/check_output.sh`, `verify_surface --determinism`) nur unter `./ce lock blender -- <Befehl>`
(Weiterleitung `scripts/heavy_lock.py`; Regel: Nexogen `templates/regeln-details.md` › Schwere Läufe und Sperren). Renderings in `quick`/`standard`, GIFs,
Viewer-Screenshots und Kontaktbögen sind nicht schwer und nehmen keine Sperre.

Maximal zwei Worker standardmäßig; Threads werden unter ihnen aufgeteilt. `--workers` und `--threads` dürfen zusammen
die CPU-Kernzahl nicht überschreiten. Arbeitspakete sind isolierte Blender-Prozesse, Zusammenführung in Katalogreihenfolge.
`logs/toolgen_report.json` nennt Schritte, Zeiten, Last und Cache-Lage. Zeitband nur gegen denselben Werkzeugumfang,
dieselbe Stufe, Maschine und Worker-Zahl; schwere Last wird nicht bewertet. Keine Geschwindigkeit ohne diese Angaben behaupten.
Den Editor oder Blender des Nutzers nicht beenden.

## Definition of Done

Fertig: passende Teststufe grün, neue Verhaltenstests, sichtbare Modelle und Animationen geprüft, Cache-Wiederholung,
Doku und Skills auf Endstand, Grenzen benannt. Unity-Gameplay nie aus Blender-/Viewer-Tests als geprüft ableiten.

## Viewer

Native SwiftUI-/SceneKit-App nach dem Aufbau von Robogen: linke Modellansicht, rechte scrollbare Seitenleiste,
Welt/FPS/Pfeil-Auswahl, Ansichten, Aktionssteuerung, Material-Looks, A/B-Vergleich und PNG-Export.
Nach Änderungen: `bash viewer/build.sh [output-dir]` und `bash viewer/test_viewer.sh [output-dir]`.
`python3 viewer/test_determinism.py <output-dir>` rendert jedes Modell achtmal und verlangt gleiche Bilder (Z-Fighting; Teil von `check_output.sh`).
Sichtbare Änderungen mit Screenshots prüfen; `--sidebar-check` muss bei 360 pt passen. Der Playhead beobachtet nur die
Zeitleiste, nicht die ganze Seitenleiste. Im Ruhezustand kein Wiedergabe-Timer, keine dauernden Dateizugriffe.
Die App bündelt Modelle und Backend. Ohne vorherige Generierung müssen die gelieferten Modelle direkt sichtbar sein.
Ego-Gestaltung, Viewmodel-Sichtfeld und verbindlicher Bildausschnitt (drei Greiffinger plus Daumen, maximal halbe Unterarme; nicht im
ADS – dort seit 0.25 Bildmitte frei, Visier auf der Achse, Nahebene frei, Nutzer 23.10.2026):
[docs/TECHNIK.md](docs/TECHNIK.md) › Hände und Bewegungsgefühl; bei Änderungen vorab lesen. Spiel-Export für Unity
(`toolgen/game_export.py`, `data/game_palette.json`, `data/game_budget.json`; Ego: Stufe `game_fps`; UV1 und Maskenkarten ab Vertrag 4:
`toolgen/surface.py`, Stufe `surface_bake`): › Spiel-Export, › Oberflächenkarten, Einbau: [docs/UNITY_EINBAU.md](docs/UNITY_EINBAU.md); matte Palette, ein Renderer für statische Teile, Kollision
am tatsächlichen Modell, Öffnungen frei.


## Hooks und Prüfungen hier

Plugin `ce-shared` über `.claude/settings.json`; Profile in `.claude/agent-guard.json`. Hookify-Regeln im Repo: `ausgabe-nie-von-hand`,
`cube-escape-nicht-aendern`, `teststufe-vor-abschluss` (Block vor Abschluss ohne `TOOLGEN_OK`). Die Blender-MCP-Regel steht global.
Subagent-Definitionen: `.claude/agents/tg-test-runner.md` (prüft, schreibt keinen Code), `tg-doc-keeper.md` (nur Markdown); Profile prüfen:
`python3 scripts/check_rules.py --shared <ce-agent-tools-Pfad>`. Swift und native Viewer-Abnahme brauchen macOS.

## Pipeline-Details

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.

Ausgabeschreibende Pipeline-Funktionen stehen in `STAGE_CACHE_FUNCTIONS` und `PIPELINE_CACHE_FUNCTIONS`; neue Helfer, die
Stufenergebnisse oder Modellpakete schreiben, werden dort ergänzt. Orchestrierung und Zeitberichte sind kein Anlass, identische Modelle neu zu bauen.
