# Entscheidungen

Dauerhafte Entscheidungen des Nutzers mit Grund. Neue Zeilen unten anfügen.

| Datum | Entscheidung | Grund |
|---|---|---|
| 15.10.2026 | Codex-Regeln gelockert: Codex darf umsetzen; Prüfung standardmäßig mit `luna`; `sol` nur bei „Keine Befunde“ ab etwa 300 Diff-Zeilen; `astra` gesperrt | Wunsch des Nutzers: Codex-Nutzung lockern, Kontingent und Arbeit sparen |
| 15.10.2026 | Keine Wartemeldungen an den Nutzer („ich warte auf …“) | Jede Meldung kostet Kontingent (Aussage des Nutzers) |
| 15.10.2026 | Versionsberichte je Hauptversion, nicht je Patch; `CHANGELOG.md` ist die einzige Übersicht | Wunsch des Nutzers: zu viele .md-Dateien |
| 15.10.2026 | Dreiecksbudgets Ego 12–16k und Welt 5–8k sind Schätzungen (`data/game_budget.json`) | Unity-Abnahme steht aus; die Werte gehören als Daten ins Budget, nicht in den Generator, und werden nach der Abnahme angepasst |
| 15.10.2026 | Ego-FOV ist ein Datenwert: das Viewmodel-Sichtfeld ist unabhängig vom Spieler-Sichtfeld | die Hände dürfen nicht mit den Spielereinstellungen skalieren; Freigaben stehen getrennt im Vertrag (`authored_model_…`, `game_model_validated_vertical_fov_degrees`) |
| 15.10.2026 | Der Bogen ist bewusst nicht als Spielwerkzeug gedacht (Waffe) | Spielregel von Cube Escape; der Bogen bleibt Referenz-/Testmodell der Pipeline |
| 15.10.2026 | Apple-Notarisierung des Viewers gestrichen | Entscheidung des Nutzers |
| 15.10.2026 | Waffen 1–9 der Konzepttafel (ohne Bogen) werden als Handwerkzeuge erzeugt: Pistole, Sturmgewehr, Impulsgewehr, Schrotflinte, Scharfschützengewehr, Maschinenpistole, Fusionsgewehr, Spurgewehr, Raketenwerfer | Auftrag des Nutzers („Mach dich für Toolgen mal an die Waffen 1-9 (außer Bogen)“); Munition und Spielregeln bleiben außerhalb |
| 15.10.2026 | Element-Zuordnung der Waffen (KINETIC: Pistole, Sturmgewehr, Spurgewehr; ENERGY: Impulsgewehr, Fusionsgewehr; SOLAR: Schrotflinte, Raketenwerfer; VOID: Scharfschützengewehr; ARC: Maschinenpistole) | Grund nicht festgehalten: das Konzeptbild war beim Bau nicht lesbar, die Zuordnung ist ein Datenwert (`element`) und leicht änderbar |
| 15.10.2026 | Ein Baukasten (`weapon_kit.py`, `weapon_designs.py`) statt neun Kopien; je Waffe ein eigener Ordner mit fünf Starter-Dateien | die Pipeline baut je Ordner; Wartbarkeit (nichts duplizieren, Anweisung des Auftrags) |
| 16.10.2026 | `Socket_SupportHand` von Portalkanone, Magnetgreifer, Taschenlampe liegt am Gehäuse (0.7.1); übrige Anker unverändert | Freigabe des Nutzers über die Cube-Escape-Sitzung: die Stützhand schwebte 35–37 mm neben dem Gerät |
| 15.10.2026 | Waffen-Use-Clips schreiben keine Kurve auf die Wurzel (`clip_root_free`) | Befund aus Cube Escape: Der Unity-Import dreht das Modell um 180°, Wurzelkurven mussten dort mitgedreht werden |

| 16.10.2026 | Waffen 1–9 tragen im Spiel-Export die Ausrüstungs-Slots `MT_<Kanal>` (Vertrag 2, Standard); `--contract 1` erzeugt das 0.7-Layout mit `M_*`-Namen; übrige Werkzeuge und die Ego-Hände bleiben bei der Palette | Auftrag über die Cube-Escape-Sitzung (Equipment-System 0.64 Anodize): Slots nach `ColorChannels.cs`, Vertragsänderung nur abwärtskompatibel |
| 16.10.2026 | Schleifenclips nur für Ego-Zustände (Idle, Walk, Sprint und später ausdrücklich benannte Zustände); Aktionsclips bleiben Einmalclips mit Rückkehr in die Ruhepose, kein Autoplay | Freigabe des Nutzers (über die Cube-Escape-Sitzung): Ego-Zustandsanimation für 0.9.0, die Zustandslogik steuert Cube Escape |
| 16.10.2026 | Handgelenk der Ego-Hände: Ziel 45°, harte Grenze 55° (Test, je Clipbild) | Entscheidung des Nutzers nach dem Befund aus Cube Escape 0.65 (vorher 105°/160°) |
| 16.10.2026 | Loop-Markierung (`loop: true`, `autoplay: false`) genau für die Ego-Clips Idle, Walk, Sprint und AimIdle; Toolgen und Viewer starten nichts selbst, Aktionsclips (Fire, Reload, Draw …) bleiben Einmalclips zwischen benannten Posen | Freigabe des Nutzers in der 0.9.0-Sitzung („Freigeben, eng“); die Zustandslogik baut Cube Escape |
| 16.10.2026 | Beim Zielen (AimIn, AimIdle, AimFire, AimOut) darf der Unterarm der Stützhand sichtbar sein (`support_forearm_visible`); Griffarm und alle übrigen Clips bleiben bei „proximale Unterarme aus dem Bild“ | Entscheidung des Nutzers: mit dem Visier in der Bildmitte liegt die Stützhand nahe der Mitte, ihr Unterarm ist dann bei Handgelenk < 55° zwangsläufig im Bild (bis 14 % der Bildhöhe, gemessen 0.9.0) |
| 16.10.2026 | Pistole beidhändig im Becher-Griff (linke Hand umfasst die rechte von links unten, `Socket_SupportHand` an der linken Griffseite, `hold.two_handed` true), 0.10.0 | Wunsch des Nutzers über die CE-Sitzung „Ego-Waffenhaltung“ (Destiny-Haltung) |
| 16.10.2026 | Ego-Clips liegen in einer eigenen Datei `<Asset>_FPS_Game_Clips.fbx/.glb` (ein Take, Clipgrenzen über Frames); die Hauptdateien behalten nur `<Name>_Use` | ältere Cube-Escape-Stände lesen `clips[0]` aus der Hauptdatei weiter; eine Datei je Clip hätte das Modell je Werkzeug 15-mal kopiert (Schätzung 16.10.2026: 1,2 MB je Ego-FBX) |
