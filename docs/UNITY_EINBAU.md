# Einbau in Cube Escape (Unity 6, URP) – Vorbereitung

Stand 0.11.0 Primer. Der Einbau ist **noch nicht abgenommen**; dieses Dokument legt fest, was das Spiel aus den Paketen
liest, damit der spätere Einbau keine Annahmen über Toolgen treffen muss. Das Spielprojekt wird aus diesem Repo nicht
verändert; Toolgen-Dateien und Werte stehen in [TECHNIK](TECHNIK.md) › Spiel-Export.

## Dateien je Werkzeug

| Zweck | Datei | Vertrag |
|---|---|---|
| Weltmodell (liegt, wird geworfen, Anzeige) | `<Asset>_Game.fbx/.glb/.blend` | `unity_contract.json` (Renderer, LOD, Kollision, Clip) |
| Ego-Modell (Hände, Arme, Werkzeug) | `<Asset>_FPS_Game.fbx/.glb/.blend` | `unity_contract_fps.json` (Renderer, LOD, Clip, `viewmodel`) |
| Viewmodel-Kamera | `viewmodel_camera.json` | vertikales FOV, Near Clip, geprüfte Werte |
| Maskenkarten (Vertrag 4, standard/full) | `<Asset>_Game_{W0,W1,Fields,Normal}.png`, `<Asset>_FPS_Game_*.png` | Block `surface` in beiden Verträgen |
| Weltmodell in der Roboterhand (0.14, acht Gewehre, Vertrag 4) | `<Asset>_Robot_Game.fbx/.glb/.blend`, `<Asset>_Robot_Game_*.png` | `unity_contract_robot.json` (wie `unity_contract.json`, dazu Block `robot`) |
| Gemeinsame Ego-Arme (0.19, Vertrag 5, ein Paket je Lauf) | `ego_arms/CubeEscape_EgoArms_Game.fbx/.glb/.blend` | `ego_arms/unity_contract_arms.json` (Rig, Fingerposen, Look) |
| Ego-Gerät ohne Arme (Vertrag 5: Sturmgewehr, Portalkanone) | `<Asset>_FPS_Game.*` (Gerät), `<Asset>_FPS_Game_Clips.*` (Zusammensetzung, alle Clips) | `unity_contract_fps.json` `format` 5 (unten › Vertrag 5) |

Materialien: nur die Palettenmaterialien aus `data/game_palette.json` (je Weltmodell höchstens 6, je Ego-Modell höchstens 7);
die neun Waffen tragen ab Vertrag 2 stattdessen die Ausrüstungs-Slots `MT_<Kanal>` (siehe „Ausrüstungs-Slots“ unten).
Cube Escape legt beim Einbau die matten Varianten (`M_RobotBody_Matte`, `M_RobotDark_Matte`, `M_Metal_Matte`,
`M_HazardOrange_Matte`) und `M_GlowWarm` aus den Palettenwerten an; `M_GlowCyan`/`M_GlowOrange` gibt es im Spiel schon.
Die FBX-/GLB-Materialien tragen nur Namen und Palettenwerte; im Spiel werden sie auf die Spielmaterialien gelegt.

FBX-Import: `bakeAxisConversion` einschalten (siehe `axes.fbx.unity_import` im Vertrag), LODGroup entsteht aus `_LOD0`/`_LOD1`.

### Achsen und die 180°-Drehung (Achsenfund Cube Escape 0.62)

Der Vertrag rechnet Blender → Unity mit `Position = (−x, z, −y)` (Blender: oben +Z, vorn −Y; Unity: oben +Y, vorn +Z) und
exportiert FBX mit `axis_forward −Z`, `axis_up Y`, `bake_space_transform` aus. Im Spiel gemessen: Mit `bakeAxisConversion`
liegt das importierte Modell trotzdem **um 180° um die Unity-Y-Achse gedreht** gegenüber den Vertragswerten – alle Anker
(`Socket_Muzzle`, `Socket_Grab`, `Socket_Nock`, `Socket_Hand`, `Socket_SupportHand`, `Socket_Camera`) lagen bei (−x, y, −z)
der Vertragswerte, das Werkzeug zeigte nach hinten. Die Ursache liegt in der Achsen-/Vorwärts-Umrechnung zwischen Blender-FBX-Export
und Unitys Importer, nicht an einzelnen Modellen; sie wurde nicht weiter im Importer zerlegt, nur gemessen (Anker-Test
`ToolgenModelTests` im Spiel).

**Korrektur macht der Einbau, nicht der Generator:** Cube Escape dreht die Wurzel des Prefabs um 180° um Y im Weltraum
(`Quaternion.Euler(0, 180, 0) * localRotation`, Welt- wie Ego-Prefab) und liest danach die Anker; die Vertragswerte bleiben unverändert und werden
nicht vorgedreht. Der Vertrag nennt den Wert als `axes.fbx.export_yaw_degrees` (180) mit Hinweis `export_yaw_note`.
Wer den FBX anders einbaut: genau einmal anwenden, nie doppelt. GLB (X-Spiegelung des Unity-glTF-Importers) wurde nicht gemessen; der
Wert gilt für FBX. Der Generator bleibt bewusst unverändert, damit bereits eingebaute Modelle nicht doppelt korrigiert werden.

### Umbenannte Werkzeuge (0.17.0 Retrace, jedes Vertragsformat additiv)

Das Spurgewehr heißt ab Toolgen 0.17.0 `trace_rifle` (bis 0.16 `scout_rifle`): Ordner `trace_rifle/`, Dateien `CubeEscape_TraceRifle_*`,
Clips `TraceRifle_*`, Roboter `CubeEscape_TraceRifle_Robot_*`, Wurzeleigenschaft `ce_weapon_class` `trace_rifle`. Modell, Anker, Clips und
Karten sind sonst gleich. Jeder Vertrag des Werkzeugs trägt den Block `renamed_from` (`tool`, `asset`, `robot`, `clip_stem`, `since`,
`map` alt → neu): Der Abnehmer ersetzt jeden Schlüssel von `map` durch seinen Wert in Ordner-, Datei-, Prefab- und Clipnamen und verschiebt
die Dateien samt `.meta` (GUIDs bleiben, Verweise in Szenen und Assets halten). Spielstände und Kataloge, die die alte ID speichern, bilden
`scout_rifle` → `trace_rifle` ab, solange es kein anderes Werkzeug `scout_rifle` gibt; danach gehört die ID dem Scout-Gewehr (KG11).
**Mindestversionen des Pakets ab 0.17.0, getrennt** (jeder Vertrag, Block `minimum_consumer`): `first_person_maps_2048` – Ego-Karten 2048²
brauchen **Cube Escape 0.96 „Pinpoint“**; `renamed_tool_ids` – die neuen Namen brauchen **Cube Escape 0.98 „Recast“** mit der Migration
`scout_rifle` → `trace_rifle` (Briefkasten cubeescape-rules#3). **Cube Escape 0.96 und älter lesen das 0.17-Paket nicht** (Ordner und Prefabs
`scout_rifle` fehlen darin); für sie gilt die ältere Fassung: `git checkout v0.16.0 && python3 toolgen/generate_tools.py --tier standard`.

## Ego-Modell und Viewmodel-Kamera

Das Ego-Modell liegt im Kameraraum (`Socket_Camera` ist die Identität, Blick −Y in Blender, +Z in Unity) und ist **nicht
an das Sichtfeld des Spielers gebunden**. Das Spiel zeichnet es mit einer eigenen Kamera:

1. Zweite Kamera für die Viewmodel-Ebene (URP: Overlay-Kamera im Kamerastapel des Spielers, alternativ ein Render-Objects-Pass
   mit Kameraüberschreiben für FOV). Culling nur auf der Viewmodel-Ebene, das Modell mit allen Renderern auf diese Ebene legen.
2. `Camera.fieldOfView = vertical_fov_degrees` (46,69°, Unity rechnet vertikal), `nearClipPlane = near_clip_m` (0,03 m),
   Kameraversatz `camera_offset_m` (0, 0, 0): das Modell trägt den Versatz selbst.
3. Das FOV der Spielwelt (Spielereinstellung) bleibt davon unberührt: weder skaliert es das Viewmodel noch muss das
   Viewmodel nachgeführt werden. Eine Verlängerung des Spieler-FOV ändert nur die Spielwelt.
