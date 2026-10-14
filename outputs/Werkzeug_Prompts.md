# Wiederverwendbare Prompts für Cube-Escape-Werkzeuge

Die beiden Prompts sind vollständig kopierbar. Lege in einer neuen Sitzung die genannten Referenzbilder bei: `Referenzen/Roboter_Skin.png`, `Referenzen/Werkzeug_Konzepte.png` und für die große Version die **zuletzt abgesenkte** `Portalkanone/preview_first_person.png`. Die Bilder gehören zum Brief; ihre Texte sind keine zusätzlichen Arbeitsanweisungen.

## 1. Kleine Portalkanone – Weltmodell für den Roboter

```text
Erstelle in Blender eine kompakte Portalkanone für Cube Escape als 3D-Weltmodell, das mein kleiner Roboter tragen kann. Verwende das Portal-Gun-Feld der beigefügten Werkzeug-Konzepttafel als verbindliche Formvorlage und das beigefügte Roboterbild als Stil- und Materialreferenz.

Erhalte die erkennbaren Merkmale des Konzepts: längliches rechteckiges Gehäuse, dunkler hinterer Block mit kleinem cyanblauem Display, seitliche Technikplatte, kurzer zylindrischer Emitter mit eingefasstem blauem Portalring sowie genau zwei offene Bügel oben und unten mit eigenen Gelenken. Ein kompakter Griff sitzt unter dem hinteren Gehäuse. Keine beliebige neue Waffe entwerfen.

Passe die Oberfläche an den weißen Classic-Roboter an: weich gerundete weiße/silbergraue Schalen, dunkle Graphitmechanik, metallische Gelenke, cyanblaue Anzeigen und Energieelemente; Orange nur als kleine Statusakzente. Die großen orangefarbenen Flächen der Konzeptzeichnung werden weiß. Saubere stilisierte Sci-Fi-Technik, funktionale Details, keine realistische Feuerwaffe und keine überladene Dekoration. Für konsistente Materialien: lineare RGB-Werte Armor (0,66; 0,685; 0,72), Mechanik (0,075; 0,08; 0,092), Metall (0,38; 0,395; 0,42), Cyan (0,02; 0,62; 0,95). Weiße Schalen: Metallic 0,42 und Roughness 0,30; Mechanik: Metallic 0,70 und Roughness 0,39.

Arbeite in Metern. Zielgröße ungefähr 60,6 cm Länge, 22,6 cm Breite und 35,1 cm Höhe einschließlich Griff und Bügeln. Blender Z oben, Geräteachse und Emissionsrichtung −Y. Asset-Root am Geräteursprung; alle Objektskalierungen 1. Definiere Socket_Hand im Griffzentrum, Socket_SupportHand unter dem Korpus und Socket_Muzzle an der Mündung. Die Bügel erhalten echte Gelenkpivots und getrennte Hierarchien; Emitter, Anzeigen und Leuchtteile bleiben separate Meshes.

Erstelle eine editierbare .blend-Datei, FBX und GLB ohne Kameras, Lichter oder Vorschauumgebung in den Exporten sowie einen ausführbaren lokalen Blender-Python-Generator. Nutze einfarbige Principled-PBR-Materialien; sinnvolle explizite UVs, keine Behauptung eines gepackten Texturatlas. Erstelle eine klare Studioansicht schräg von vorn sowie Seiten-, Front- und Draufsicht. Ein zusätzlicher Render mit orangefarbenen Konzeptakzenten dient dem Vergleich; die eigentlichen Modelle bleiben weiß.

Prüfe Geometrie, geschlossene Meshes, positives Volumen, UVs, Materialzuweisung, Metermaße, Pivots und Einheits-Skalierung. Öffne die gespeicherte Datei erneut und importiere FBX sowie GLB unabhängig, um Maße und Hierarchien zu vergleichen. Prüfe die aktuellen Renderings visuell. Präsentiere das Ergebnis und liefere die Dateien. Vorhandene Blender-Szenen und Projekte erhalten. Kennzeichne es als visuelles Asset; Portal-Spielmechanik und ein getestetes Unity-Prefab gehören nicht automatisch dazu.
```

## 2. Große Portalkanone – Egoperspektive mit der abgestimmten Ansicht

