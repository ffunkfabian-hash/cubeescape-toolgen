# Ego-Clips für Cube Escape

Diese Tabelle ist die Referenz für Cube Escapes Ego-Zustandslogik. Quelle sind `data/ego_clips.json`,
`data/tools.json` und `data/viewmodels.json`; Clipauflösung und Übergänge stammen aus
`scripts/tool_assets/ego_clips.py`. Der Einzelclip liegt in `<Asset>_FPS_Game.fbx` als `<Name>_Use`;
die Ego-Clips liegen in `<Asset>_FPS_Game_Clips.fbx` in einem Take `<Name>_EgoClips`, abgegrenzt über Frames.
Die Abtastrate beträgt 24 fps. `length` zählt Frame-Intervalle, also hat ein Clip `length + 1` Samples.
Bei Loop-Clips ist das letzte Sample identisch mit dem ersten.

## Posen und Übergänge

- **rest**: Hüftpose, identisch mit Frame 1 des Use-Clips
- **aim**: Visierpose: Visierlinie auf Bildschirmmitte, Lauf parallel zur Blickrichtung
- **sprint**: abgesenkte, nach innen geneigte Waffe; Hände bleiben im Bild
- **lowered**: Anfang von Draw / Ende von Holster: abgesenkt und geneigt, weiterhin im Bild

Übergänge sind Schnitte ohne Überblendung, wenn `to` des vorherigen Clips dem `from` des nächsten entspricht.
Loops dürfen an jedem Frame mit kurzer Überblendung verlassen werden. Bei `interruptible: false` ist ein Clip nur am Ende verlassbar.
Events sind relativ zum Clipstart angegeben.
In den Ziel-Clips (AimIn, AimIdle, AimFire, AimOut) darf der Unterarm der Stützhand sichtbar sein (`support_forearm_visible`, Entscheidung des Nutzers 16.10.2026); sonst bleiben die Ellbogenhälften der Unterarme außerhalb des Bildes.
Vertrag 5 (0.19, Sturmgewehr und Portalkanone, `data/ego_arms.json`): alle Clips, der Use-Clip zuerst, liegen in `<Asset>_FPS_Game_Clips.fbx` und bewegen die gemeinsame Armkette; das Sturmgewehr hat eigene `Reload`/`ReloadEmpty` (Start/End und die Rig-Ereignisse `HandOff`/`HandOn`, Kanal „rig“, markiert mit ⟂). Einbau: docs/UNITY_EINBAU.md › Vertrag 5.
Gruppe 1 der Animationsvorgabe (0.24, Vertrag 5): MP, Impuls- und Scout-Gewehr mit eigenem Nachladen (`Move` = erste Bewegung, `Ready` = Freigabe, `Still` = ruhig), am Ende angehängt MP `AutoFire`/`AimAutoFire` (Zustandsschleife, ein `Shot` je echtem Schuss), Impuls `Burst`/`AimBurst` (drei `Shot`, `BurstEnd`), Scout `ReloadEmpty` und die Zielfernrohr-Marker `ScopeOn`/`ScopeOff`. Einbau: docs/UNITY_EINBAU.md › Gruppe 1.

## Clips je Klasse

Längen sind Frame-Intervalle; `—` bedeutet, dass die Klasse den Clip nicht besitzt.

