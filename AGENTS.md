# Toolgen – Regeln für KI-Agenten

**Werkzeuge (Pflicht, auch für Codex ohne Hooks):** `./ce reserve <Name>` vor der ersten Änderung einer Version (Patch: Branch `claude/<repo>-patch-<kurzname>`) ·
`./ce search <Begriffe>` vor dem Lesen langer Docs · `./ce lock unity|blender|gpu -- <Befehl>` für schwere Läufe · `./ce check` vor Commit ·
`./ce judge` vor Merge (Versionen) · Belege `./ce clip|sheet|still`, Bildurteil `./ce diff` · `./ce report` am Ende (Ist-Zeit Warten/Rechnen/Lesen/Umsetzen).

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
- Roboter-Variante der acht Gewehre (`<Asset>_Robot`, 0.14): Verformung des Designs (`weapon_designs.py` › `ROBOT`), nie ein zweites
  Modellset; sie ändert Weltmodell, Ego-Modell und Clips nicht (Beleg `scripts/compare_models.py`).
- Vertrag 5 (0.19): **ein** gemeinsames Ego-Arm-Rig (`toolgen/ego_arms.py`, Paket `ego_arms`), Geräte mit `tools.json` › `game_contract` 5
  hängen ohne Arme an `Prop_R` (`ego_rig.py`, `game_export_rig.py`, Daten nur in `data/ego_arms.json`); Rig-Änderung = `rig.version` +1,
  Rückweg `--contract 4`; `first_person.py` bleibt der Weg für Vertrag 4. Vertrag: [docs/UNITY_EINBAU.md](docs/UNITY_EINBAU.md) › Vertrag 5.
- Das Spielprojekt Cube Escape wird aus diesem Repo nicht verändert. Unity-Spielverhalten bleibt dort.
- Keine Animation läuft automatisch. Aktionsclips (Use, Fire, Draw …) laufen einmal und kehren in die Ruhepose zurück; Loop ist
  eine Viewer-Prüfoption. Ausnahme (Nutzer, 16.10.2026): Ego-Zustandsclips Idle, Walk, Sprint, AimIdle (0.9.0), FusionRifle_Charge (0.11.0, und was später
  ausdrücklich als Zustand gilt) dürfen Schleifen sein, weil Cube Escape sie per Zustandslogik startet und stoppt; Autoplay bleibt aus.
- Modellteile, Materialien, UVs, Einheiten, Hierarchie und bewegliche Anker müssen im FBX-/GLB-Reimport erhalten bleiben.

## Wahrheit und Aktualität

Code ist die Wahrheit, dann README, `docs/TECHNIK.md`, `CHANGELOG.md`. Version und Stand: `toolgen/version.py`,
`git describe --tags`, `CHANGELOG.md` (App und Berichte übernehmen die Version daraus). Vor Systemarbeit `git worktree list`,
lokale Änderungen und laufende Prozesse prüfen; laufende Umbauten nicht überlagern. Dauerhafte Entscheidungen mit Grund:
[docs/ENTSCHEIDUNGEN.md](docs/ENTSCHEIDUNGEN.md). Globale Regeln (Actions-Budget, Unteragenten und Modelle, Kontingent sparen,
Codex als Unteragent, Versionsberichte): Repo `~/Claude/cubeescape-rules` (`~/.claude/CLAUDE.md` und `~/.codex/AGENTS.md` sind
Links darauf).
**Erfahrungen:** [docs/LESSONS.md](docs/LESSONS.md) (≤ 60 Zeilen, eine Zeile je Lehre, Link zur Langform) wird vor Arbeit gelesen und von
Schwesterprojekten quergelesen (globale Regel › Erfahrungen festhalten und querlesen); Langform in `docs/TECHNIK.md`, `docs/ENTSCHEIDUNGEN.md`.
Schwesterprojekte: Cube Escape `Docs/LESSONS.md`, Robogen/Cubegen/Design `docs/LESSONS.md`.
Berichte einer Sitzung stehen in `report.md` im Worktree-Wurzelordner (ungetrackt, `.git/info/exclude`).

## Befehle

`./check` (schnell: Doku-/Konfigurationsprüfung und Python-Tests, kein Blender), `./check --full` (Doku plus
`scripts/check_output.sh`, schwer), `./check --nightly` (0.20: `scripts/nightly.sh` – `--tier full` aller Werkzeuge plus `check_output.sh`,
einmal täglich auf `main`, vom Nutzer oder `launchd` gestartet, nie als Workflow), `./release` (Trockenlauf: Version, CHANGELOG, Tag, Release-Branch; `--execute` nur auf
Nutzerwunsch). Konfiguration: `.ce-repo.json`. Die gemeinsamen Werkzeuge liegen als eingebettete Kopie in `scripts/ce_tools/`
(erzeugt mit `python3 $CE_TOOLS/ce_sync.py --repo .` aus dem Plugin `ce-agent-tools`, nie von Hand ändern, Prüfung
`python3 scripts/ce_tools/ce_lint.py`). Das Plugin meldet vor `git commit` bei geänderten Docs/Skills die Lint-Ergebnisse (nur Warnung).