4. Seitenverhältnis: Das vertikale FOV bleibt fest, das horizontale folgt dem Bildformat (16:9 → 75,0°, 16:10 → 69,3°).
   Bei breiteren Bildschirmen sieht man dasselbe Bild mit mehr Raum an den Seiten, die Hände bleiben im Bild.
5. Wertebereich: Der Bildausschnitt (Hände im Bild, freies Fadenkreuz, Unterarme außerhalb) ist nur beim Datenwert und den
   in `authored_model_validated_vertical_fov_degrees` genannten Werten für das gestaltete Modell geprüft (Bogen nur 46,69°, Taschenlampe 42,69–54,69°); das reduzierte Spielmodell nur bei `vertical_fov_degrees` (`viewmodel_framing` in `qa_game_fps.json`). Soll das Spiel
   eine Viewmodel-FOV-Einstellung anbieten, nur diese Werte zulassen oder den Bildausschnitt neu prüfen.
6. Der Datenwert steht in `data/viewmodels.json` › `camera` und nur dort: Änderungen dort erzeugen neue Pakete mit neuer
   QA (`qa_viewmodel.json`) und neuem `viewmodel_camera.json`; es gibt keinen weiteren fest gebackenen 75°-Wert.

Beispiel (Skizze, nicht im Spiel getestet):

```csharp
// ViewmodelCamera.cs - values come from viewmodel_camera.json of the tool package
[RequireComponent(typeof(Camera))]
public class ViewmodelCamera : MonoBehaviour
{
    public float verticalFov = 46.69f;   // viewmodel_camera.json > vertical_fov_degrees
    public float nearClip = 0.03f;       // near_clip_m
    void OnEnable()
    {
        var cam = GetComponent<Camera>();
        cam.fieldOfView = verticalFov;    // independent of the world camera's FOV setting
        cam.nearClipPlane = nearClip;
        cam.clearFlags = CameraClearFlags.Depth;
    }
}
```

Das Ego-Modell hat keine Kollision (`colliders` im Vertrag ist leer); Treffer, Greifen und Schuss laufen über die Weltseite.
Die Anker (`Socket_Muzzle`, `Socket_Grab`, `Socket_Nock`, `Socket_Hand`, `Socket_SupportHand`) bleiben im Ego-Modell erhalten.

## Weltmodell

Statische Teile bilden einen Renderer; Kollision als Boxen aus `colliders` (Cubegen-Sidecar-Format, Öffnungen bleiben frei).
Die Dreiecksbudgets stehen in `data/game_budget.json` (LOD0, LOD1 etwa 30 % davon); Ändern des Budgets baut die Modelle neu.

## Waffen in der Hand (0.7.0)

Die neun Waffen (Pistole, Sturmgewehr, Impulsgewehr, Schrotflinte, Scharfschützengewehr, Maschinenpistole, Fusionsgewehr, Spurgewehr,
Raketenwerfer; Technik: [TECHNIK](TECHNIK.md) › Waffen 1–9) sind Werkzeuge wie die übrigen: Weltmodell und Ego-Modell, ein Clip
`<Name>_Use`, die Verträge `unity_contract.json`/`unity_contract_fps.json`. Munition, Schaden und Regeln gehören dem Spiel.

**Block `hold`** (nur bei Werkzeugen, die in der Hand liegen): `hand_socket` (`Socket_Hand`, Mitte des Pistolengriffs), `support_socket`
(`Socket_SupportHand`, Mitte des Handschutzes oder Vorderschafts; Pistole: linke Griffseite), `muzzle_socket`, `two_handed`,
`support_grip` (0.10.0: `underhand` Gewehre, `cup` Pistole), `grip_tilt_degrees`,
`grip_axis` (Richtung von der Griffunterkante zur Oberkante, Blender und Unity), `muzzle_axis` (−Y bzw. +Z) und
`grip_to_muzzle_degrees`. So richtet man die Roboterhand aus: die Griffachse der Hand (Handfläche → Fingerspitzen) auf `grip_axis`
legen, die rechte Hand an `Socket_Hand`, die linke an `Socket_SupportHand`, und die Zielrichtung der Figur auf `muzzle_axis`. Das Modell
liegt unrotiert im Wurzelraum: Lauf = −Y (Unity +Z), oben = +Z (Unity +Y), der Lauf steht waagerecht; der Griff lehnt oben nach vorn.
Wer das Werkzeug „verkehrt herum“ oder zu steil sieht, hat die Wurzeldrehung (siehe unten) doppelt oder gar nicht angewendet, nicht den
Haltewinkel geändert. Das Modell ist nicht gespiegelt: Griffhand rechts, Stützhand links. Seit 0.10.0 ist auch die Pistole beidhändig
(`two_handed` true, `support_grip` `cup`, Becher-Griff wie in Destiny): `Socket_SupportHand` liegt an der linken Griffseite unter der rechten
Hand (0,017 | 0,0039 | −0,0155 m, Blender, vorher 0 | −0,05 | 0,034 am Rahmen); die linke Hand ist wie die rechte ausgerichtet (Finger nach
vorn, Handfläche links am Griff) und umfasst deren Finger von links unten, der linke Unterarm kommt von links unten. Mindestversion des
Abnehmers: der CE-Stand mit beidhändiger Pistole; ältere Fassung: `git checkout 384f9e2 -- data/tools.json data/viewmodels.json
scripts/tool_assets/weapon_designs.py` und neu erzeugen (384f9e2 = Toolgen 0.9.0).

**Anker liegen am Werkzeug.** Für die Waffen sind beide Handanker geprüft: `Socket_Hand` und `Socket_SupportHand` liegen im Griff- bzw.
Handschutzteil (`anchors[].surface_distance_m` im Vertrag: negativ = im Teil, QA `grip_sockets_on_tool`, Grenze +4 mm). Der Vertrag meldet
den Wert auch für die älteren Werkzeuge (nur Information): bis 0.7.0 lag `Socket_SupportHand` bei der Portalkanone und beim Magnetgreifer 37 mm außerhalb des
Gehäuses, bei der Taschenlampe 35 mm – eine Hand, die dort griff, schwebte. Seit 0.7.1 liegt `Socket_SupportHand` auch bei diesen drei Werkzeugen am Gehäuse (vorher 35–37 mm daneben; Vertragsänderung,
Modelle aus Toolgen ≥ 0.7.1, siehe CHANGELOG); alle übrigen Anker blieben unverändert.

**Clip und Wurzeldrehung.** Der Use-Clip der Waffen enthält keine Kurve auf der Wurzel (`clips[0].root_curves` ist leer, QA
`clip_root_free`): bewegt werden nur Kind-Knoten (`Anim_Slide`, `Anim_Bolt`, `Anim_Cell`, `Anim_FinL/R`, `Anim_Coil`, `Anim_Hatch`,
`animated_nodes` im Vertrag). Dreht der Einbau die Wurzel des Prefabs um `axes.fbx.export_yaw_degrees` (180°), bleibt der Clip
dadurch unverändert gültig; Positions- oder Rotationskurven auf der Wurzel müssten sonst mitgedreht werden (so musste Cube Escape es
beim Ego-Clip der Portalkanone tun). Der Clip endet in der Ruhepose, läuft einmal und startet nur auf Auslösung (`ce_trigger`: `FireAction`,
beim Fusionsgewehr `ChargeFireAction` mit dem Schuss bei Bild 46).

**Neue Materialien:** `M_GlowVoid` (violett), `M_GlowArc` (blau), `M_GlowKinetic` (kühl weiß), je beim Import aus den Palettenwerten
anlegen; ENERGY und SOLAR benutzen das vorhandene `M_GlowCyan` bzw. `M_GlowOrange`. Das Element steht im Vertrag (`hold.element`) und
als Wurzeleigenschaft `ce_weapon_element`.

## Roboter-Variante in der Hand (0.14.0 Fieldfit, Vertrag 4 additiv)