| Suffix | Pistole | Maschinenpistole | Sturmgewehr | Spurgewehr | Impulsgewehr | Schrotflinte | Fusionsgewehr | Scharfschützengewehr | Raketenwerfer | Scout-Gewehr | Werkzeuge (Portalkanone / Magnetgreifer / Taschenlampe / Bogen) | Loop | Von → nach | Fadenkreuz frei | Unterbrechbar | Events (Frames je Werkzeug unten) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Use | 97 | 97 | 97 | 97 | 97 | 97 | 97 | 97 | 97 | 97 | 97 | Nein | rest → rest | Ja | Ja | Fire, Grab, Switch; Bogen: eigene Marker |
| Idle | 72 | 72 | 72 | 72 | 72 | 72 | 72 | 72 | 72 | 72 | 72 / 72 / 72 / 72 | Ja | rest → rest | Ja | Ja | — |
| Walk | 32 | 32 | 32 | 32 | 32 | 32 | 32 | 32 | 32 | 32 | 32 / 32 / 32 / 32 | Ja | rest → rest | Ja | Ja | FootL, FootR |
| SprintIn | 8 | 7 | 8 | 8 | 8 | 10 | 10 | 11 | 12 | 8 | 8 / 8 / 8 / 8 | Nein | rest → sprint | Ja | Ja | — |
| Sprint | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 20 / 20 / 20 / 20 | Ja | sprint → sprint | Ja | Ja | FootL, FootR |
| SprintOut | 8 | 7 | 8 | 8 | 8 | 10 | 10 | 11 | 12 | 8 | 8 / 8 / 8 / 8 | Nein | sprint → rest | Ja | Ja | Ready |
| Fire | 8 | 7 | 9 | 19 | 14 | 28 | 36 | 36 | 48 | 8 | — / — / — / — | Nein | rest → rest | Ja | Ja | Start, Shot, Fire, Move, Ready, Still, End |
| AimIn | 8 | 7 | 8 | 9 | 8 | 9 | 9 | 12 | 12 | 9 | — / — / — / — | Nein | rest → aim | Nein | Ja | Aimed |
| AimIdle | 72 | 72 | 72 | 72 | 72 | 72 | 72 | 72 | 72 | 72 | — / — / — / — | Ja | aim → aim | Nein | Ja | — |
| AimFire | 8 | 7 | 9 | 19 | 14 | 28 | 36 | 36 | 48 | 8 | — / — / — / — | Nein | aim → aim | Nein | Ja | Start, Shot, Fire, Move, Ready, Still, End |
| AimOut | 8 | 7 | 8 | 9 | 8 | 9 | 9 | 12 | 12 | 9 | — / — / — / — | Nein | aim → rest | Nein | Ja | — |
| Draw | 9 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 / 12 / 12 / 12 | Nein | lowered → rest | Ja | Nein | Ready |
| Holster | 7 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 | 8 / 8 / 8 / 8 | Nein | rest → lowered | Ja | Nein | Holstered |
| Inspect_A | 96 | 96 | 96 | 96 | 96 | 96 | 96 | 96 | 96 | 96 | 96 / 96 / 96 / 96 | Nein | rest → rest | Nein | Ja | — |
| Inspect_B | 96 | 96 | 96 | 96 | 96 | 96 | 96 | 96 | 96 | 96 | 96 / 96 / 96 / — | Nein | rest → rest | Nein | Ja | Start, Move, HandOff, PressCheck, HandOn, Still, End |
| Reload | 32 | 40 | 40 | 56 | 42 | 64 | 60 | 64 | 78 | 44 | — / — / — / — | Nein | rest → rest | Nein | Ja | Start, Move, HandOff, MagOut, MagIn, HandOn, Ready, Still, End |
| ReloadEmpty | 43 | — | 46 | — | — | — | — | — | — | 52 | — / — / — / — | Nein | rest → rest | Nein | Ja | Start, Move, HandOff, MagOut, MagIn, Chamber, HandOn, Ready, Still, End |
| FireLast | 8 | — | — | — | — | — | — | — | — | — | — / — / — / — | Nein | rest → rest | Ja | Ja | Start, Shot, Fire, Move, SlideLock, Ready, Still, End |
| AimFireLast | 8 | — | — | — | — | — | — | — | — | — | — / — / — / — | Nein | aim → aim | Nein | Ja | Start, Shot, Fire, Move, SlideLock, Ready, Still, End |
| SlideLocked | 24 | — | — | — | — | — | — | — | — | — | — / — / — / — | Ja | rest → rest | Ja | Ja | — |
| AutoFire | — | 12 | — | — | — | — | — | — | — | — | — / — / — / — | Ja | rest → rest | Ja | Ja | Shot, Shot, Shot, Shot, Shot, Shot |
| AimAutoFire | — | 12 | — | — | — | — | — | — | — | — | — / — / — / — | Ja | aim → aim | Nein | Ja | Shot, Shot, Shot, Shot, Shot, Shot |
| Burst | — | — | — | — | 14 | — | — | — | — | — | — / — / — / — | Nein | rest → rest | Ja | Ja | Start, Shot, Shot, Shot, Move, BurstEnd, Ready, Still, End |
| AimBurst | — | — | — | — | 14 | — | — | — | — | — | — / — / — / — | Nein | aim → aim | Nein | Ja | Start, Shot, Shot, Shot, Move, BurstEnd, Ready, Still, End |
| Charge | — | — | — | — | — | — | 18 | — | — | — | — / — / — / — | Ja | rest → rest | Ja | Ja | ChargeCycle |