Arbeitsanweisung: [.agents/skills/tg-testing/SKILL.md](.agents/skills/tg-testing/SKILL.md).

| Stufe | Anlass | Ausgabe |
|---|---|---|
| `quick` | nach Code-Änderungen, **vor Commit** | `output/_quick`: Modelle, Animation, Geometrie-QA, Spiel-Export mit QA, Viewer-Daten; keine Bilder |
| `standard` | vor Merge nach `main`, **nur geänderte Werkzeuge** (`--tool`, aus `testplan.py`) | `output/_standard`: zusätzlich unabhängiger Reimport, kleine Renderings (50 %, 12 Samples), Aktions-GIFs, Bake halb (Viewmodel 1024², `preview: true`) |
| `full` | Nachtlauf auf `main`, Lieferstand, Release | `output`: dieselben Prüfungen, volle Auflösung, 40 Samples, Bake 2048² |

Rendern ist vom Commit gelöst (0.20, globale Regel › Rendern und Prüfen): vor Commit nur `quick` plus gezielte Bilder der geänderten
Werkzeuge; die vollen Bildstufen, Golden-Hashes und der Determinismus-Test laufen gebündelt im Nachtlauf. Vorher: `standard` aller 13
Werkzeuge 43,5 min vor jedem Commit (0.16), `surface_bake` 2048² 100–460 s je Werkzeug.
Zuerst `python3 scripts/testplan.py` (kleinster Prüfweg aus dem Diff, `--run` führt ihn aus). Dann
`python3 toolgen/generate_tools.py --tier quick`; danach unverändert wiederholen: Cache-Treffer, unveränderte Dateien.
`--no-cache` umgeht Treffer und erzeugt alles neu. Der Cache ist geteilt (`~/Library/Caches/CubeEscapeToolgen/cache`,
`TOOLGEN_CACHE`, `TOOLGEN_CACHE_LIMIT_GB`) und arbeitet je Stufe: Schlüssel aus Quellen-Closure, Vorstufen-Hashes, Blender-Version
und bei Bildern Samples/Gerät, nicht aus Dateizeiten oder Pfaden; jeder Treffer prüft die Datei-Hashes erneut. Eine neue Stufe ist
ein Eintrag in `STAGES` (`generate_tools.py`); Änderungen an nicht erfassten Umgebungsbedingungen erfordern `STAGE_SCHEMA`/
`CACHE_SCHEMA` zu erhöhen oder einen zusätzlichen Schlüssel. Aufbau und Regeln: [docs/TECHNIK.md](docs/TECHNIK.md) › Cache und Worker.
Schwere Läufe (`--tier full`, Stufe `surface_bake`, `scripts/check_output.sh`, `verify_surface --determinism`) warten auf die
**Blender-Sperre** `scripts/heavy_lock.py --resource blender` (ce-agent-tools 0.5.0: eine Sperre je Ressource; eine Unity-Regression von
Cube Escape läuft daneben, ein zweiter Blender-Lauf wartet; `CE_HEAVY_LOCK=0` überspringt). Renderings in `quick`/`standard`, GIFs,
Viewer-Screenshots und Kontaktbögen sind nicht schwer und nehmen keine Sperre. Die Sperre wird nur gemeinsam mit den anderen Repos geändert.

**Cloud-Sitzungen** nur für reine Logik (Code ohne Bildbeurteilung, Daten, Doku, `./check`, `--tier quick`); alles mit Bild, Blender oder Viewer
startet direkt auf dem Mac (globale Regel › Cloud-Sitzungen, 21.10.2026). Cloud-Zeiten werden nicht bewertet.

Maximal zwei Worker standardmäßig; Threads werden unter ihnen aufgeteilt. `--workers` und `--threads` dürfen zusammen
die CPU-Kernzahl nicht überschreiten. Arbeitspakete sind isolierte Blender-Prozesse, Zusammenführung in Katalogreihenfolge.
`logs/toolgen_report.json` nennt Schritte, Zeiten, Last und Cache-Lage. Zeitband nur gegen denselben Werkzeugumfang,
dieselbe Stufe, Maschine und Worker-Zahl; schwere Last wird nicht bewertet. Keine Geschwindigkeit ohne diese Angaben behaupten.
Braucht eine Messung den Rechner für sich: Cube Escapes `pause_sessions.py run -- <Befehl>` verwenden und die Pause im
Bericht nennen. Den Editor oder Blender des Nutzers nicht beenden.

## Regeln

