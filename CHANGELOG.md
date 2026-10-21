# Änderungen

## 0.19.0 – Kinetic (21.10.2026)

E1 des Arm-Umbaus (Entscheidungen des Nutzers 20.10.2026): **Vertrag 5** – ein gemeinsames Ego-Arm-Rig `ego_arms` (Kette Schulter → Oberarm →
Unterarm → Hand, `Prop_R`/`Prop_L`, drei Greiffinger mit drei Gliedern + Daumen, Handgelenk-Servo, 1,4× eingebacken, 12 000 Dreiecke) statt
eingebackener Arme je Gerät. Pilot Sturmgewehr (`Reload`/`ReloadEmpty` wie Destiny, Ereigniskanäle `action`/`rig`) und Portalkanone (Stützhand
umgreift das Gehäuse) auf Vertrag 5; alle übrigen Geräte Vertrag 4 und unverändert, Rückweg `--contract 4`. Mac-Abnahme: Nachladen ohne
Durchdringung (Freifahr-Schlüssel, Fingerwächter, neue QA je Bild), Viewer für Vertrag 5, `device_scale.world_factor`; **Kardan-Handgelenk**
(`WristYoke_<S>`, `rig.version` 2, Entscheidung des Nutzers 21.10.2026); Bildregel „Greiffinger im Bild“ präzisiert. Bericht: [docs/versions/0.19.md](docs/versions/0.19.md).

## 0.18.0 – Bedrock (20.10.2026)

Konzeptgeometrie von cubeescape-formgen (geometry-spec 1) als Bauquelle: `data/concepts/` mit Herkunft (Release, Zip- und Datei-sha256),
`scripts/import_concepts.py`, Lader `concept_spec.py`/`concept_kit.py`. Pilot: Sturmgewehr = KG02 aus claude-v0.15 (Variante G, holo, Griffneigung 10,27°, Ladehebel p32 im Use-Clip,
offenes Visierfenster ohne Glas, neuer Anker `Socket_Reticle`, benannte Stützhand-Korrektur). Vertrag 4 additiv
(`minimum_consumer.concept_models`: CE-Version „offen“). Alle Dreiecksbudgets +25 % (Entscheidung des Nutzers 20.10.2026: Welt
4 500–8 000 → 6 000–10 000, Roboter 12 000 → 15 000, Ego 12 000–16 000 → 15 000–20 000; CE muss `FrameBudgetEnvelopeTests` anheben,
`minimum_consumer.triangle_budgets` „offen“). Bericht: [docs/versions/0.18.md](docs/versions/0.18.md).

## 0.17.2 – Retrace (19.10.2026)

Golden: belegter Ausweichwert für die Raketenwerfer-Roboter-Normalkarte (ein Texel, Cycles-Bake-Kipp zwischen Läufen derselben Quellen; kein Inhalt geändert).

## 0.17.1 – Retrace (19.10.2026)

Nachtrag zur Mindestversion des Abnehmers: die Migration `scout_rifle` → `trace_rifle` kommt mit Cube Escape 0.98 „Recast“.
Der Vertrag nennt jetzt diese Version; die älteren Paketgrenzen und der Rückweg zu Toolgen 0.16.0 bleiben unverändert.

## 0.17.0 – Retrace (19.10.2026)

Spurgewehr umbenannt: `scout_rifle` → `trace_rifle` (Entscheidung des Nutzers 19.10.2026; `scout_rifle` wird frei für das Scout-Gewehr KG11 aus
cubeescape-design), Vertrag 4 additiv (Bericht: [docs/versions/0.17.md](docs/versions/0.17.md)).

- ID, Asset und Clips: `trace_rifle`, `CubeEscape_TraceRifle` (Roboter `CubeEscape_TraceRifle_Robot`), `TraceRifle_*`; Ordner `Spurgewehr/`, Label und
  Geometrie gleich; Daten, Golden-Manifest, Tests und Doku nachgezogen.
- Übergang: `tools.json` › `renamed_from`; jeder Vertrag des Werkzeugs trägt `renamed_from` mit `map` alt → neu; `generate_tools.py --tool scout_rifle`
  baut mit Warnung `trace_rifle`, bis ein Werkzeug die ID wieder trägt (`tests/test_rename.py`).