## Clips je Werkzeug und Waffe

### Pistole (`pistol`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `Pistol_Use` | 1–97 | 4.00 | Fire 13 |
| `Pistol_Idle` | 101–173 | 3.00 | — |
| `Pistol_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `Pistol_SprintIn` | 213–221 | 0.33 | — |
| `Pistol_Sprint` | 225–245 | 0.83 | FootL 0, FootR 10 |
| `Pistol_SprintOut` | 249–257 | 0.33 | Ready 8 |
| `Pistol_Fire` | 261–269 | 0.33 | Start 0, Shot 0, Fire 0, Move 1, Ready 4, Still 7, End 8 |
| `Pistol_AimIn` | 273–281 | 0.33 | Aimed 8 |
| `Pistol_AimIdle` | 285–357 | 3.00 | — |
| `Pistol_AimFire` | 361–369 | 0.33 | Start 0, Shot 0, Fire 0, Move 1, Ready 4, Still 7, End 8 |
| `Pistol_AimOut` | 373–381 | 0.33 | — |
| `Pistol_Draw` | 385–394 | 0.38 | Ready 9 |
| `Pistol_Holster` | 398–405 | 0.29 | Holstered 7 |
| `Pistol_Inspect_A` | 409–505 | 4.00 | — |
| `Pistol_Inspect_B` | 509–605 | 4.00 | Start 0, Move 1, HandOff⟂ 30, PressCheck 44, HandOn⟂ 60, Still 90, End 96 |
| `Pistol_Reload` | 609–641 | 1.33 | Start 0, Move 1, HandOff⟂ 2, MagOut 8, MagIn 17, HandOn⟂ 22, Ready 26, Still 29, End 32 |
| `Pistol_ReloadEmpty` | 645–688 | 1.79 | Start 0, Move 1, HandOff⟂ 2, MagOut 8, MagIn 17, Chamber 26, HandOn⟂ 32, Ready 36, Still 40, End 43 |
| `Pistol_FireLast` | 692–700 | 0.33 | Start 0, Shot 0, Fire 0, Move 1, SlideLock 2, Ready 4, Still 7, End 8 |
| `Pistol_AimFireLast` | 704–712 | 0.33 | Start 0, Shot 0, Fire 0, Move 1, SlideLock 2, Ready 4, Still 7, End 8 |
| `Pistol_SlideLocked` | 716–740 | 1.00 | — |

### Maschinenpistole (`smg`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `SubmachineGun_Use` | 1–97 | 4.00 | Fire 13 |
| `SubmachineGun_Idle` | 101–173 | 3.00 | — |
| `SubmachineGun_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `SubmachineGun_SprintIn` | 213–220 | 0.29 | — |
| `SubmachineGun_Sprint` | 224–244 | 0.83 | FootL 0, FootR 10 |
| `SubmachineGun_SprintOut` | 248–255 | 0.29 | Ready 7 |
| `SubmachineGun_Fire` | 259–266 | 0.29 | Shot 0, Fire 0 |
| `SubmachineGun_AimIn` | 270–277 | 0.29 | Aimed 7 |
| `SubmachineGun_AimIdle` | 281–353 | 3.00 | — |
| `SubmachineGun_AimFire` | 357–364 | 0.29 | Shot 0, Fire 0 |
| `SubmachineGun_AimOut` | 368–375 | 0.29 | — |
| `SubmachineGun_Draw` | 379–391 | 0.50 | Ready 12 |
| `SubmachineGun_Holster` | 395–403 | 0.33 | Holstered 8 |
| `SubmachineGun_Inspect_A` | 407–503 | 4.00 | — |
| `SubmachineGun_Inspect_B` | 507–603 | 4.00 | — |
| `SubmachineGun_Reload` | 607–647 | 1.67 | Start 0, Move 1, HandOff⟂ 2, MagOut 8, MagIn 22, HandOn⟂ 28, Ready 32, Still 37, End 40 |
| `SubmachineGun_AutoFire` | 651–663 | 0.50 | Shot 0, Shot 2, Shot 4, Shot 6, Shot 8, Shot 10 |
| `SubmachineGun_AimAutoFire` | 667–679 | 0.50 | Shot 0, Shot 2, Shot 4, Shot 6, Shot 8, Shot 10 |