Für Sturmgewehr, Impulsgewehr, Schrotflinte, Scharfschützengewehr, Maschinenpistole, Fusionsgewehr, Spurgewehr und Raketenwerfer
gibt es ein **zusätzliches Weltmodell für die Roboterhand** (`HeldToolModels`). Es wird mit **`heldScale` 1,0** gehalten; das
bisherige Weltmodell (liegend, Spender, Anzeige), das Ego-Modell und ADS bleiben unverändert. Die Pistole hat keine Variante
(Becher-Griff sitzt bei `heldScale` 1,1). Technik und Maße: [TECHNIK](TECHNIK.md) › Roboter-Variante der Waffen.

**Namen (dauerhafte IDs):** Datenschlüssel `tools.json` › `robot` = `<Asset>_Robot`; Spielmodell `<Asset>_Robot_Game.fbx/.glb/.blend`
mit dem Wurzelknoten `<Asset>_Robot` (Properties `ce_variant` `robot`, `ce_held_scale` `1.0`); Karten `<Asset>_Robot_Game_W0/W1/Fields/
Normal.png` (512², eigenes UV1-Atlas, `surface.uv1.shared_with_world` false); Vertrag `unity_contract_robot.json` (`variant` `robot`);
QA `qa_game_robot.json`, `qa_geometry_robot.json`, `qa_surface_robot.json`. Anker-, Teil- und Clipnamen sind die des Weltmodells
(`Socket_Hand`, `Socket_SupportHand`, `Socket_Muzzle`, `Socket_Sight`, bei Zielfernrohren `Socket_Eye`, `Socket_CenterOfMass`; Clip
`<Name>_Use` mit Marker `Fire`); der Block `hold` ist identisch.

**Block `robot`** im Vertrag: `replaces_in_hand` (das Weltmodell, das die Variante in der Hand ersetzt), `held_scale` 1,0,
`measures_m` (Länge, Schaft hinter und Stützhand vor `Socket_Hand`, Abstand und Höhe der Stützhand, Laufdurchmesser, Gehäusehöhe,
Mündung vor der Hand), `limits_m`, `robot_reference_m` (Roboter aus CE 0.82) und `support_part`. Abweichend vom Satz im `hold`-Block
liegt `Socket_SupportHand` hier nicht am Handschutz, sondern 0,09 m vor `Socket_Hand` am Magazinschacht bzw. an der Gehäusefront
(Raketenwerfer: Rohrunterseite), etwa auf Griffhöhe; der Schaft endet 0,11 m hinter `Socket_Hand`.

**Mindestversion des Abnehmers:** der Cube-Escape-Stand der Equipment-Linie, der `unity_contract_robot.json` liest; ältere Stände
ignorieren die zusätzlichen Dateien. Fassung ohne Variante: `python3 toolgen/generate_tools.py --tier standard --contract 3` (keine
Roboterdateien) oder Toolgen ≤ 0.13 (`v0.13.0`). Dreiecke: `game_budget.json` › `robot` 12 000 je Variante (die vom Nutzer
entschiedene Weltgrenze; CE zieht `FrameBudgetEnvelopeTests` nach).

## Handgelenk im Ego-Modell (0.8.0)

Jede Ego-Hand hat einen leeren Knoten `Wrist_R`/`Wrist_L` (Kind von `Hand_R`/`Hand_L`, `ce_role` `wrist`, in `nodes` des Vertrags,
additiv, Format unverändert). Handgelenkwinkel wie Toolgens `wrist_bend` (`qa_viewmodel.json`): Winkel zwischen Ellbogen
(Ursprung `LowerArm_<Seite>`) → `Wrist_<Seite>` und der Knöchelrichtung = lokal −Y von `Hand_<Seite>`, in Blender wie im importierten Unity-Modell (gemessen in Cube Escape 0.65 mit `bakeAxisConversion`: rechts 43,5–50,3°, links 29,5–30,1°; +Z ergäbe 132–139°).
Grenze 55°, Ziel 45° (Entscheidung des Nutzers, 16.10.2026).

## Ausrüstungs-Slots der Waffen (0.8.0, Vertrag 2)

Die neun Waffen benennen ihre Material-Slots nach der Ausrüstungskonvention von Cube Escape (`Docs/EQUIPMENT.md`,
`Assets/Scripts/Equipment/ColorChannels.cs`): `MT_Primary` (Hauptschale), `MT_Secondary` (Rahmen, Verkleidung), `MT_Accent`
(Akzente, Markierungen), `MT_Metal` (Lauf, Mechanik), `MT_Energy` (Energiezellen, Spulen, Elementleuchten), `MT_Emission`
(Anzeigen, Visier, Statuslichter) und `MT_Detail` (Gummi, Glas, kleine dunkle Teile). Jede Waffe nutzt alle sieben im Welt- und
Ego-Modell (Konzeptwaffen ab 0.18: die Kanäle ihres Blatts, KG02 ohne `MT_Energy`; `equipment.channels` nennt sie); die Roboterhände des Ego-Modells behalten ihre Palettenmaterialien (`M_*`), damit das Bemalen der Waffe sie nicht färbt.

- Vertrag: `format` 2, `material_convention` (`equipment_channels` bei den Waffen, `palette` bei den übrigen Werkzeugen) und Block
  `equipment`: je Kanal `slot`, Standardfarbe (`color_srgb`), `metallic`, `roughness`, `emission`, `material_kind` (Materialart von
  `MaterialKinds`), `untouched_slots` (Hand-Materialien). `materials` listet die Slots mit denselben Standardwerten. `MT_Energy` trägt Farbe
  und Leuchtstärke des Elements der Waffe (`element`, `legacy` = früheres `M_Glow*`).
- Einbau: Slots nach Namen auf Spielmaterialien `MT_<Kanal>` legen (eines je Kanal, für alle Waffen gemeinsam, Farbe per
  `MaterialPropertyBlock`); die Standardwerte aus `equipment.channels` sind das Standarddesign der Waffe.
- **Mindestversion des Abnehmers:** Cube Escape 0.64 (Ausrüstungssystem mit `MT_`-Import, Phase 7). Cube Escape 0.63 liest nur
  `M_*`-Namen (`ToolgenMaterials` verlangt das Präfix `M_`): für ältere Stände den Vertrag 1 erzeugen,
  `python3 toolgen/generate_tools.py --tier standard --contract 1 --output output/_contract1` (Palettennamen wie in 0.7, Geometrie neu,
  Anker und Clips unverändert). `data/game_palette.json` bleibt Format 1; der Abschnitt `channels` ist für 0.63 unsichtbar.

## Ego-Clips (0.9.0, Vertrag 3)

Jedes Ego-Modell bekommt Zustandsclips (Waffen 15, Fusionsgewehr 16, Portalwerfer/Magnetgreifer/Taschenlampe 9 seit 0.15, Bogen 8); Tabelle mit Längen, Loops, Posen, Events und
Übergängen: [EGO_CLIPS.md](EGO_CLIPS.md) (erzeugt aus `data/ego_clips.json`, `python3 scripts/ego_clip_table.py --json <pfad>` liefert
dieselben Daten maschinenlesbar).

- Dateien: `<Asset>_FPS_Game.fbx/.glb` bleiben wie bisher (nur `<Name>_Use`, 97 Frames). Neu `<Asset>_FPS_Game_Clips.fbx/.glb`: dasselbe
  Modell mit derselben Hierarchie und einem Take `<Name>_EgoClips` über alle Ego-Clips (Frames ab 101, drei Frames Abstand).
- Vertrag `unity_contract_fps.json`, `format` 3: `clips[0]` ist weiter der Use-Clip; danach je Ego-Clip ein Eintrag mit `name`
  (`<Name>_<Suffix>`, z. B. `Pistol_AimIn`), `state` (Suffix), `file`, `take`, `take_frame_start`/`take_frame_end` (Frames im Take, 0 = erster Frame),
  `frames` (Samples), `duration_seconds`, `loop`, `autoplay` (immer false), `from`/`to` (= `from_pose`/`to_pose`), `reticle_free`, `interruptible`,
  `events` (Frame und Sekunden ab Clipstart). Block `ego_clips`: Clipnamen als Konstanten (`names`: Suffix → Name), Posen,
  `transitions` (welcher Clip ohne Überblendung folgen darf), Regeln, Import-Hinweis, `reload_part`.
