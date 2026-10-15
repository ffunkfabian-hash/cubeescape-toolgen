# Toolgen – Regeln für KI-Agenten

Gemeinsamer Werkzeug-Generator für Cube Escape. Code ist die Wahrheit, dann [README.md](README.md),
[docs/TECHNIK.md](docs/TECHNIK.md), [CHANGELOG.md](CHANGELOG.md). Antworten, Doku, UI und Commit-Messages auf Deutsch;
Code, Bezeichner, Kommentare und Log-Ausgaben auf Englisch.

## Quellen und Verträge

- `data/tools.json` führt Werkzeug-IDs, Varianten und Bau-Schritte. IDs und exportierte Anker sind dauerhaft.
- Generatoren in `scripts/tool_assets/`, Pipeline in `toolgen/`, native Oberfläche in `viewer/Sources/`.
  Genau eine produktive Pipeline (`generate_tools.py`); `build_toolset.py` ist ein Kompatibilitätseinstieg.
- `output/` ist nicht versioniert und entsteht ausschließlich durch die Pipeline. Nie Modelle, Binärpuffer,
  QA oder Manifest von Hand ändern. `outputs/` enthält die historischen Referenzpakete und Shell-Einstiege;
  neue Lieferpakete entstehen in `output/`. Generatorcode gehört nicht mehr in diese Referenzpakete.
- Das Spielprojekt Cube Escape wird aus diesem Repo nicht verändert. Unity-Spielverhalten bleibt dort.
- Keine Animation läuft automatisch. Aktionsclips kehren in die Ruhepose zurück; Loop ist eine Viewer-Prüfoption.
- Modellteile, Materialien, UVs, Einheiten, Hierarchie und bewegliche Anker müssen im FBX-/GLB-Reimport erhalten bleiben.

## Teststufen und Leistung

Arbeitsanweisung: [.agents/skills/tg-testing/SKILL.md](.agents/skills/tg-testing/SKILL.md).

| Stufe | Anlass | Ausgabe |
|---|---|---|
| `quick` | nach Code-Änderungen | `output/_quick`: Modelle, Animation, Geometrie-QA, Viewer-Daten; keine Bilder |
| `standard` | vor Commit | `output/_standard`: zusätzlich unabhängiger Reimport, kleine Renderings, Aktions-GIFs |
| `full` | Lieferstand / Release | `output`: dieselben Prüfungen, volle Renderauflösung und Samples |

`python3 toolgen/generate_tools.py --tier quick`; danach unverändert wiederholen: Cache-Treffer, unveränderte Dateien.
`--no-cache` umgeht Treffer und erzeugt alles neu. Cache-Schlüssel hängen an Quellinhalt, Werkzeugdaten, Blender-Version,
Stufe und Cache-Schema, nicht an Dateizeiten. Änderungen an nicht erfassten Umgebungsbedingungen erfordern eine
Schema-Erhöhung oder einen zusätzlichen Schlüssel. Jeder Treffer prüft die Datei-Hashes erneut.

Maximal zwei Worker standardmäßig; Threads werden unter ihnen aufgeteilt. `--workers` und `--threads` dürfen zusammen
die CPU-Kernzahl nicht überschreiten. Arbeitspakete sind isolierte Blender-Prozesse, Zusammenführung in Katalogreihenfolge.
`logs/toolgen_report.json` nennt Schritte, Zeiten, Last und Cache-Lage. Zeitband nur gegen denselben Werkzeugumfang,
dieselbe Stufe, Maschine und Worker-Zahl; schwere Last wird nicht bewertet. Keine Geschwindigkeit ohne diese Angaben behaupten.
Braucht eine Messung den Rechner für sich: Cube Escapes `pause_sessions.py run -- <Befehl>` verwenden und die Pause im
Bericht nennen. Den Editor oder Blender des Nutzers nicht beenden.

## Viewer

Native SwiftUI-/SceneKit-App nach dem Aufbau von Robogen: linke Modellansicht, rechte scrollbare Seitenleiste,
Welt/FPS/Pfeil-Auswahl, Ansichten, Aktionssteuerung, Material-Looks, A/B-Vergleich und PNG-Export.
Nach Änderungen: `bash viewer/build.sh [output-dir]` und `bash viewer/test_viewer.sh [output-dir]`.
Sichtbare Änderungen mit Screenshots prüfen; `--sidebar-check` muss bei 360 pt passen. Der Playhead beobachtet nur die
Zeitleiste, nicht die ganze Seitenleiste. Im Ruhezustand kein Wiedergabe-Timer, keine dauernden Dateizugriffe.
Die App bündelt Modelle und Backend. Ohne vorherige Generierung müssen die gelieferten Modelle direkt sichtbar sein.
Ego-Gestaltung und verbindlicher Bildausschnitt (Dreifingerhände, maximal halbe Unterarme):
[docs/TECHNIK.md](docs/TECHNIK.md) › Hände und Bewegungsgefühl; bei Änderungen vorab lesen.

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
| Blender-MCP | optionaler Prüfstand in eigener Szene, nichts im geöffneten Nutzerprojekt speichern |
| Unity / Unity-Perf | erst beim Einbau ins Spiel; dortige Skills und Testkopien verwenden |

Subagent-Definitionen: `.claude/agents/tg-test-runner.md` (prüft, schreibt keinen Code), `tg-doc-keeper.md` (nur Markdown).
Profile mit dem Wächter aus `ce-agent-tools` prüfen: `python3 scripts/check_rules.py --shared <ce-agent-tools-Pfad>`.
Diese Definitionen erteilen keinen Auftrag, andere laufende Chats anzuschreiben oder Subagents ungefragt zu starten.
Cloud-SessionStart übernimmt Robogens Blender-Python-/ImageMagick-Kompatibilität. Swift und native Viewer-Abnahme brauchen
macOS; Cloud-Zeiten sind nicht mit dem Mac vergleichbar.

## Versionen, Git und Abschluss

Jeder neue Auftrag bekommt Minor +1 und einen englischen Namen; Fortsetzungen behalten die Version.
Führend: `toolgen/version.py`, Changelog; App und Berichte übernehmen die Version daraus.
Vor Systemarbeit `git worktree list`, lokale Änderungen und laufende Prozesse prüfen; laufende Umbauten nicht überlagern.
Committen, taggen, mergen und pushen nur auf Nutzerwunsch. Haupt-Checkouts nicht ungefragt verändern. Nie Force-Push oder
nacktes `git stash`. Workflows: Push nur `main`, PR + auf Wunsch `workflow_dispatch`, Doku ignorieren, Concurrency,
Timeouts, wenige Linux-Jobs; keine Schedules ohne Auftrag. Keine Änderung an gemeinsamen Regeln ohne deren Tests.

Fertig: passende Teststufe grün, neue Verhaltenstests, sichtbare Modelle und Animationen geprüft, Cache-Wiederholung,
Doku und Skills auf Endstand, Grenzen benannt. Unity-Gameplay nie aus Blender-/Viewer-Tests als geprüft ableiten.

Metal-Rendering: `--device auto` nutzt auf kompatiblen Macs die ermittelte Metal-GPU; `--device cpu` erzwingt CPU.
Das Rendergerät steckt im Cache- und Zeitbandschlüssel. Unter Fremdlast keine Beschleunigung aus Laufzeiten ableiten.

Ausgabeschreibende Pipeline-Funktionen stehen in `PIPELINE_CACHE_FUNCTIONS`; neue Helfer, die Modellpakete schreiben,
werden dort ergänzt. Orchestrierung und Zeitberichte sind kein Anlass, identische Modelle neu zu bauen.