### Sturmgewehr (`assault_rifle`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `AssaultRifle_Use` | 1–97 | 4.00 | Fire 13 |
| `AssaultRifle_Idle` | 101–173 | 3.00 | — |
| `AssaultRifle_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `AssaultRifle_SprintIn` | 213–221 | 0.33 | — |
| `AssaultRifle_Sprint` | 225–245 | 0.83 | FootL 0, FootR 10 |
| `AssaultRifle_SprintOut` | 249–257 | 0.33 | Ready 8 |
| `AssaultRifle_Fire` | 261–270 | 0.38 | Shot 0, Fire 0 |
| `AssaultRifle_AimIn` | 274–282 | 0.33 | Aimed 8 |
| `AssaultRifle_AimIdle` | 286–358 | 3.00 | — |
| `AssaultRifle_AimFire` | 362–371 | 0.38 | Shot 0, Fire 0 |
| `AssaultRifle_AimOut` | 375–383 | 0.33 | — |
| `AssaultRifle_Draw` | 387–399 | 0.50 | Ready 12 |
| `AssaultRifle_Holster` | 403–411 | 0.33 | Holstered 8 |
| `AssaultRifle_Inspect_A` | 415–511 | 4.00 | — |
| `AssaultRifle_Inspect_B` | 515–611 | 4.00 | — |
| `AssaultRifle_Reload` | 615–655 | 1.67 | Start 0, HandOff⟂ 2, MagOut 8, MagIn 22, HandOn⟂ 29, Ready 32, End 40 |
| `AssaultRifle_ReloadEmpty` | 659–705 | 1.92 | Start 0, HandOff⟂ 2, MagOut 8, MagIn 22, Chamber 27, HandOn⟂ 34, Ready 38, End 46 |

### Spurgewehr (`trace_rifle`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `TraceRifle_Use` | 1–97 | 4.00 | Fire 13 |
| `TraceRifle_Idle` | 101–173 | 3.00 | — |
| `TraceRifle_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `TraceRifle_SprintIn` | 213–221 | 0.33 | — |
| `TraceRifle_Sprint` | 225–245 | 0.83 | FootL 0, FootR 10 |
| `TraceRifle_SprintOut` | 249–257 | 0.33 | Ready 8 |
| `TraceRifle_Fire` | 261–280 | 0.79 | Shot 0, Fire 0 |
| `TraceRifle_AimIn` | 284–293 | 0.38 | Aimed 9 |
| `TraceRifle_AimIdle` | 297–369 | 3.00 | — |
| `TraceRifle_AimFire` | 373–392 | 0.79 | Shot 0, Fire 0 |
| `TraceRifle_AimOut` | 396–405 | 0.38 | — |
| `TraceRifle_Draw` | 409–421 | 0.50 | Ready 12 |
| `TraceRifle_Holster` | 425–433 | 0.33 | Holstered 8 |
| `TraceRifle_Inspect_A` | 437–533 | 4.00 | — |
| `TraceRifle_Inspect_B` | 537–633 | 4.00 | — |
| `TraceRifle_Reload` | 637–693 | 2.33 | MagOut 18, MagIn 38, Ready 56 |