- Import: Clips-Datei wie das Hauptmodell (Generic, `bakeAxisConversion`), Take mit `ModelImporter.clipAnimations` teilen: je Eintrag
  ein Clip, `firstFrame`/`lastFrame` = Startzeit des Takes (`importedTakeInfos`) + `take_frame_start`/`take_frame_end`, `loopTime` = `loop`.
  Die Clips binden über die Knotennamen an das Hauptmodell; sie schreiben keine Wurzelkurve (die 180°-Drehung bleibt unberührt).
- Posen: Jeder Clip beginnt und endet exakt in seiner benannten Pose (`rest` = Frame 1 von Use, `aim`, `sprint`, `lowered`); Schnitt
  ohne Überblendung, wenn `to_pose` = `from_pose` des nächsten. Loops (Idle, Walk, Sprint, AimIdle; letztes Sample = erstes) dürfen an
  jedem Frame mit kurzer Überblendung verlassen werden; `interruptible` false (Draw, Holster) nur am Ende.
- Geprüft je Frame jedes Clips (`qa_viewmodel.json` › `ego_clips`): Handgelenk unter 55° (Ziel 45°), Hände im Bild, proximale
  Unterarme aus dem Bild (auch 1,7× um `Socket_Hand`; Ausnahme: Stützarm in den Ziel-Clips, `support_forearm_visible`), Hand–Socket-Kontakt (außer der Stützhand im Reload-Fenster), Fadenkreuz frei
  bei `reticle_free`, Visierlinie in AimIdle auf der Bildmitte und Visier nicht von Händen verdeckt; Reimport der Clips-Datei
  (`roundtrip_clips_fbx/glb` in `qa_game_fps.json`). Farbe und Material gehen in keinen Clip ein.
- Fire/AimFire: Schuss bei Frame 0, Rückstoß in den ersten ≈ 0,1 s, Länge höchstens die Abklingzeit der Waffe in Cube Escape
  (`fire_cooldown_s`, Werte aus CE `Items/Weapons.cs`: der nächste Schuss startet den Clip neu); das Fusionsgewehr feuert ohne Aufladen.
- **Ego-Werkzeuge (0.15.0):** `clips[0].events` des Use-Clips nennt `Fire` (Portalwerfer, Bild 14), `Grab` (Magnetgreifer, Bild 13, Backen
  geschlossen) bzw. `Switch` (Taschenlampe, Bild 14); neuer letzter Clip `<Name>_Inspect_B` (Frames 389–485, rest → rest, frühere Clips
  behalten ihre Frames); `lowered` (Anfang von Draw, Ende von Holster) liegt deutlich tiefer (`Socket_Hand` 14–17 mm statt ≈ 2 mm). Arme in
  neuer Ruhehaltung (Handgelenk ≤ 55° in jedem Bild), dadurch geänderte Bewegung in allen Clips; Hand- und Werkzeugknoten, Anker und
  Clipnamen bleiben. `viewmodel.authored_model_validated_vertical_fov_degrees` nur noch 46,69 (Taschenlampe 46,69/50,69).
- **Mindestversion des Abnehmers:** keine für den bisherigen Einbau: Cube Escape ab 0.64 liest `clips[0]` und ignoriert die neuen
  Einträge. Die Ego-Clips nutzt erst der Cube-Escape-Stand mit Ego-Zustandslogik (Sitzung „Ego-Waffenhaltung“). Ältere Fassung ohne
  Clips-Datei: `python3 toolgen/generate_tools.py --tier standard --contract 2` (Layout 0.8).

## Maskenkarten und UV1 (0.11.0, Vertrag 4)

Für das Bemalen im Spiel (Cube Escape 0.71 „Maskwork“, Masken-Modus des PAINT-Rezepts, `_EquipParams.x = 1`). Vertrag `format` 4, additiv:
UV0, Anker, Slots, Clips und alle Felder aus Vertrag 3 bleiben gleich.

- **UV1** (`TEXCOORD_1`, FBX-UV-Satz 1, Blender-Name `UV1`) auf allen Renderern, LOD0 und LOD1, auch in der Clips-Datei: je Werkzeugteil vor dem
  Zusammenführen erzeugt (Smart-Projektion 66°, gleiche Texeldichte, gepackt ohne Drehung), ein Atlas je Modell, alle Werte in 0..1,
  LOD0 überlappungsfrei (Raster 2048), Abstand zwischen Inseln ≥ 4 px bei 1024 als UV-Abstand (= 2 px auf der 512²-Weltkarte, 8 px auf der
  2048²-Ego-Karte; gepackt mit 8/1024, `uv1.margin_px_at_map` nennt den Wert der Karte), deterministisch. Die Kollaps-Dezimierung
  (Budget, LOD1) faltet einzelne Dreiecke; Toolgen entfaltet sie danach (`decimation_folds` in `qa_game*.json`).
  Hände und Arme des Ego-Modells (Quellmaterialien `FPS_*`) haben keine Insel: ihre UV1 ist der Punkt (0, 0) in einem freien Rand
  (16 px bei 1024 links und unten), dort sind alle Gewichte 0. Wo die Gewichtssumme 0 ist, behält der Slot seine eigene Farbe
  (bei Portalwerfer, Magnetgreifer, Taschenlampe und Bogen liegen Hand und Werkzeug im selben Mesh und Slot).
- **Gemeinsame UV1:** Hat jedes Werkzeugteil des Ego-Modells im Weltmodell einen Zwilling (Name und Flächenaufbau), übernimmt das Ego-Modell
  dessen UV1 bitgleich (`surface.uv1.shared_with_world` true; die neun Waffen und der Bogen). Portalwerfer, Magnetgreifer und Taschenlampe bauen
  ihr Ego-Werkzeug mit anderen Schrauben, sie haben je ein eigenes Atlas (false). Karten gibt es immer je Modell (eigene Auflösung, eigene Dezimierung).
- **Tangenten:** GLB trägt `TANGENT` auf UV1 (MikkTSpace, w = Händigkeit). FBX trägt keine Tangenten: Unitys FBX-Import liest nur
  UV0-Tangenten (Messung Cube Escape 0.71, alle drei Tangenten-Modi); Cube Escape rechnet sie beim Import aus UV1 (`OnPostprocessModel`).
- **Karten** je Modell (`<Asset>_Game_*.png` Welt 512², `<Asset>_FPS_Game_*.png` Ego **2048²** seit 0.16 – 1024² bis 0.15; gilt auch für die Clips-Datei), PNG 8 Bit RGBA, linear,
  ohne Farbprofil-/Gamma-Chunks, oberste PNG-Zeile = v 1:

  | Karte | R | G | B | A |
  |---|---|---|---|---|
  | `W0` (`_RegionMask0`) | Primary | Secondary | Accent | Emission |
  | `W1` (`_RegionMask1`) | Metal | Detail | Energy | 0 |
  | `Fields` (`_FieldMap`) | AO (1 = offen) | Kante (1 = konvex) | oben = max(0, Normale·oben) | Höhe 0..1 über das LOD0-Modell |
  | `Normal` (`_BumpMap`) | Tangentenraum UV1, OpenGL (Y+), flach 128,128,255 | | | |

  Gewichte one-hot 255 je Dreieck nach dem Kanal seines Slots, auf Nähten hart, jede Insel nach außen fortgesetzt (`maps.dilation_px`: 8 px auf 512²,
  16 px auf 2048² – dieselben 8/1024 des Atlas wie die 1024²-Karten; nächster Texel, feste Reihenfolge bei Gleichstand); außerhalb 0. Import: sRGB aus, `alphaIsTransparency` aus, kein Premultiply (W0.a trägt Emission), `wrapMode` Clamp (der Punkt (0, 0) der Hände soll
  nicht über den Rand filtern).
  Satz je Modell ≤ 2,5 MB bei 512² und ≤ 10 MB bei 2048² (`maps.set_bytes_limit`; gemessen: Welt 0,6–0,8 MB; Ego 1024² (0.13, Pistole) 1,9 MB, Ego 2048² (0.16) 4,5–5,9 MB je Satz). Rauschen/Detail kommt nicht von Toolgen.
