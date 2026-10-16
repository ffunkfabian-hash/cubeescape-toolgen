# Einbau in Cube Escape (Unity 6, URP) – Vorbereitung

Stand 0.8.0 Gunmetal. Der Einbau ist **noch nicht abgenommen**; dieses Dokument legt fest, was das Spiel aus den Paketen
liest, damit der spätere Einbau keine Annahmen über Toolgen treffen muss. Das Spielprojekt wird aus diesem Repo nicht
verändert; Toolgen-Dateien und Werte stehen in [TECHNIK](TECHNIK.md) › Spiel-Export.

## Dateien je Werkzeug

| Zweck | Datei | Vertrag |
|---|---|---|
| Weltmodell (liegt, wird geworfen, Anzeige) | `<Asset>_Game.fbx/.glb/.blend` | `unity_contract.json` (Renderer, LOD, Kollision, Clip) |
| Ego-Modell (Hände, Arme, Werkzeug) | `<Asset>_FPS_Game.fbx/.glb/.blend` | `unity_contract_fps.json` (Renderer, LOD, Clip, `viewmodel`) |
| Viewmodel-Kamera | `viewmodel_camera.json` | vertikales FOV, Near Clip, geprüfte Werte |

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
(`Socket_SupportHand`, Mitte des Handschutzes oder Vorderschafts), `muzzle_socket`, `two_handed`, `grip_tilt_degrees`,
`grip_axis` (Richtung von der Griffunterkante zur Oberkante, Blender und Unity), `muzzle_axis` (−Y bzw. +Z) und
`grip_to_muzzle_degrees`. So richtet man die Roboterhand aus: die Griffachse der Hand (Handfläche → Fingerspitzen) auf `grip_axis`
legen, die rechte Hand an `Socket_Hand`, die linke an `Socket_SupportHand`, und die Zielrichtung der Figur auf `muzzle_axis`. Das Modell
liegt unrotiert im Wurzelraum: Lauf = −Y (Unity +Z), oben = +Z (Unity +Y), der Lauf steht waagerecht; der Griff lehnt oben nach vorn.
Wer das Werkzeug „verkehrt herum“ oder zu steil sieht, hat die Wurzeldrehung (siehe unten) doppelt oder gar nicht angewendet, nicht den
Haltewinkel geändert. Das Modell ist nicht gespiegelt: Griffhand rechts, Stützhand links. Einhändig (Pistole, `two_handed` false)
trägt `Socket_SupportHand` den Rahmen für einen optionalen zweiten Griff.

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
Ego-Modell; die Roboterhände des Ego-Modells behalten ihre Palettenmaterialien (`M_*`), damit das Bemalen der Waffe sie nicht färbt.

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

## Prüfen

Unity-seitig sind offen: Materialzuordnung, LODGroup-Schwellen, Layer/Culling der Viewmodel-Kamera, Z-Fighting mit der Weltkamera
(Overlay-Kamera hat eigenen Tiefenpuffer), Licht auf dem Viewmodel, Greif- und Schussereignisse.