### Impulsgewehr (`pulse_rifle`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `PulseRifle_Use` | 1–97 | 4.00 | Fire 13 |
| `PulseRifle_Idle` | 101–173 | 3.00 | — |
| `PulseRifle_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `PulseRifle_SprintIn` | 213–221 | 0.33 | — |
| `PulseRifle_Sprint` | 225–245 | 0.83 | FootL 0, FootR 10 |
| `PulseRifle_SprintOut` | 249–257 | 0.33 | Ready 8 |
| `PulseRifle_Fire` | 261–275 | 0.58 | Shot 0, Fire 0 |
| `PulseRifle_AimIn` | 279–287 | 0.33 | Aimed 8 |
| `PulseRifle_AimIdle` | 291–363 | 3.00 | — |
| `PulseRifle_AimFire` | 367–381 | 0.58 | Shot 0, Fire 0 |
| `PulseRifle_AimOut` | 385–393 | 0.33 | — |
| `PulseRifle_Draw` | 397–409 | 0.50 | Ready 12 |
| `PulseRifle_Holster` | 413–421 | 0.33 | Holstered 8 |
| `PulseRifle_Inspect_A` | 425–521 | 4.00 | — |
| `PulseRifle_Inspect_B` | 525–621 | 4.00 | — |
| `PulseRifle_Reload` | 625–667 | 1.75 | Start 0, Move 1, HandOff⟂ 2, MagOut 11, MagIn 28, HandOn⟂ 34, Ready 38, Still 40, End 42 |
| `PulseRifle_Burst` | 671–685 | 0.58 | Start 0, Shot 0, Shot 2, Shot 4, Move 1, BurstEnd 4, Ready 10, Still 12, End 14 |
| `PulseRifle_AimBurst` | 689–703 | 0.58 | Start 0, Shot 0, Shot 2, Shot 4, Move 1, BurstEnd 4, Ready 10, Still 12, End 14 |

### Schrotflinte (`shotgun`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `Shotgun_Use` | 1–97 | 4.00 | Fire 13 |
| `Shotgun_Idle` | 101–173 | 3.00 | — |
| `Shotgun_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `Shotgun_SprintIn` | 213–223 | 0.42 | — |
| `Shotgun_Sprint` | 227–247 | 0.83 | FootL 0, FootR 10 |
| `Shotgun_SprintOut` | 251–261 | 0.42 | Ready 10 |
| `Shotgun_Fire` | 265–293 | 1.17 | Shot 0, Fire 0 |
| `Shotgun_AimIn` | 297–306 | 0.38 | Aimed 9 |
| `Shotgun_AimIdle` | 310–382 | 3.00 | — |
| `Shotgun_AimFire` | 386–414 | 1.17 | Shot 0, Fire 0 |
| `Shotgun_AimOut` | 418–427 | 0.38 | — |
| `Shotgun_Draw` | 431–443 | 0.50 | Ready 12 |
| `Shotgun_Holster` | 447–455 | 0.33 | Holstered 8 |
| `Shotgun_Inspect_A` | 459–555 | 4.00 | — |
| `Shotgun_Inspect_B` | 559–655 | 4.00 | — |
| `Shotgun_Reload` | 659–723 | 2.67 | MagOut 18, MagIn 45, Ready 64 |