- **`channel_map`** (Block `surface`): Slot → Kanal für jeden Slot des Modells. `MT_<Kanal>` folgt aus dem Namen; die Palettennamen aus
  `data/game_palette.json` › `channel_map`: `M_RobotBody_Matte` Primary, `M_RobotDark_Matte` Secondary, `M_HazardOrange_Matte` Accent,
  `M_Metal_Matte` Metal, `M_GlowOrange` Emission, alle übrigen Glühmaterialien Energy (wie die Definitionen in CE `Docs/EQUIPMENT.md`).
- **Block `surface`** in `unity_contract.json` und `unity_contract_fps.json` (`version` 1): `uv1` (Attribut, Auflösung der Randregel 1024, `margin_px` 4,
  `margin_px_at_map`, `islands_rotated` false, `shared_with_world`, Layout-Werte, `unpainted`), `tangents`, `regions`, `channel_map`, `unmapped_slots`, `maps`
  (Dateinamen, Auflösung – **Cube Escape liest die Kartengröße hier, nicht aus dem Dateinamen** –, `dilation_px`, `files` mit sha256, `set_bytes`, `set_bytes_limit`, `applies_to`), `fields` (Bedeutung je Kanal), `bake` (Stufe, Blender, Schlüssel,
  Einstellungen), `minimum_consumer`, `older_consumers`.
- **Stufen:** Karten und Block entstehen in `standard` und `full` (Stufe `surface_bake`, gleiche Dateien in beiden); `quick` lässt sie weg und sagt
  das im `manifest.json` (`"surface": {"included": false, ...}`). UV1 und die GLB-Tangenten gibt es in jeder Stufe.