- Golden: belegter Ausweichwert für die SMG-Roboter-Normalkarte (ein Texel, ausgelöst schon von der Versionszeichenkette; Gegenprobe mit `v0.16.0`).
- Mindestversionen getrennt in jedem Vertrag (`minimum_consumer`): Ego-Karten 2048² → Cube Escape 0.96 „Pinpoint“ (bisher irrtümlich 0.94);
  umbenannte IDs → CE-Version mit der Migration scout_rifle → trace_rifle (Nummer folgt, cubeescape-rules#3). Cube Escape 0.96 und älter lesen das
  0.17-Paket nicht; für sie `git checkout v0.16.0 && python3 toolgen/generate_tools.py --tier standard`.

## 0.16.0 – Finegrain (18.10.2026)

Ego-Karten in 2048² (Entscheidung des Nutzers 18.10.2026, ersetzt „Ego 2048² nein“ vom 17.10.; Wunsch der Equipment-Linie, cubeescape-rules#3),
Vertrag 4 additiv (Bericht: [docs/versions/0.16.md](docs/versions/0.16.md)). Gebaut in einer Cloud-Sitzung, am Mac abgenommen (Standard-Stufe, Golden neu, Karten- und Vorschauprüfung).

- `surface.MAP_RESOLUTION['viewmodel']` 1024 → 2048 für alle zwölf Ego-Modelle; Welt und Roboter-Variante bleiben 512². `surface.maps.resolution` der
  Ego-Verträge 2048, Dateinamen unverändert.
- Dilatation je Auflösung (`dilation_px`: 512 → 8 px, 2048 → 16 px = dieselben 8/1024 des Atlas wie bei 1024), Satzgrenze je Auflösung (2048 → 10 MB,
  gemessen 4,5–5,9 MB je Ego-Satz), Randregel als UV-Abstand ausgewiesen (`uv1.margin_px_at_map`: 2 px bei 512, 8 px bei 2048; `qa_game*.json` › `margin_px_at`).
- Golden: die 36 Ego-Karten der Waffen neu geschrieben (`stale`-Markierung getilgt, `verify_surface.py --update-golden`); die 68 Welt- und Roboter-Hashes sind
  bytegleich zu 0.15.1 geblieben.
- Am Mac gefunden und behoben: die freie Ecke wurde mit 16 px bei 1024 gegen das ganze 16-px-Band geprüft, was bei Layouts mit Inseln nahe der Ecke elf Spielexporte
  scheitern ließ (`CORNER_CHECKS`: je Karte das Eck-Texel); `verify_surface.py` bemisst die Dilatationsgrenze an einem Raster mit Randtoleranz 1e-5 (float32-UV1 der GLB; Bake rechnet
  vorher 1 Randtexel mehr bei Sturmgewehr und Bogen).
- Mindestversion des Abnehmers: Cube Escape 0.94 liest `maps.resolution`; ältere Fassung mit 1024²: `v0.15.1`.

## 0.15.1 – Toolgrip (18.10.2026)

Golden der Oberflächenkarten mit belegten Ausweich-Hashes (Bericht: [docs/versions/0.15.md](docs/versions/0.15.md) › 0.15.1); keine Modell- oder Kartenänderung.

- Befund: Der Cycles-Normal-Bake der Roboter-Varianten von Spur- und Scharfschützengewehr kippt bei gleicher Eingabe und gleichen Einstellungen je einen Texel um eine Stufe (Blaukanal 253/254, 1 von 3 Läufen, jede Thread-Zahl); `verify_surface.py` war deshalb je nach Lauf rot.
- `tests/golden/surface/manifest.json` › `alternates`: je Karte die belegten anderen sha256 (nur diese zwei Karten); `verify_surface.py` akzeptiert Hauptwert oder Ausweichwert, `--update-golden` behält sie nur, wenn die Karte zwischen bekannten Werten kippt.
- Tests: `tests/test_verify_surface.py` › `GoldenAlternatesTests` (unter Blenders Python).

## 0.15.0 – Toolgrip (18.10.2026)

Ego-Werkzeuge wie die Waffen: Wunsch aus Cube Escape 0.85 „Quickdraw“ Phase 4 (Bericht: [docs/versions/0.15.md](docs/versions/0.15.md)), Vertrag 4 unverändert.

- Portalwerfer, Magnetgreifer, Taschenlampe: `arm_pose` je Arm, Handgelenk in jedem Clipbild ≤ 55° (Ruhe 45,6°/48,7°/46,7° statt 82°/84°/89°).
- Use-Ereignis `Fire`/`Grab`/`Switch`, neuer Clip `<Name>_Inspect_B`, `lowered` in Draw/Holster 14–17 mm tiefer (vorher ≈ 2 mm); Waffen, Bogen und alle Weltmodelle bytegleich.
- Prüfung: `tests/test_ego_clips.py` (EgoToolTests), `verify_output.py`, `qa_viewmodel.json` › `ego_clips.lowered`; Bewegungsbeleg `scripts/ego_video.py` (MP4, Kontaktbogen).
- Mindestversion: keine (Namen und Knoten bleiben); `Inspect_B` und die Ereignisse nutzt der CE-Stand mit Phase 4; ältere Fassung: `main` bei `8abf588` (0.14.0, ohne Tag).

## 0.14.0 – Fieldfit (17.10.2026)

Roboter-Variante der Weltmodelle für die acht Unterhand-Waffen (Entscheidung des Nutzers 17.10.2026, „sehr wichtig“; Bericht: [docs/versions/0.14.md](docs/versions/0.14.md)), Vertrag 4 additiv.

- `<Asset>_Robot` je Gewehr: Verformung des Designs (`weapon_designs.py` › `ROBOT`): Länge = CE-Länge in der Hand, `Socket_SupportHand` 0,09 m vor `Socket_Hand`, Schaft 0,11 m dahinter, Querschnitt × 1,15–1,6; Weltmodell, Ego, Clips und ADS unverändert (GLB bytegleich zu 0.13).
- Stufen `robot`, `game_robot`, `surface_bake_robot`: `<Asset>_Robot_Game.*`, `unity_contract_robot.json` (Block `robot`), eigene Karten 512²; Budget `game_budget.json` › `robot` 12 000.
- Prüfung: `tests/test_robot_variant.py`, `verify_output.py`, `scripts/compare_models.py`; Sichtprüfung `scripts/robot_preview.py` (`Previews/robot_variant.png`, `robot_contact.png`); Viewer-Varianten „Roboter-Weltmodell“/„Roboter-Spielmodell“.
- Mindestversion: der CE-Stand, der `unity_contract_robot.json` liest; ältere Fassung `--contract 3` oder `v0.13.0`.

## 0.13.0 – Enamel (17.10.2026)

Oberflächen der Waffen 1–9 nach dem Konzeptblatt „Waffen Texturen 1–9“, Stufe A im heutigen Rahmen (Bericht: [docs/versions/0.13.md](docs/versions/0.13.md)), Vertrag 4 additiv.

- Relief je Teil in der Normalkarte (Rändel, Rillen, Lamellen, Panel-Fugen, Bürstung, Korn; ≤ 0,3 mm, Fields bytegleich), Rezepte in `data/surface_recipes.json`.
- Decals als einfarbige Regionsgewichte in W0/W1 (eigene Strichschrift, ImageMagick, `data/decals.json`, Anker `DECALS`), QA je Decal; Block `surface.recipe` (Werkstoff, Glätte, Abnutzung, Leuchtfarbe, Decals) für Cube Escape 0.76; `BAKE_SCHEMA` 2.
- Sichtprüfung ohne Unity: `scripts/surface_preview.py` (`Previews/surface_<Waffe>.png`, Kontaktbogen); Golden `tests/golden/surface` (sha256 aller 72 Karten, keine Referenzbilder) in `verify_surface.py`.
- Leuchtfarbe nach dem Blatt (Entscheidung des Nutzers 17.10.): Pistole solar, Sturm- und Spurgewehr arc, Impuls- und Fusionsgewehr void, Scharfschützengewehr und MP energy; kein Werkzeug mehr kinetic.
- Nachträge aus dem CE-0.75-Import: Anker-Drehung ist kein Vertrag (nur Position, Achsen aus `hold.muzzle_axis`), `hold.ads_eye_distance_m` auf die Abstände von Cube Escape 0.75.
- Mindestversion: Karten Cube Escape 0.71, Rezept 0.76; ältere Fassung `v0.12.0`, ohne Karten `--contract 3`.

## 0.12.0 – Sightline (16.10.2026)

Zulieferung T1/T2/T3/T5/T6 für Cube Escape 0.72 „Sightline“ (vormals 0.66 „Deadeye“) (Bericht: [docs/versions/0.12.md](docs/versions/0.12.md)), Vertrag 4 additiv (auf 0.11.0 Primer).

- `Socket_Sight` je Waffe, Visierlinie über dem Gehäuse (Bildmitte frei); Scopes mit offenem Okular, `Socket_Eye` an der Linse (Ziel-Clips von Sturm-, Impulsgewehr und Raketenwerfer zielen dafür neu über das Gehäuse); `hold.sight_socket`/`sight_kind`/`eye_socket`/`eye_radius_m`/`ads_eye_distance_m`.
- Marker `Fire` im Use-Clip am `fire_frame`; Fire/AimFire der Ego-Clips nennen `Fire` neben `Shot`.
- Finger animiert (Abzugfinger in Fire/AimFire, Nachfassen in Reload), `FusionRifle_Charge` als Zustands-Loop (letzter Clip), `ce_action_clips`.
- Z-Fighting behoben (Befund Mac-Viewer): Dekore, Ringe, Linsen ≥ 0,5 mm über ihrer Unterlage (Schrotflinte, Pistole, Sturm-, Impuls-, Scharfschützen-, Spur-, Fusionsgewehr, MP); neuer Viewer-Determinismus-Test (8 Läufe, 1 px) in `check_output.sh`.
- UV1-Drehgrenze (`uv1_source`, Vertrag 4) 0,5° statt 0,1°: Packer-Rauschen je Plattform (Magnetgreifer Mac 0,097°, Linux 0,1015°), Entscheidung des Nutzers.
- Prüfung: Handkontakt je Clipbild, ADS-Zielpose (Bildmitte frei, ≤ 25 % über der Mitte, Fingerbefund) in `qa_game_fps.json` › `ads`.
- Mindestversion des Abnehmers: keine (Cube Escape 0.72 liest `Socket_Sight` live aus dem Modell, ohne ihn gilt das Ersatz-Visier hinter der Mündung); Mindestversion für Vertrag 4 bleibt Cube Escape 0.71; Fassung ohne die neuen Anker: Stand `624a011` (0.11.0 Primer) erzeugen, ohne Karten `--contract 3`.

## 0.11.0 – Primer (16.10.2026)

Vertrag 4 für das Bemalen im Spiel (Cube Escape 0.71 „Maskwork“, Entwurf und Spike in der Notiz `ce071-vertrag4-an-toolgen.md`, Freigabe des
Nutzers über die Equipment-Sitzung): UV1, GLB-Tangenten auf UV1, Maskenkarten W0/W1/Fields/Normal und Block `surface`
([UNITY_EINBAU](docs/UNITY_EINBAU.md) › Maskenkarten und UV1, [TECHNIK](docs/TECHNIK.md) › Oberflächenkarten).

- Vertragsänderung (`format` 4, additiv): UV1 (`TEXCOORD_1`) auf allen Spielmodellen samt LOD1 und Clips-Datei, je Werkzeugteil vor dem
  Zusammenführen, Ego übernimmt die Welt-UV1 (Waffen und Bogen; Portalwerfer, Magnetgreifer, Taschenlampe eigenes Atlas); Hände ohne Insel.
  Neue Stufe `surface_bake` (standard/full, `heavy_lock`): Karten Welt 512², Ego 1024², Satz 0,61–1,98 MB. FBX ohne Tangenten (CE rechnet sie).
  **Mindestversion des Abnehmers: Cube Escape 0.71**; ältere Fassung: `python3 toolgen/generate_tools.py --tier standard --contract 3 --output output/_contract3`.
- Kollaps-Dezimierung faltet UV1 (Portalwerfer 250 Dreiecke): Entfaltung nach der Dezimierung, LOD0 und LOD1 aller 26 Modelle überlappungsfrei.
- Prüfung: `./check` (206 Tests; die 7 numpy-Tests laufen unter Blenders Python, grün), `--tier standard` alle 13 grün (1025 s, partiell), Wiederholung 13 Cache-Treffer,
  `verify_output.py` 768 Prüfungen, `scripts/verify_surface.py` (neu, unabhängig aus GLB/PNG) 26 Modelle grün, Bake bitgleich bei 1 und 8 Threads
  (Taschenlampe, Pistole), `--contract 3` ohne UV1/Karten, `check_output.sh` grün (Viewer 190). Codex: Abnahmeskript (`luna`, im Sandkasten
  ohne Blender; Lauf und Korrekturen Claude); Prüfung `sol` 4 Befunde, behoben: Überlappungsfläche bei Punkt-Dreiecken, Inselverschweißung
  im Abnahmeskript, Hinweis `wrapMode` Clamp; Nullflächen-Dreiecke der Entfaltung bleiben (QA zählt sie: 635 in 26 LOD0, höchstens 165).

## 0.10.0 – Steadyhand (16.10.2026)

Pistole beidhändig im Becher-Griff wie in Destiny (Wunsch des Nutzers über die CE-Sitzung Ego-Waffenhaltung): die linke Hand umfasst die
rechte von links unten, linker Unterarm von links unten ([UNITY_EINBAU](docs/UNITY_EINBAU.md) › Waffen in der Hand).

- Vertragsänderung: Pistole `hold.two_handed` true, neues Feld `hold.support_grip` (`cup` Pistole, `underhand` Gewehre), `Socket_SupportHand`
  der Pistole von (0, −0,05, 0,034) am Rahmen nach (0,017, 0,0039, −0,0155) an die linke Griffseite (Welt- und Ego-Modell; übrige Anker,
  Geometrie und Clips gleich). Mindestversion des Abnehmers: Cube Escape mit beidhändiger Pistolen-Haltung (CE nach 0.66); ältere Fassung:
  `git checkout 384f9e2 -- data/tools.json data/viewmodels.json scripts/tool_assets/weapon_designs.py` und neu erzeugen (384f9e2 = 0.9.0).
- Ego: linkes Handgelenk in Ruhe 36,5°, in allen Clips höchstens 48,9° (rechts 52,1° aus 0.8.0), `Wrist_L` wie bei den Gewehren, Bildausschnitt
  auch bei 1,7×, linke Finger ohne Überschneidung mit den rechten; beim Nachladen bleibt die linke Hand am Griff (das Magazin löst sich
  nur 2,5 cm, sonst schwebte es neben der Hand); Pistolen-Clips (Sprint, Senken, Inspect, Zielen 8 Frames) dafür angepasst.
- Prüfung: `./check` (183 Tests), `--tier standard` alle 13 grün, Wiederholung 13 Cache-Treffer, `verify_output.py` 430 Prüfungen, `--contract 1`
  quick (Pistole). Codex nur Prüfung (5-h-Kontingent bei 25 % Rest, Umsetzung durch Claude): `luna` 1 Befund (unzutreffend), `sol` nach
  dem Reset 2 Befunde (Finger durchdrangen sich 2,9 mm, Magazin schwebte beim Nachladen), behoben.

## 0.9.0 – Cadence (16.10.2026)

Ego-Zustandsclips für alle Ego-Modelle: Waffen 15 (Idle, Walk, SprintIn/Sprint/SprintOut, Fire, AimIn/AimIdle/AimFire/AimOut, Draw,
Holster, Inspect_A/B, Reload), Werkzeuge 8 ([EGO_CLIPS](docs/EGO_CLIPS.md), [TECHNIK](docs/TECHNIK.md) › Ego-Clips).

- Vertragsänderung (Format 3, abwärtskompatibel): neue Datei `<Asset>_FPS_Game_Clips.fbx/.glb` (ein Take `<Name>_EgoClips`), `clips[0]` bleibt
  `<Name>_Use` in der Hauptdatei, danach je Clip Framebereich, Loop, Posen, Events; Block `ego_clips` (Namen als Konstanten, Übergänge).
  Mindestversion des Abnehmers: keine für den bisherigen Einbau (CE ab 0.64 liest `clips[0]`); ältere Fassung: `--contract 2`.
- Abgestimmt mit CE 0.66: Fire/AimFire höchstens Abklingzeit der Waffe (Pistole 0,6 s … Raketenwerfer 2,0 s), Schuss bei 0, Fusion ohne
  Aufladen; Draw 0,5 s / Holster 0,33 s (Pistole 0,38/0,29 s); Vertragsfelder `state`, `from`, `to`. Reload bleibt (Auftrag des Nutzers).
- Geprüft je Frame: Handgelenk < 55° (Waffen max. 52,7°), Hände im Bild, Ellbogenhälften außerhalb (auch 1,7×; Ausnahme Stützarm beim Zielen,
  Entscheidung des Nutzers), Kontakt, Clipgrenzen exakt, kein Zucken, Visier in AimIdle mittig; Nachladeteile `Anim_Magazine`/`Anim_EnergyCell`.
- Prüfung: `./check` (183 Tests), `--tier standard` alle 13 grün, Wiederholung 13 Cache-Treffer, `verify_output.py` 430 Prüfungen,
  `--contract 2` quick (Pistole). Codex: Clip-Tabelle und Waffenklassen umgesetzt; Prüfung `sol` 5 Befunde, 4 behoben (1 unzutreffend).

## 0.8.0 – Gunmetal (16.10.2026)

Waffen 1–9 detailreicher und mit den Ausrüstungs-Slots von Cube Escape ([TECHNIK](docs/TECHNIK.md) › Waffen-Module, [UNITY_EINBAU](docs/UNITY_EINBAU.md) › Ausrüstungs-Slots).

- Module je Waffe: Verkleidungen mit Fugen, Seitenpanzer, Anzeigen (zur Ego-Kamera), Energiezellen, Kühlrippen, Akzente, Griffsporn;
  Anker, Knoten, Pivots, Clips und Maßstab gleich wie 0.7.1 (gegen die Verträge in Cube Escape 0.63 verglichen).
- Vertragsänderung (Format 2): Waffen-Slots `MT_Primary/Secondary/Accent/Metal/Energy/Emission/Detail`, `material_convention`, Block `equipment`;
  Hände und übrige Werkzeuge bleiben bei `M_*`. Mindestversion des Abnehmers: Cube Escape 0.64 (Equipment-Import);
  ältere Fassung: `python3 toolgen/generate_tools.py --tier standard --contract 1`.
- Ego-Hände/-Arme (Befund CE 0.65): Stützhand im Untergriff, Unterarme diagonal von unten (`arm_pose`, Daten), neue Prüfungen
  Handgelenkwinkel je Bild (Ziel 45°, Grenze 55°; vorher 105°/160°, jetzt rechts 46–52°, links 30–31°), Läufe in der Ego-Pose fast
  waagerecht, Bildausschnitt bei 1,7× Vergrößerung, Knoten `Wrist_R`/`Wrist_L` für die Messung im Spiel (additiv); nur Hand-/Armknoten
  und die Ego-Pose ändern sich.
- Budgets der Waffen +1 000–2 000 Dreiecke (Welt 4 500–8 000, Ego 13 000–16 000; Schätzungen); `verify_output.py` kennt die Slot-Grenze.
- Prüfung: `./check` (157 Tests), `--tier standard` alle 13 Werkzeuge grün, Wiederholung 13 Cache-Treffer, `verify_output.py` 378 Prüfungen;
  `--contract 1` quick für Pistole und Schrotflinte. Codex-Prüfung (`gpt-6.1-sol`, high): 3 Befunde, behoben (1,7×-Rahmen verbindlich, kein `-Infinity` im QA-JSON, Waffenquellen ohne `MT_`-Slot brechen ab). Grenzen: kein `--tier full`, kein Viewer-Bau, keine Unity-Abnahme.

## 0.7.1 – Ironsight (16.10.2026)

Vertragsänderung auf Wunsch des Nutzers (über die Cube-Escape-Sitzung): `Socket_SupportHand` von Portalkanone, Magnetgreifer und
Taschenlampe liegt jetzt am Gehäuse statt 35–37 mm daneben.

- Portalkanone und Magnetgreifer: (0, −0,045, −0,008) → (0, −0,045, 0,03), Abstand zur Oberfläche +1 mm; Taschenlampe: (0, −0,018, 0,018) →
  (0, −0,018, 0,07), 15 mm im Gehäuse. Alle anderen Anker (`Socket_Hand`, `Socket_Muzzle`, `Socket_Grab`, `Socket_Camera`) unverändert; Vertragsformat 1 unverändert.
- Die Ego-Hände ändern sich nicht (Stützhand der älteren Werkzeuge sitzt weiter über `support_offset`); `hand_touch_m` ≤ 0,13 mm.
- Mindestversion des Abnehmers: Modelle aus Toolgen ≥ 0.7.1; wer `Socket_SupportHand` dieser drei Werkzeuge nutzt, muss neu importieren.
  Ältere Fassung: `git checkout 807a6d9 -- scripts/tool_assets/Portalkanone/create_portal_gun.py scripts/tool_assets/Magnetgreifer/create_magnet_gripper.py scripts/tool_assets/Taschenlampe/create_flashlight.py`
  und neu erzeugen (807a6d9 = 0.6.3).
- Prüfung: `./check`, `--tier standard` für die drei Werkzeuge.

## 0.7.0 – Ironsight (15.10.2026)

Neun Handwaffen (Konzepttafel 1–9, ohne Bogen) als Werkzeuge: Pistole, Sturmgewehr, Impulsgewehr, Schrotflinte, Scharfschützengewehr,
Maschinenpistole, Fusionsgewehr, Spurgewehr, Raketenwerfer. Technik: [docs/TECHNIK.md](docs/TECHNIK.md) › Waffen 1–9.

- Je Waffe Welt- und Ego-Modell, Anker (`Socket_Hand`, `Socket_SupportHand`, `Socket_Muzzle`, `Socket_CenterOfMass`), Einzelclip `<Name>_Use`
  (97 Bilder, Ruhepose am Ende), Spiel-Export mit Vertrag, Elementfarbe (kinetic, energy, solar, void, arc); keine Munition, keine Regeln.
  Ein Baukasten (`weapon_kit.py`, `weapon_designs.py`) mit je Waffe einem Ordner aus fünf Starter-Dateien statt neun Kopien.
- Vertrag: Block `hold` (Anker, Griffachse, Haltewinkel, Mündungsachse, Element), `anchors[].surface_distance_m` und QA
  `grip_sockets_on_tool` (Handanker höchstens 4 mm außerhalb des Werkzeugs; für die älteren Werkzeuge nur Information: Portalkanone und
  Magnetgreifer 37 mm, Taschenlampe 35 mm außerhalb; mit 0.7.1 korrigiert).
- Use-Clips schreiben keine Wurzelkurven (QA `clip_root_free`, `clips[0].root_curves`): unabhängig von der 180°-Drehung des Unity-Imports.
- Ego: Stützhand am Anker `Socket_SupportHand` mit eigenem Handschutz-Radius (`support_socket`, `support_radius`), QA `hand_touch_m`
  (Hand berührt das Werkzeug, Grenze 8 mm), Rückstoß (`motion`, `motion_profiles.recoil_impulse`), je Werkzeug anpassbare Kopfgrenzen
  (`head.limits`). Die älteren Werkzeuge behalten ihr Verhalten (neu nur der Messwert `hand_touch_m`).
- Palette: `M_GlowVoid`, `M_GlowArc`, `M_GlowKinetic` (neu in Cube Escape). Budgets: Welt 3 500–7 000, Ego 11 000–15 000 Dreiecke (Schätzungen).
- Prüfung: 141 Unit-Tests (neu `tests/test_weapons.py`, Rückstoß in `test_motion.py`), `--tier standard` für alle 13 Werkzeuge grün,
  `verify_output.py` 360 Prüfungen (53 Modelle). Grenzen: kein `--tier full`, keine Unity-Abnahme.

## 0.6.3 – Sightline (15.10.2026)

Doku-/Vertragspatch: die 180°-Drehung beim Unity-Import (Achsenfund aus dem Cube-Escape-Einbau).

- `docs/UNITY_EINBAU.md`: Abschnitt „Achsen und die 180°-Drehung“ (Befund, betroffene Anker, Korrektur durch den Einbau, nie doppelt).
- Vertrag: `axes.fbx.export_yaw_degrees` (180) und `export_yaw_note`; reine Dokumentation, Anker- und Modellwerte unverändert.
- Test: `ImportYawTests` (Anker (−x, y, −z) wird durch die Halbdrehung auf den Vertragswert zurückgeführt).
- Generator, Modelle und Pipeline unverändert; kein Blender-Volllauf.

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