### Fusionsgewehr (`fusion_rifle`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `FusionRifle_Use` | 1–97 | 4.00 | Fire 45 |
| `FusionRifle_Idle` | 101–173 | 3.00 | — |
| `FusionRifle_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `FusionRifle_SprintIn` | 213–223 | 0.42 | — |
| `FusionRifle_Sprint` | 227–247 | 0.83 | FootL 0, FootR 10 |
| `FusionRifle_SprintOut` | 251–261 | 0.42 | Ready 10 |
| `FusionRifle_Fire` | 265–301 | 1.50 | Shot 0, Fire 0 |
| `FusionRifle_AimIn` | 305–314 | 0.38 | Aimed 9 |
| `FusionRifle_AimIdle` | 318–390 | 3.00 | — |
| `FusionRifle_AimFire` | 394–430 | 1.50 | Shot 0, Fire 0 |
| `FusionRifle_AimOut` | 434–443 | 0.38 | — |
| `FusionRifle_Draw` | 447–459 | 0.50 | Ready 12 |
| `FusionRifle_Holster` | 463–471 | 0.33 | Holstered 8 |
| `FusionRifle_Inspect_A` | 475–571 | 4.00 | — |
| `FusionRifle_Inspect_B` | 575–671 | 4.00 | — |
| `FusionRifle_Reload` | 675–735 | 2.50 | MagOut 20, MagIn 42, Ready 60 |
| `FusionRifle_Charge` | 739–757 | 0.75 | ChargeCycle 0 |

### Scharfschützengewehr (`sniper_rifle`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `SniperRifle_Use` | 1–97 | 4.00 | Fire 13 |
| `SniperRifle_Idle` | 101–173 | 3.00 | — |
| `SniperRifle_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `SniperRifle_SprintIn` | 213–224 | 0.46 | — |
| `SniperRifle_Sprint` | 228–248 | 0.83 | FootL 0, FootR 10 |
| `SniperRifle_SprintOut` | 252–263 | 0.46 | Ready 11 |
| `SniperRifle_Fire` | 267–303 | 1.50 | Shot 0, Fire 0 |
| `SniperRifle_AimIn` | 307–319 | 0.50 | Aimed 12 |
| `SniperRifle_AimIdle` | 323–395 | 3.00 | — |
| `SniperRifle_AimFire` | 399–435 | 1.50 | Shot 0, Fire 0 |
| `SniperRifle_AimOut` | 439–451 | 0.50 | — |
| `SniperRifle_Draw` | 455–467 | 0.50 | Ready 12 |
| `SniperRifle_Holster` | 471–479 | 0.33 | Holstered 8 |
| `SniperRifle_Inspect_A` | 483–579 | 4.00 | — |
| `SniperRifle_Inspect_B` | 583–679 | 4.00 | — |
| `SniperRifle_Reload` | 683–747 | 2.67 | MagOut 22, MagIn 45, Ready 64 |

### Raketenwerfer (`rocket_launcher`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `RocketLauncher_Use` | 1–97 | 4.00 | Fire 13 |
| `RocketLauncher_Idle` | 101–173 | 3.00 | — |
| `RocketLauncher_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `RocketLauncher_SprintIn` | 213–225 | 0.50 | — |
| `RocketLauncher_Sprint` | 229–249 | 0.83 | FootL 0, FootR 10 |
| `RocketLauncher_SprintOut` | 253–265 | 0.50 | Ready 12 |
| `RocketLauncher_Fire` | 269–317 | 2.00 | Shot 0, Fire 0 |
| `RocketLauncher_AimIn` | 321–333 | 0.50 | Aimed 12 |
| `RocketLauncher_AimIdle` | 337–409 | 3.00 | — |
| `RocketLauncher_AimFire` | 413–461 | 2.00 | Shot 0, Fire 0 |
| `RocketLauncher_AimOut` | 465–477 | 0.50 | — |
| `RocketLauncher_Draw` | 481–493 | 0.50 | Ready 12 |
| `RocketLauncher_Holster` | 497–505 | 0.33 | Holstered 8 |
| `RocketLauncher_Inspect_A` | 509–605 | 4.00 | — |
| `RocketLauncher_Inspect_B` | 609–705 | 4.00 | — |
| `RocketLauncher_Reload` | 709–787 | 3.25 | MagOut 27, MagIn 55, Ready 78 |

### Scout-Gewehr (`scout_rifle`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `Scout_Use` | 1–97 | 4.00 | Fire 13 |
| `Scout_Idle` | 101–173 | 3.00 | — |
| `Scout_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `Scout_SprintIn` | 213–221 | 0.33 | — |
| `Scout_Sprint` | 225–245 | 0.83 | FootL 0, FootR 10 |
| `Scout_SprintOut` | 249–257 | 0.33 | Ready 8 |
| `Scout_Fire` | 261–269 | 0.33 | Shot 0, Fire 0 |
| `Scout_AimIn` | 273–282 | 0.38 | ScopeOn 7, Aimed 9 |
| `Scout_AimIdle` | 286–358 | 3.00 | — |
| `Scout_AimFire` | 362–370 | 0.33 | Shot 0, Fire 0 |
| `Scout_AimOut` | 374–383 | 0.38 | ScopeOff 0, Move 1 |
| `Scout_Draw` | 387–399 | 0.50 | Ready 12 |
| `Scout_Holster` | 403–411 | 0.33 | Holstered 8 |
| `Scout_Inspect_A` | 415–511 | 4.00 | — |
| `Scout_Inspect_B` | 515–611 | 4.00 | — |
| `Scout_Reload` | 615–659 | 1.83 | Start 0, Move 1, HandOff⟂ 2, MagOut 9, MagIn 24, HandOn⟂ 31, Ready 36, Still 41, End 44 |
| `Scout_ReloadEmpty` | 663–715 | 2.17 | Start 0, Move 1, HandOff⟂ 2, MagOut 9, MagIn 24, Chamber 31, HandOn⟂ 39, Ready 44, Still 49, End 52 |