- **Mindestversion des Abnehmers: Cube Escape 0.71.** Ältere Stände ignorieren UV1 und den Block. **Ego-Karten 2048² (0.16): Cube Escape 0.96 „Pinpoint“** (eingebaut in 0.96, nicht 0.94; cubeescape-rules#3) liest
  `maps.resolution` und streamt die volle Größe nur für das gehaltene Gerät (Mip-Streaming); ältere Stände importieren die PNG mit ihrer Importer-Grenze
  (nicht geprüft). Ältere Fassung mit Ego 1024²: Tag `v0.15.1` (`git checkout v0.15.1 && python3 toolgen/generate_tools.py --tier standard`). Ältere Fassung ohne UV1 und Karten
  (Layout 0.10): `python3 toolgen/generate_tools.py --tier standard --contract 3 --output output/_contract3`.

### Relief, Decals und Block `surface.recipe` (0.13.0, Vertrag 4 additiv)

Für die Equipment-Linie von Cube Escape (Presets ab 0.76). Vertrag `format` 4 bleibt, `surface.version` 1 bleibt; neu sind Inhalte der
Karten und ein Block, den Cube Escape 0.71–0.75 ignoriert.

- **Karten der neun Waffen:** `Normal` trägt Relief je Teil (Griffrändel, Rillen, Lamellen, Panel-Fugen, Bürstung, Korn; höchstens 0,3 mm
  Höhenäquivalent, ändert weder Silhouette noch Kollision). `W0`/`W1` tragen Decals (Symbole, Nummern, Seriennummer S-07, Warnzeichen,
  Pfeile, Tech-Linien): ihr Texel gehört dem Kanal des Decals (meist Accent, leuchtende Symbole Emission bzw. Energy), Summe weiter one-hot
  255. Kein neuer Shaderpfad, kein neuer Import: dieselben vier Karten. `Fields` unverändert; Portalwerfer, Magnetgreifer, Taschenlampe
  und Bogen bytegleich zu 0.12. `surface.bake.settings.schema` 2.
- **Block `surface.recipe`** (nur Waffen, `version` 1), Vorschlag aus dem Konzeptblatt für die Presets – Cube Escape entscheidet:
  `palette` (vier Blattfarben), `glow` (`color`, `element` des Blatts, `model_element` des Modells), `wear` (`level` subtle/medium/strong,
  `amount` 0,2/0,5/0,8 für die Abnutzungsmenge), `channels.<Kanal>` (`material`: painted, painted_matte, ceramic, brushed, satin, polished,
  rough_cast, rubber, energy_glass; `smoothness` ≤ 0,45 als Glätte im Masken-Modus, `note`), `decals` (Anker mit Bild, Kanal, Texelzahl),
  `relief` (was in der Normalkarte steckt, nur zur Information), `computed_by_consumer`, `minimum_consumer`. „Poliert“/„Premium“ ist eine
  Glätte im Masken-Modus; `game_palette.json` › `finish` gilt weiter für den Slot-Weg.
- **0.23 (Livery), additiv – Konzeptwaffen:** `regions` (`source`, `items`: je Aufkleber des Blatts `region` „KG02#i“, `part`, `face`,
  `polygon`, `rect`, `channel`, `part_channel`, `color`, `emissive`, `texels`) und `palettes` (`default` „base“, `items`: `id`, `name`,
  `swatches`, `channels` Primary … Detail → sRGB oder `null`, `other_colors`, `on_sheet`). `decals` bleibt die Liste der Toolgen-Decals
  (bei KG02 leer), `palette` die vier Farben des Texturblatts 1–9; `version` bleibt 1. Die Regions-ID folgt der Reihenfolge der
  Aufkleber im Blatt und ist **nicht dauerhaft** (formgen kann neu ordnen): Regionen über `part`/`face`/`polygon` ansprechen. Die Regionen ändern nur Inhalte von W0/W1
  (dieselben Kanäle, one-hot 255): kein neuer Kanal, keine neue Karte, kein neues Format.
- **Mindestversion:** Karten Cube Escape 0.71 (wie Vertrag 4), Rezept Cube Escape 0.76. Ältere Fassung ohne Relief/Decals: Toolgen 0.12.0
  (`v0.12.0`), ohne Karten `--contract 3`.
- **Test für den Abnehmer:** Karten aus `output/_standard` in die Testkopie importieren, `verify.sh test EditMode Toolgen`; Sichtvergleich
  vorab ohne Unity: `output/_standard/Previews/surface_<Waffe>.png`.

## Visier und Zielen (0.12.0, Vertrag 4 additiv)

Zulieferung für Cube Escape 0.72 „Sightline“ (vormals 0.66 „Deadeye“) (T1, T2, T6; Technik: [TECHNIK](TECHNIK.md) › Visier und Zielen). Nur Ergänzungen:
alle bisherigen Namen, Anker, Clips (auch `<Name>_Use`) und Felder bleiben.

- **Anker:** `Socket_Sight` je Waffe in Welt- und Ego-Modell (`anchors[]` wie `Socket_Muzzle`, im FBX-/GLB-Reimport geprüft): Punkt auf der
  Visierlinie am hinteren Ende des Visiers. **Vertrag ist nur die Position:** die eigene Drehung der Leerobjekte (`Socket_Sight`,
  `Socket_Muzzle`, alle Anker) ist im importierten FBX nicht die Unity-Konvention – die Blender-Achsen bleiben erhalten, die Vorwärtsachse
  zeigt nach unten (Befund Cube Escape 0.75); `unity.localRotation` im Vertrag (identity) beschreibt den Wurzelraum, nicht das importierte
  Leerobjekt. Laufrichtung aus `hold.muzzle_axis` (Unity +Z im Wurzelraum), oben = +Y der Wurzel. Bei Kimme/Korn, Reflex,
  Holo und Energie läuft die Linie über das Gehäuse (Oberkante des Visiers = Zielpunkt, die Bildmitte bleibt frei). Scopes
  (Scharfschützen-, Spurgewehr): offenes Okular mit Linse `ScopeEyeLens` 8 mm innen; `Socket_Eye` in deren Mitte auf derselben Linie,
  `hold.eye_radius_m` ihr Radius im Ego-Modell (Weltmodell: durch `tool_scale` geteilt) – dort die Render-Texture-Linse setzen. Die
  180°-Importdrehung gilt wie für alle Anker genau einmal.
- **`hold`:** neu `sight_socket` (`Socket_Sight`), `sight_kind` (`iron`, `reflex`, `holo`, `scope`, `energy`), `eye_socket` (`Socket_Eye` oder
  null), `eye_radius_m` (Scopes, sonst null), `ads_eye_distance_m` (der Augenabstand, mit dem Toolgen die Zielpose prüft) und `sight_note`.
- **Ereignisse:** `clips[0].events` des Use-Clips enthält `Fire` am Schussbild (= `fire_frame` in `data/viewmodels.json`; Bild 14,
  Fusionsgewehr 46; `seconds` ab Clipstart). Fire/AimFire der Ego-Clips nennen neben `Shot` das gleichbedeutende `Fire` (Bild 0). Achtung Versatz: die Ego-Clips Fire/AimFire beginnen ein Bild vor dem Schussbild des Use-Clips (`fire_frame` − 1, Rückstoßbeginn), ihr `Fire` bei Bild 0 entspricht also Use-Bild 13 (Fusion 45), nicht 14 – wie `Shot` seit 0.9.0.
- **Finger:** `Fingers_R_0` (Abzugfinger; Fire/AimFire) und bei den Gewehren `Fingers_L_0…2` (Nachfassen in Reload) sind animierte Knoten
  (`animated_nodes`, eigene Renderer); im Use-Clip stehen sie in Ruhe.
- **Charge:** `FusionRifle_Charge` (Loop, `state` `Charge`, rest → rest, Ereignis `ChargeCycle` je Schleife) liegt als letzter Clip in der
  Clips-Datei; Ablauf im Spiel: Charge schleifen, solange geladen wird, dann `FusionRifle_Fire` (Schnitt ohne Überblendung, beide in `rest`).
- **Clip-Liste:** Wurzeleigenschaft `ce_action_clips` (JSON-Liste aller Clipnamen); `ce_action_clip` bleibt `<Name>_Use`.
- **Zielpose:** `qa_game_fps.json` › `ads`: Ruhepose starr so verschoben, dass `Socket_Sight` bei `ads_eye_distance_m` auf der
  Kameraachse liegt (`frame_matrix_blender`), Bildausschnitt je 16:9/16:10, `eye_distance_range_m` = Abstände, bei denen drei Greiffinger
  und Daumen beider Hände im Bild und die Griffarm-Unterarmhälfte draußen bleiben.

Gemessen mit Toolgen 0.12.0 (quick, 16.10.2026; Viewmodel-Sichtfeld 46,69°, 16:9 und 16:10, Maßstab 1). Verbindlich und bei allen erfüllt: Bildmitte frei (Scopes: Okularlinse), Modell höchstens 25 % der Bildhöhe über der Mitte (negativ = ganz darunter). Nicht verbindlich, Befund für Cube Escape: die Finger beim Profilabstand. Zu nah heißt: die Waffe füllt das Bild, Finger rutschen unten heraus (Grund in allen Fällen; die Unterarmhälfte des Griffarms bleibt überall draußen). Die Schrotflinte hat nur ein Korn (`FrontBead`) vorn am Lauf, ihr `Socket_Sight` liegt deshalb weit vorn und der Abstand zählt bis dorthin.

| Waffe | `sight_kind` | Profilabstand (m) | Bildmitte | Modell über der Mitte | Finger im Bild beim Profil | Bereich, der hält (m) |
|---|---|---:|---|---:|---|---|
| Pistole | `iron` | 0.30 | frei | -2.6 % | nein | 0.355–0.500 |
| Sturmgewehr | `reflex` | 0.26 | frei | -1.4 % | nein | 0.335–0.515 |
| Impulsgewehr | `holo` | 0.26 | frei | -1.5 % | nein | 0.310–0.495 |
| Schrotflinte | `iron` | 0.28 | frei | -2.4 % | nein | 0.590–0.770 |
| Scharfschützengewehr | `scope` | 0.22 | Okularlinse | 8.1 % | ja | 0.210–0.400 |
| Maschinenpistole | `reflex` | 0.24 | frei | -4.8 % | nein | 0.365–0.535 |
| Fusionsgewehr | `energy` | 0.26 | frei | -2.1 % | nein | 0.345–0.530 |
| Spurgewehr | `scope` | 0.20 | Okularlinse | 8.5 % | nein | 0.215–0.405 |
| Raketenwerfer | `iron` | 0.30 | frei | 4.7 % | nein | 0.390–0.575 |

- **Mindestversion des Abnehmers:** keine über Vertrag 4 hinaus (Cube Escape 0.71) – Cube Escape 0.72 liest `Socket_Sight` live aus dem
  animierten Modell; ohne den Anker nutzt es das Ersatz-Visier (`ads.sight_back_m`, `sight_up_m`, `sight_offset_m`); die neuen Felder und
  Anker sind zusätzlich. `--contract 3` (ohne UV1/Karten), `2` und `1` enthalten die Anker und Felder ebenfalls (Zusatzdaten, die ältere
  Stände nicht lesen).

## Konzeptwaffen (0.18.0 Bedrock, Vertrag 4 additiv)

Das Sturmgewehr (`assault_rifle`) ist ab Toolgen 0.18.0 das Konzeptmodell KG02 „Kantenläufer“ (Variante G) aus cubeescape-formgen
(Technik: [TECHNIK](TECHNIK.md) › Konzeptmodelle). ID, Asset, Clipnamen, Knoten (`Anim_Bolt`, `Anim_Magazine`) und die vier bisherigen
Anker bleiben; neu oder geändert:

- **Teilnamen** wie im Blatt: `SM_PG_<Bezeichnung>_<id>` (z. B. `SM_PG_Griff_p03`, `SM_PG_Handschutz_p11`, `SM_PG_Gehaeuse_p09`,
  `SM_PG_Magazin_p07` unter `Anim_Magazine`, Visierrahmen `SM_PG_Rahmen_p24`). Wer Teile beim Namen sucht, sucht neu.
- **`hold`:** `grip_tilt_degrees` 10,27 (bisher 16), `sight_kind` `holo` (bisher `reflex`), neu `reticle_socket` (`Socket_Reticle`) mit
  `reticle_note`. `ads_eye_distance_m` bleibt 0,379 (Wert von Cube Escape).
- **Visier:** offenes Holo-Fenster ohne Glas (Entscheidung des Nutzers 20.10.2026). Die Visierlinie läuft durch die Fenstermitte, nicht
  über das Gehäuse; `Socket_Sight` liegt am hinteren Fensterrand auf der Linie, **`Socket_Reticle` (neu)** in der Fenstermitte – dort
  zeichnet der Abnehmer Tönung und Absehen. Der Rahmen hat keinen Kollider, das Fenster bleibt frei (Öffnungsprobe im Spiel-Export).
- **`Socket_SupportHand`** liegt 10 cm hinter der Handschutzmitte des Blatts (benannte Korrektur, Ego-Bildregel; Entscheidung des Nutzers).
- **`Anim_Bolt`** trägt den Ladehebel `SM_PG_Ladehebel_p32` (formgen claude-v0.15, +X-Seite des Gehäuses); der Use-Clip schiebt ihn wie
  bisher 50 mm nach hinten (Bild 14–28) und zurück.
- **Kanäle:** KG02 nutzt sechs der sieben Ausrüstungs-Slots; `MT_Energy` fehlt, das Leuchten des Blatts (Emitter) ist `MT_Emission`
  (Orange). `equipment.channels` und die Maskenkarten nennen nur diese sechs; das Element (`arc`) bleibt Wurzeleigenschaft.
- **Block `concept`** (nur Konzeptwaffen): Blatt, Variante, Format, Repository, Release, Commit, Zip- und Datei-sha256, `sight_window`.
- **Aufkleber und Paletten (0.23 Livery, Stufe B):** die 63 Aufkleber des Blatts stecken als Maskenregionen in W0/W1 (Kanal des Blatts:
  56 Secondary, 5 Primary, 2 Accent; die zwei Toolgen-Decals von 0.13–0.20 entfallen), die vier Blattpaletten `base` (Standard),
  `standard`, `arktis`, `nacht` stehen in `surface.recipe.palettes`. Keine Palette belegt `MT_Energy` (bei allen `null`); der Kanal fehlt
  KG02 also weiter, ohne dass Paletten oder Regionen ihn brauchen. Cube Escape 0.106 lädt das Paket unverändert (liest aus dem Block
  `surface` nur Kartennamen und `maps.resolution`); neue Karten heißt neu importieren.
- **Befund für Cube Escape:** beim hohen Holovisier hält der Bildausschnitt der Zielpose erst ab etwa 0,475 m Augenabstand
  (`qa_game_fps.json` › `ads.eye_distance_range_m`); beim Profilabstand 0,379 m fehlen die Finger der Griffhand. Das ist kein Abbruch
  (wie in der Tabelle oben), aber ein Wert für die Übernahme.
- **Dreiecksbudgets (alle Werkzeuge, 0.18):** +25 % (Welt bis 10 000, Ego bis 20 000, Roboter 15 000 LOD0-Dreiecke; Werte in
  `data/game_budget.json`, je Vertrag `budget`). `minimum_consumer.triangle_budgets`: die CE-Version, die `FrameBudgetEnvelopeTests`
  (bisher 16 000 Ego, 8 000 Welt) anhebt – **Cube Escape 0.106 „Knuckleline“** (Gerät 20 000, Welt 10 000; Toolgen 0.23).
- **Mindestversion des Abnehmers:** `minimum_consumer.concept_models` – die Cube-Escape-Version, die das Konzeptmodell zuerst übernimmt
  (CE-A „Refit“, **noch nicht reserviert: „offen“**). Cube Escape ab 0.98 liest das Paket (gleiche IDs, Anker, Clips), ist aber auf das alte
  Modell abgestimmt (Griffneigung, Handpose, Visierart). Das alte Sturmgewehr: `git checkout v0.17.2 && python3 toolgen/generate_tools.py
  --tier standard`.

## Vertrag 5 – gemeinsames Ego-Arm-Rig (0.19.0 Kinetic)

Endgültiger Text zum Entwurf E0 (rules#1, Kommentar 6293153456, freigegeben 6293286116; Entscheidungen 6292820613). Technik und Lehren:
[TECHNIK](TECHNIK.md) › Gemeinsames Ego-Arm-Rig. **Ein** Arm- und Hand-Modell für alle Ego-Geräte; ein Gerät auf Vertrag 5 hat keine Arme
mehr, hängt an `Prop_R` und bewegt sich nur über die rechte Armkette. Vertrag 4 und 5 bestehen nebeneinander: Toolgen wählt je Gerät
(`tools.json` › `game_contract`; in 0.19 nur `assault_rifle` und `portal_emitter`), Cube Escape liest je Ordner nach `format`.

**Rückweg:** `python3 toolgen/generate_tools.py --contract 4` baut die beiden Pilotgeräte wie 0.18 (gebackene Arme, gleiche Anker, Karten
und Clipnamen) und lässt die übrigen Geräte unberührt; Cube Escape 0.104 und älter lesen nur diese Fassung.

**Mindestversion:** jeder Vertrag eines Vertrag-5-Geräts (Welt, Roboter, Ego) und der Armvertrag tragen `minimum_consumer.shared_arm_rig`
= **Cube Escape 0.106 „Knuckleline“** (E2 des Arm-Umbaus; bis Toolgen 0.20 „offen“, nachgetragen in 0.23). Welt- und Robotervertrag ändern sonst nichts (Format 5, Inhalt wie 4).

### Arm-Paket `ego_arms`

| Feld | Inhalt |
|---|---|
| Dateien | `output/<Stufe>/ego_arms/CubeEscape_EgoArms_Game.fbx/.glb/.blend` (Ruhepose, keine Animation), `unity_contract_arms.json`, `qa_arms.json`, `preview_arms.png` (Bildstufen). Ablage in CE: `Assets/Art/ToolgenShared/EgoArms/` (nicht unter `Assets/Art/Toolgen/`) |
| Knoten | Wurzel `CubeEscape_EgoArms` (Kameraraum), `Socket_Camera`; je Seite `Shoulder_<S>` → `UpperArm_<S>` → `LowerArm_<S>` → `WristYoke_<S>` → `Hand_<S>` → `Wrist_<S>`, `GripContact_<S>`, `Prop_<S>`, `Fingers_<S>_<i>` → `Fingers_<S>_<i>_1` → `Fingers_<S>_<i>_2` (i = 0 Abzugfinger, 1, 2), `Thumb_<S>` → `Thumb_<S>_1`. Leerobjekte, kein Armature, kein Skinning |
| Achsen | +Z längs jedes Glieds; `LowerArm_<S>` sitzt fest bei (0, 0, `upper_arm`), `WristYoke_<S>` bei (0, 0, `forearm`), `Hand_<S>` im Joch bei (0, 0, 0) – Clips drehen die Kette und verschieben nur `Shoulder_<S>`. **Kardan-Handgelenk** (rig 2): `WristYoke_<S>` dreht nur um lokal +X (Beugen), `Hand_<S>` nur um lokal +Y (seitlich). `Hand_<S>`: Ursprung = Handgelenk-Drehpunkt, +Z zu den Knöcheln, +Y Handrücken, +X Daumenseite rechts (links gespiegelt). Finger beugen um lokal +X |
| Maße | `lengths_m` (Oberarm 0,448, Unterarm 0,42, `hand_scale` 0,91 = Toolgen 0,65 × 1,4): **Faktor 1,4 eingebacken**, CE nutzt für Vertrag-5-Geräte die Rahmengröße 1,0 und ignoriert `hip.scale` |
| Meshes | je bewegtem Knoten ein Renderer `<Knoten>_Mesh` (28: Unterarm, Joch, Hand, 9 Fingerglieder, 2 Daumenglieder je Seite), LOD0 only, keine Kollision; Handgelenk als Bauteile (`WristServo_<S>` im Unterarm-Mesh, `WristYoke_<S>`/`WristRotor_<S>` im Joch-Mesh, `WristFork_<S>` im Hand-Mesh, `parts` je Renderer) |
| Look | genau vier Slots `M_RobotBody_Matte`/`M_RobotDark_Matte`/`M_Metal_Matte`/`M_HazardOrange_Matte` → `armor`/`mech`/`metal`/`lights` (Block `look`); keine `MT_`-Slots, keine UV1 |
| Budget | 12 000 Dreiecke LOD0 für beide Arme (`data/ego_arms.json` › `rig.budget_triangles`; eigene Datei, damit die Schlüssel und Verträge der Vertrag-4-Geräte gleich bleiben); Gerät + Arme ≤ 32 000 |
| `rig` | `id` `ego_arms` (ewig), `version` 2 (0.19 Mac-Abnahme: Kardan-Handgelenk; Version 1 war nur der unveröffentlichte Cloud-Stand), `hash` = sha256 über Name, Eltern und lokale Ruhe-Transformation aller Knoten (Regel `hash_rule`); Meshes und Farben zählen nicht |
| `finger_poses` | Bibliothek `open`, `grip`, `regrip`, `trigger`, `underhand`, `cup`, `wrap`, `mag_hold`, `pinch` (Namen ewig, nur anhängen; Winkel in Grad je Gelenk, Daumen `[flex, out, tip]`); die Geräte nennen ihre eigenen, am Mesh geschlossenen Winkel |
| `measures` | Handgelenk = Winkel zwischen `LowerArm_<S>` +Z und `Hand_<S>` +Z (Ziel 45°, Grenze 55°) |

### Gerätepaket ohne Arme (`unity_contract_fps.json`, `format` 5)

| Feld / Datei | Vertrag 5 |
|---|---|
| `<Asset>_FPS_Game.*` | **nur das Gerät, ohne Take**: Wurzel `<Asset>_FPS` (Ursprung = `Socket_Hand`, Gerätachsen, unrotiert), Anker, `Anim_*`, Renderer wie Vertrag 4 (Palette/`MT_`, UV1, LOD0/LOD1, Budget `data/game_budget.json` › `viewmodel` jetzt für das Gerät allein); zweite Wurzel **`<Asset>_FPS_HandL`** mit den Teilen der linken Hand (Sturmgewehr: `HandMag_L`, Kopie des Magazins) |
| `<Asset>_FPS_Game_Clips.*` | **die Zusammensetzung als Knoten ohne Meshes**: `CubeEscape_EgoArms` mit `<Asset>_FPS` unter `Prop_R` und `<Asset>_FPS_HandL` unter `Prop_L`; ein Take `<Stamm>_EgoClips`, `<Stamm>_Use` zuerst (Take-Bild 0–96), danach alle Ego-Clips |
| `attach` | Lage der Gerätewurzel in `Prop_R` (`blender`, `unity`); in jedem Clip konstant, die Clips-Datei trägt dieselbe Transformation (Prüfwert ≤ 0,1 mm / 0,05°). `attach_left`: Wurzel der Handteile in `Prop_L` (Identität) |
| `grip` | `R`/`L`: Lage von `Hand_<S>` im Geräteraum (Position und Drehung = Ausrichtung der Handfläche), `mode` (`grip`, `support`; später `free`, `hidden`), `pose`, Toleranzen 8 mm / 5°. Portalkanone: `hold`-frei, Stützhand `wrap` (umgreift das Gehäuse) |
| `arms_rig` | `id`, `version`, `hash` des Arm-Pakets, mit dem die Clips gebaut sind – CE bricht beim Import mit deutscher Meldung ab, wenn der Hash nicht zum Armvertrag passt |
| `assembly` | alle Knotenpfade der Zusammensetzung (Pfad relativ zu `CubeEscape_EgoArms`, Name, Eltern): Unity Generic bindet die Clips über diese Pfade |
| `finger_poses` | die Stellungen des Geräts (rechts z. B. `trigger`, links `underhand`/`wrap`, `mag_hold`, `pinch`) als Gelenkwinkel |
| `support_ik` | `blend_frames` 3: die Stützhand-IK blendet ab `HandOff` auf 0 und ab `HandOn` auf 1; Ziel `Hand_L` = Gerätewurzel × `grip.L` |
| `visibility_nodes` | `Anim_Magazine`, `HandMag_L`: Sichtbarkeit über Skalierung 1 / 0,001, Schritt genau am `MagOut`-Bild (Magazin in die Hand) und am `MagIn`-Bild (zurück); gleiche Weltlage ± 2 mm. FBX- und glTF-Export tasten jedes Bild ab und interpolieren linear: zwischen dem Bild davor und dem Schrittbild skaliert Unity über eine Bilddauer (≈ 42 ms); wer exakt schalten will, setzt die Kurven beim Import auf konstant (`AnimationUtility.SetKeyBroken`/`TangentMode.Constant`) |
| `frame_size` | 1,0 (Faktor eingebacken) |
| `device_scale` | `factor` = Skalierung des Modells aus dem fps-Schritt (`tool_scale` × 1,4, wie `tool_scale` in Vertrag 4); `surface_bake` legt die Decals danach. `world_factor` = Gerät gegen sein Weltmodell (`factor` × `fps_enlargement`, der eigenen Vergrößerung des fps-Schritts: Portalkanone 1,5 → 0,75; Sturmgewehr 1,0 → 1,008) |
| `hand_parts` | Knoten unter `<Asset>_FPS_HandL` (lokale Lagen, Sichtbarkeitsknoten); in der Gerätedatei steht `HandMag_L` bei Skalierung 0,001 (Bild 0) |

**Halbdrehung genau einmal:** CE dreht die Wurzel der **zusammengesetzten** Hierarchie (Arme + Gerät) einmal um 180° um Y, wie jede
Prefab-Wurzel; die Gerätewurzel unter `Prop_R` bekommt keine eigene Drehung. Toolgen prüft die **Selbstkonsistenz der Vertragswerte**
(`qa_game_fps.json` › `anchor_half_turn`): `Prop_R` (Ruhe) × `attach` × Ankerkette (Unity-Werte des Vertrags) ergibt die Unity-Lage des Ankers
in der Zusammensetzung (Fehler < 0,001 mm) – Arm-Rig und Gerät teilen eine Umrechnung; eine zweite Drehung an der Gerätewurzel würde die Anker
um 0,56 m (Portalkanone) bzw. 1,25 m (Sturmgewehr) verschieben. Das ist **keine Messung** von Unitys FBX-Import: die misst CE in E2 (Anker-Test
im Builder).

### Clips und Ereignisse

- Alle Clips bewegen die ganze Kette Bild für Bild (Zwei-Glied-Lösung beim Bau, Unterarm rollt mit der Hand, das Handgelenk dreht als
  Kardan: Joch beugt, Hand neigt seitlich), kleiner Servo-Nachlauf des Unterarms (Richtung zu 30 % zwei Bilder zurück), Finger mit Greifstellungen. Nie bewegt:
  Rig-Wurzel, `Prop_*`, Gerätewurzel, Materialien. Zustandsclips (Idle, Walk, Sprint, AimIdle) sind Schleifen, sonst einmal; nichts startet
  von selbst. 24 Bilder/s; Ruhe = Bild 0 von `<Stamm>_Use` für alle Knoten.
- Ereignisse tragen **`channel`**: `action` (Standard, `EquipmentActionEvent`) oder `rig` (`HandOff`, `HandOn`; nur die Stützhand-IK).
- **`Reload`** (40 Bilder): `Start` 0 · `HandOff` 2 · `MagOut` 8 · `MagIn` 22 · `HandOn` 29 · `Ready` 32 · `End` 40.
  **`ReloadEmpty`** (neu, ans Ende der Clipliste, 46 Bilder): `Start` 0 · `HandOff` 2 · `MagOut` 8 · `MagIn` 22 · `Chamber` 27 (Ladehebel
  ganz hinten) · `HandOn` 34 · `Ready` 38 · `End` 46. CE wählt nach dem Magazinstand aus 0.103; Munition und Bereitschaft kommen aus dem
  Aktionsvertrag an den Markern, nie aus der Cliplänge.
- Ablauf wie Destiny (Form; Zeiten sind CE-Gestaltung nach dem benannten Beispiel Chroma Rush, cubeescape-reference `docs/destiny2.md`
  `#z-chroma-rush`: heraus +0,25 s, ein +0,93 s, Ladegriff +1,05 s, Hüfte +1,58 s): rechte Hand bleibt am Griff, die Waffe kippt (Oberseite
  nach rechts, Mündung hoch – Entscheidung des Nutzers 20.10.2026, der Entwurf nannte links), die linke Hand greift das Magazin, zieht es nach unten aus dem Bild, kommt mit ihm zurück, setzt ein
  (kurzer Stoß), bei `ReloadEmpty` zum Ladehebel (`pinch`) und zieht ihn mit `Anim_Bolt` 5 cm zurück, dann zurück an den Handschutz.
- Portalkanone: die linke Hand umgreift das Gehäuse in allen Clips (kein `HandOff`/`HandOn`).

### Prüfungen in Toolgen (quick, `qa_viewmodel.json`, `qa_game_fps.json`, `qa_arms.json`)

Reimport FBX/GLB des Arm-Pakets (Namen, Eltern, Ruhe-Matrizen, Slots, Dreiecke), der Zusammensetzung und beider Spieldateien; Gerät ohne
Arm-Knoten, `Socket_Hand` im Ursprung; Handkontakt ≤ 8 mm rechts in jedem Bild, links außerhalb `[HandOff + 3, HandOn]`; Handgelenk ≤ 55°;
Bildausschnitt 16:9 und 16:10 beim festen FOV (drei Greiffinger + Daumen jeder haltenden Hand im Bild außer in Ziehen/Wegstecken/Sprint,
proximale Unterarmhälfte und Ellbogen nie, Fadenkreuz frei in den freien Clips); Ereignisse vollständig und geordnet, genau ein `Ready`;
Magazintausch an derselben Stelle; Fingerposen ohne Berührung nicht benachbarter Teile – in der Bibliothek und in jedem abgetasteten Bild
(`hand_self_contacts`); **kein Eindringen** der Hand ins Gerät dieses Bilds (`penetration`: bewegte Teile, ausgeblendete Teile weg,
`HandMag_L` dabei); seitliche Handgelenkneigung gemessen (`wrist_side_max_degrees`, ohne Grenze). Der Arm-Reimport prüft Eltern und Lage
auch der 26 Renderer. Mac-Abnahme: `docs/versions/0.19.md` › Mac-Abnahme.

## Prüfen

Unity-seitig sind offen: Materialzuordnung, LODGroup-Schwellen, Layer/Culling der Viewmodel-Kamera, Z-Fighting mit der Weltkamera
(Overlay-Kamera hat eigenen Tiefenpuffer), Licht auf dem Viewmodel, Greif- und Schussereignisse.
