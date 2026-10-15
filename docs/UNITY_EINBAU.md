# Einbau in Cube Escape (Unity 6, URP) – Vorbereitung

Stand 0.6.0 Sightline. Der Einbau ist **noch nicht abgenommen**; dieses Dokument legt fest, was das Spiel aus den Paketen
liest, damit der spätere Einbau keine Annahmen über Toolgen treffen muss. Das Spielprojekt wird aus diesem Repo nicht
verändert; Toolgen-Dateien und Werte stehen in [TECHNIK](TECHNIK.md) › Spiel-Export.

## Dateien je Werkzeug

| Zweck | Datei | Vertrag |
|---|---|---|
| Weltmodell (liegt, wird geworfen, Anzeige) | `<Asset>_Game.fbx/.glb/.blend` | `unity_contract.json` (Renderer, LOD, Kollision, Clip) |
| Ego-Modell (Hände, Arme, Werkzeug) | `<Asset>_FPS_Game.fbx/.glb/.blend` | `unity_contract_fps.json` (Renderer, LOD, Clip, `viewmodel`) |
| Viewmodel-Kamera | `viewmodel_camera.json` | vertikales FOV, Near Clip, geprüfte Werte |

Materialien: nur die Palettenmaterialien aus `data/game_palette.json` (je Weltmodell höchstens 6, je Ego-Modell höchstens 7).
Cube Escape legt beim Einbau die matten Varianten (`M_RobotBody_Matte`, `M_RobotDark_Matte`, `M_Metal_Matte`,
`M_HazardOrange_Matte`) und `M_GlowWarm` aus den Palettenwerten an; `M_GlowCyan`/`M_GlowOrange` gibt es im Spiel schon.
Die FBX-/GLB-Materialien tragen nur Namen und Palettenwerte; im Spiel werden sie auf die Spielmaterialien gelegt.

FBX-Import: `bakeAxisConversion` einschalten (siehe `axes.fbx.unity_import` im Vertrag), LODGroup entsteht aus `_LOD0`/`_LOD1`.

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
   in `validated_vertical_fov_degrees` genannten Werten geprüft (Bogen nur 46,69°, Taschenlampe 42,69–54,69°). Soll das Spiel
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

## Prüfen

Unity-seitig sind offen: Materialzuordnung, LODGroup-Schwellen, Layer/Culling der Viewmodel-Kamera, Z-Fighting mit der Weltkamera
(Overlay-Kamera hat eigenen Tiefenpuffer), Licht auf dem Viewmodel, Greif- und Schussereignisse.