### Portalkanone (`portal_emitter`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `PortalEmitter_Use` | 1–97 | 4.00 | Fire 13 |
| `PortalEmitter_Idle` | 101–173 | 3.00 | — |
| `PortalEmitter_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `PortalEmitter_SprintIn` | 213–221 | 0.33 | — |
| `PortalEmitter_Sprint` | 225–245 | 0.83 | FootL 0, FootR 10 |
| `PortalEmitter_SprintOut` | 249–257 | 0.33 | Ready 8 |
| `PortalEmitter_Draw` | 261–273 | 0.50 | Ready 12 |
| `PortalEmitter_Holster` | 277–285 | 0.33 | Holstered 8 |
| `PortalEmitter_Inspect_A` | 289–385 | 4.00 | — |
| `PortalEmitter_Inspect_B` | 389–485 | 4.00 | — |

### Magnetgreifer (`magnet_gripper`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `MagnetGripper_Use` | 1–97 | 4.00 | Grab 12 |
| `MagnetGripper_Idle` | 101–173 | 3.00 | — |
| `MagnetGripper_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `MagnetGripper_SprintIn` | 213–221 | 0.33 | — |
| `MagnetGripper_Sprint` | 225–245 | 0.83 | FootL 0, FootR 10 |
| `MagnetGripper_SprintOut` | 249–257 | 0.33 | Ready 8 |
| `MagnetGripper_Draw` | 261–273 | 0.50 | Ready 12 |
| `MagnetGripper_Holster` | 277–285 | 0.33 | Holstered 8 |
| `MagnetGripper_Inspect_A` | 289–385 | 4.00 | — |
| `MagnetGripper_Inspect_B` | 389–485 | 4.00 | — |

### Taschenlampe (`flashlight`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `Flashlight_Use` | 1–97 | 4.00 | Switch 13 |
| `Flashlight_Idle` | 101–173 | 3.00 | — |
| `Flashlight_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `Flashlight_SprintIn` | 213–221 | 0.33 | — |
| `Flashlight_Sprint` | 225–245 | 0.83 | FootL 0, FootR 10 |
| `Flashlight_SprintOut` | 249–257 | 0.33 | Ready 8 |
| `Flashlight_Draw` | 261–273 | 0.50 | Ready 12 |
| `Flashlight_Holster` | 277–285 | 0.33 | Holstered 8 |
| `Flashlight_Inspect_A` | 289–385 | 4.00 | — |
| `Flashlight_Inspect_B` | 389–485 | 4.00 | — |

### Bogen (`bow`)

| Clip | Frames auf der Zeitleiste | Sekunden | Events (Frame im Clip) |
|---|---:|---:|---|
| `Bow_Use` | 1–97 | 4.00 | Marker des Modells, `clips[0].events` im Vertrag |
| `Bow_Idle` | 101–173 | 3.00 | — |
| `Bow_Walk` | 177–209 | 1.33 | FootL 0, FootR 16 |
| `Bow_SprintIn` | 213–221 | 0.33 | — |
| `Bow_Sprint` | 225–245 | 0.83 | FootL 0, FootR 10 |
| `Bow_SprintOut` | 249–257 | 0.33 | Ready 8 |
| `Bow_Draw` | 261–273 | 0.50 | Ready 12 |
| `Bow_Holster` | 277–285 | 0.33 | Holstered 8 |
| `Bow_Inspect_A` | 289–385 | 4.00 | — |