Jeder neue Auftrag bekommt Minor +1 und einen englischen Namen; Fortsetzungen behalten die Version.
Führend: `toolgen/version.py`, Changelog; App und Berichte übernehmen die Version daraus.
Vor Systemarbeit `git worktree list`, lokale Änderungen und laufende Prozesse prüfen; laufende Umbauten nicht überlagern.
Committen, taggen, mergen und pushen nur auf Nutzerwunsch. Haupt-Checkouts nicht ungefragt verändern. Nie Force-Push oder
nacktes `git stash`. Workflows: Push nur `main`, PR + auf Wunsch `workflow_dispatch`, Doku ignorieren, Concurrency,
Timeouts, wenige Linux-Jobs; keine Schedules ohne Auftrag. Keine Änderung an gemeinsamen Regeln ohne deren Tests.

Metal-Rendering und Cache-Regeln stehen unten unter „Pipeline-Details“; Viewer-, Plugin- und Hook-Regeln danach.

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
Ego-Gestaltung, Viewmodel-Sichtfeld und verbindlicher Bildausschnitt (drei Greiffinger plus Daumen, maximal halbe Unterarme):
[docs/TECHNIK.md](docs/TECHNIK.md) › Hände und Bewegungsgefühl; bei Änderungen vorab lesen. Spiel-Export für Unity
(`toolgen/game_export.py`, `data/game_palette.json`, `data/game_budget.json`; Ego: Stufe `game_fps`; UV1 und Maskenkarten ab Vertrag 4:
`toolgen/surface.py`, Stufe `surface_bake`): › Spiel-Export, › Oberflächenkarten, Einbau: [docs/UNITY_EINBAU.md](docs/UNITY_EINBAU.md); matte Palette, ein Renderer für statische Teile, Kollision
am tatsächlichen Modell, Öffnungen frei.

## Plugins und Hooks

Gemeinsame Quelle: [ce-agent-tools](https://github.com/ffunkfabian-hash/ce-agent-tools), Plugin `ce-shared` über
`.claude/settings.json`. Gemeinsame Regeln nicht kopieren oder abweichend neu implementieren.
Claude-Code-Plugins sind nicht automatisch Codex-Werkzeuge; alle Agenten befolgen diese Regeln auch ohne Plugin.

| Plugin / Werkzeug | Einsatz |
|---|---|
| `ce-shared` | Force-Push, geteilten Stash, Teleport und Unity auf Checkouts sperren; Profile in `.claude/agent-guard.json` |
| `hookify` | Repo-Regeln: generierte Ausgaben und Spielprojekt nicht editieren, Viewer prüfen, Teststufe vor Abschluss |
| `quick-gate-python` | Ruff und reine Python-Tests; Blender-Teststufen bleiben verbindlich |
| `code-review` | vor Release/Merge; keine Veröffentlichung ohne Nutzerauftrag |
| `github` / `gh` | Repository, Pull Requests und Releases; Actions lokal zuerst, keine Workflows ohne Auftrag |
| `engineering` / `design` | Fehlerursachen, Tests, Doku, Prüfung von Oberfläche und Vorschauen |
| Blender-MCP | **ausdrücklich erwünscht** (Nutzer, 19./20.10.2026; globale Regel › Blender-MCP): ohne Nachfrage, wenn Blender läuft – Modelle, UV, Material, Posen/Clips, Handkontakte, Probe-Bakes prüfen; eigene Szene, nie im Nutzerprojekt; Befunde in der Pipeline beheben, nie `output/` von Hand; Speichern nur über `wm.save_as_mainfile` |
| Unity / Unity-Perf | erst beim Einbau ins Spiel; dortige Skills und Testkopien verwenden |

Subagent-Definitionen: `.claude/agents/tg-test-runner.md` (prüft, schreibt keinen Code), `tg-doc-keeper.md` (nur Markdown).
Profile mit dem Wächter aus `ce-agent-tools` prüfen: `python3 scripts/check_rules.py --shared <ce-agent-tools-Pfad>`.
Diese Definitionen erteilen keinen Auftrag, andere laufende Chats anzuschreiben oder Subagents ungefragt zu starten.
Cloud-SessionStart übernimmt Robogens Blender-Python-/ImageMagick-Kompatibilität. Swift und native Viewer-Abnahme brauchen
macOS; Cloud-Läufe siehe › Befehle (Cloud-Sitzungen).

## Pipeline-Details

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.

Ausgabeschreibende Pipeline-Funktionen stehen in `STAGE_CACHE_FUNCTIONS` und `PIPELINE_CACHE_FUNCTIONS`; neue Helfer, die
Stufenergebnisse oder Modellpakete schreiben, werden dort ergänzt. Orchestrierung und Zeitberichte sind kein Anlass, identische Modelle neu zu bauen.