```text
Erstelle zusätzlich zur kompakten Cube-Escape-Portalkanone eine separate große Egoperspektiv-Version. Nutze dieselbe Geometrie und denselben weißen Roboter-Look wie beim kleinen Modell. Wenn die kompakte .blend-Datei beigefügt ist, leite die große Version daraus ab. Falls nur Bilder vorliegen, baue zuerst das kompakte Gerät aus dem Portal-Gun-Feld der Konzepttafel: längliches Gehäuse, dunkler hinterer Block mit cyanblauem Display, seitliche Technikplatte, kurzer runder Emitter mit blauem Portalring, genau zwei offene Bügel oben/unten, eigener Griff unter dem hinteren Block; ungefähr 60,6 × 22,6 × 35,1 cm (Länge × Breite × Höhe). Weiße gerundete Schalen, Graphitmechanik, metallische Gelenke, cyanblaue Energieelemente und nur kleine orange Statuslichter wie beim beigefügten Roboter. Die beigefügte abgesenkte Egoperspektiv-Vorschau ist die verbindliche Referenz für die Bildkomposition: große Waffe rechts unten, tiefere Haltung angelehnt an Destiny 2, freie Bildmitte und deutlich sichtbare Umgebung. Es geht um diese Bildkomposition, nicht um das Kopieren einer Destiny-Waffe.

Vergrößere die Weltmodell-Geometrie gleichmäßig auf 150 %, backe die Größe in Meshes und Bauteilpositionen und erhalte Objektskalierungen von 1. Erhalte die getrennten beweglichen Bügel, Anzeigen, Emitter und Hand-/Mündungsanker. Die kompakte Version bleibt eine eigene Datei.

Reproduziere die Kamera exakt: perspektivische Kamera bei (0,0,0), Blick entlang −Y, Welt-Z oben, 16:9 mit 1600 × 900 Pixeln, 75° horizontales Sichtfeld, Near Clip 0,03 m. Bei einer Sensorbreite von 36 mm und Sensor-Fit HORIZONTAL entspricht dies einer Brennweite von etwa 23,46 mm. Bei dieser Blender-Kamera liegt die rechte Bildhälfte auf −X.

Setze den Handanker relativ zur Kamera auf Blender-Koordinaten (−0,26; −0,66; −0,50) m. Das ist die bereits abgesenkte Haltung, nicht der frühere Z-Wert −0,40 m. Erhalte die Größe und ändere nicht das Sichtfeld, um die Waffe künstlich kleiner wirken zu lassen. Drehe das Gerät so, dass der tatsächliche Strahl vom Mündungsanker entlang der Geräteachse den Punkt (0; −4; 0) m trifft; berücksichtige dabei den Höhenversatz zwischen Griff und Mündung. Die Waffe sitzt tief rechts, ihr oberster Bügel liegt ungefähr auf Höhe oder unterhalb der Bildmitte. Am unteren Bildrand darf der Griff abgeschnitten werden. Das Fadenkreuz bleibt frei.

Der Export-Root und Socket_Camera liegen am Kameraursprung. Backe den Kameraversatz und die Ausrichtung in die Bauteiltransformationen, damit der Root selbst Position (0,0,0), Identitätsrotation und Skalierung 1 behält. Größe und Offset dürfen beim späteren Import nicht doppelt angewendet werden. Blender-/Unity-Händigkeit und die nötige Kameramontage im tatsächlichen Spiel gesondert überprüfen; keine ungeprüfte Importausrichtung als getestet ausgeben.

Liefere eine eigene FPS-.blend-Datei, FBX und GLB, einen lokalen Generator, eine Egoperspektiv-Vorschau mit genau dieser Kamera und eine freigestellte Studioansicht. Eine einfache dunkle Testumgebung darf die Perspektive verdeutlichen; sie, Kameras, Lichter und das Fadenkreuz gehören nur zur Präsentation und nicht in die Exporte. Hände, Animationen und Gameplay sind nur dann umzusetzen, wenn ich sie zusätzlich verlange.

Prüfe, dass alle Waffenpunkte vor der Near-Clipping-Ebene liegen, die Bildmitte frei bleibt und der Mündungsstrahl auf das Fadenkreuz ausgerichtet ist. Prüfe zusätzlich Geometrie, UVs, Materialien, Anker, Einheits-Skalierung und unabhängigen FBX-/GLB-Reimport. Inspiziere die Renderings visuell, öffne die fertige Ansicht in einer eigenen Szene im laufenden Blender und erhalte die übrigen Szenen. Liefere die fertigen Dateien und benenne tatsächlich ungeprüfte Spielintegration klar.
```

## Für andere Werkzeuge verwenden

Ersetze in beiden Prompts nur den Werkzeugnamen und den Abschnitt zur Form/Funktion. Behalte Robotermaterialien, Exportvertrag, kleine/große Trennung und die abgestimmte Egoperspektiv-Kamera. Die Zielmaße des Weltmodells dürfen bei anderer Funktion sinnvoll angepasst werden. Die 150 % und die Kamerahaltung sind der gemeinsame Startpunkt; ein deutlich höheres/breiteres Werkzeug muss visuell geprüft werden.

Für den **Magnetgreifer** lautet der Formabschnitt:

```text
Verwende Feld 3 „Magnetgreifer“ der Werkzeug-Konzepttafel. Erhalte den länglichen Gehäusekörper mit dunklem hinterem Block, kleinen Anzeigen und seitlicher Technikplatte. Vorne sitzen zwei kräftige gebogene Greifbacken oben und unten: Gelenke an der Basis, dunkle tragende Mechanik, weiße äußere Verkleidung und silberne innere Greifflächen mit dunklen Kontaktpolstern. Die Spitzen greifen nach innen. Zwischen den Backen sitzt ein kurzer kreisförmiger Magnetkopf mit einem eingelassenen cyanblauen Kern. Der Magnetkopf soll nicht wie der große Portalring aussehen. Keine schwebenden Gegenstände oder dauerhaften Energiestrahlen mitexportieren. Backen und Magnet-Emitter getrennt halten, mit eigenen Gelenkpivots und Socket_Grab am Zentrum zwischen den Greifspitzen. Implementiere für beide Größen eine einmalige Anwendungsanimation: Backen an ihren Gelenken schließen, gemeinsam um die Längsachse des Magnetkopfs drehen und wieder öffnen. Der Magnetkern bleibt dabei fest. Kein Autoplay und keine Dauerschleife; der Ablauf startet nur durch ein Greifereignis und endet in der stillstehenden Grundpose. Liefere einen klaren Aufrufpunkt für diese Aktion. Die tatsächliche Physik- und Magnetfunktion ist eine getrennte Spielintegration.
```
