# Allgemeiner Design-Prompt – Cube-Escape-Werkzeuge

Diesen Prompt mit einem Werkzeugnamen, einer kurzen Funktion und den Referenzbildern verwenden. Die abgesenkte Portalkanonen-Vorschau dient als Kamerareferenz. Für konkrete Portalkanonen-Details stehen die zwei ausführlichen Prompts in `Werkzeug_Prompts.md`.

## Kurzer allgemeiner Design-Prompt

```text
Entwirf [WERKZEUG] für Cube Escape mit der Funktion [FUNKTION]. Verwende die beigefügte Konzeptzeichnung als Formvorlage und den weißen Roboter sowie die bereits erstellten Werkzeuge als gemeinsame Stilreferenz. Das Werkzeug soll erkennbar zur selben Produktfamilie gehören.

Stilisierte, funktionale Sci-Fi-Technik mit einer klaren Silhouette: weich gerundete weiße/silbergraue Gehäuseschalen, dunkle Graphitmechanik, metallische Gelenke und Kontaktflächen, kleine cyanblaue Anzeigen und Energieelemente. Orange nur als sparsamer Statusakzent. Wenige große nachvollziehbare Bauteile, sichtbare mechanische Funktion, saubere Fugen und kontrollierte Glanzlichter. Keine beliebige neue Form, überladene Dekoration oder realistische Feuerwaffen-Ästhetik. Die Merkmale des Konzepts erhalten und nur Farben, Materialien und Rundungen an den Roboter anpassen.

Erstelle eine kleine Version für die Roboterhand und eine separate große Version für die Egoperspektive. Die große Version besitzt dieselbe Konstruktion mit 150 % Größe und sitzt wie in der beigefügten abgesenkten Portalkanonen-Ansicht tief rechts im Bild, angelehnt an die Bildkomposition von Destiny 2. Die Umgebung und das zentrale Zielfeld bleiben frei. Bewegliche Teile und Leuchtteile bleiben getrennt. Gewünschte Anwendungsbewegungen laufen ausschließlich nach einer Aktion wie „Greifen“, einmalig und ohne Autoplay oder Dauerschleife; anschließend steht das Werkzeug wieder still.
```

## Ausführlicher Auftrag für die Erstellung der Modelle

```text
Entwirf und erstelle ein 3D-Werkzeug für Cube Escape.

WERKZEUG: [Name]
FUNKTION: [Was es im Spiel tun soll]
KONZEPTREFERENZ: [Passendes Feld der beigefügten Konzepttafel oder ein eigenes Konzept]
BEWEGUNG BEIM ANWENDEN: [z. B. keine / aufklappen / greifen / schließen und um die Längsachse rotieren]

Das Werkzeug gehört sichtbar zur gleichen Produktfamilie wie mein beigefügter kleiner weißer Roboter und die bereits erstellte Portalkanone. Das Konzept bestimmt Funktion, Silhouette und Hauptbauteile; der Roboter bestimmt Materialien, Rundungen und Detailgrad. Die Konzeptvorlage darf technisch sinnvoll interpretiert werden, soll aber erkennbar bleiben. Bei einer ungeklärten Bewegungsachse kurz nachfragen und unabhängige Arbeiten fortsetzen.

DESIGNSPRACHE
Stilisierte, funktionale Sci-Fi-Technik. Weich gerundete, klare Gehäuseschalen mit gut lesbarer Silhouette. Weiße bis silbergraue Außenverkleidung; dunkle Graphitmechanik in Fugen, Gelenken, Griffen und tragenden Teilen; sparsame metallische Kontaktflächen und Befestigungen. Kleine cyanblaue Anzeigen und Energieelemente kennzeichnen Funktion und Zustand. Orange bleibt ein kleiner Statusakzent. Keine großflächige orange Lackierung, überladene Dekoration, willkürlichen Kabel oder realistische Feuerwaffen-Details. Form und sichtbare Mechanik sollen die Werkzeugfunktion erklären. Wenige große, nachvollziehbare Bauteile statt beliebiger Kleinteile.

MATERIALKONSISTENZ
Principled-PBR. Lineare RGB-Palette: Armor (0,66; 0,685; 0,72), Mechanik (0,075; 0,08; 0,092), Metall (0,38; 0,395; 0,42), Cyan (0,02; 0,62; 0,95), dunkles Glas (0,006; 0,007; 0,01). Schalen: Metallic 0,42, Roughness 0,30; Mechanik: Metallic 0,70, Roughness 0,39. Glanzlichter weich und kontrolliert; Formen müssen auch ohne Bloom lesbar bleiben. Leuchtflächen mit eigenem Emissionsmaterial, kein mitexportierter Halo als schwebende Geometrie.

ZWEI GETRENNTE MODELLVARIANTEN
1. Kompaktes Weltmodell, passend zur Hand und zu den Proportionen des kleinen Roboters. Für Geräte derselben Familie ungefähr 60 cm Länge und 20–25 cm Breite; bei anderer Funktion sinnvolle Maße wählen und dokumentieren. Der Körper und die Montagepunkte des Roboters werden nicht verändert.
2. Eigene große Egoperspektiv-Version derselben Konstruktion mit 150 % Geometriegröße. Die zusätzliche Größe wird in Geometrie und Bauteilpositionen eingerechnet; Objektskalierungen bleiben 1. Bewegliche Teile, Materialfarben, Designmerkmale und Montageanker stimmen zwischen beiden Größen überein.

ABGESTIMMTE EGOPERSPEKTIVE
Verwende die abgesenkte Portalkanonen-Vorschau als verbindliche Kompositionsreferenz. Das große Werkzeug sitzt tief rechts, angelehnt an das Waffenbild von Destiny 2, ohne dessen Waffendesigns zu kopieren. Umgebung und Fadenkreuz bleiben frei. Nicht wieder zur höheren ersten Kamerahaltung wechseln.
Blender-Kamera am Ursprung, Blick −Y, Z oben, 75° horizontales Sichtfeld, 16:9 mit 1600 × 900 Pixeln, Near Clip 0,03 m. Bei dieser Kamera ist −X die rechte Bildhälfte. Handanker bei (−0,26; −0,66; −0,50) m. Emissions-/Arbeitsachse auf (0; −4; 0) m ausrichten, unter Berücksichtigung des Versatzes zwischen Griff und Arbeitskopf. Ein am unteren Rand angeschnittener Griff ist gewollt. Bei abweichender Werkzeugform die Silhouette visuell prüfen und nötige Abweichungen begründen; nicht durch ein anderes Sichtfeld kaschieren.

MONTAGE UND BEWEGUNG
Meter, Blender Z-up. Ein klarer Asset-Root, benannte Hand-/Stützhandanker, funktionaler Arbeitsanker am Kopf. Bewegliche Teile besitzen echte Gelenkpivots und getrennte Hierarchien; ein drehbarer Kopf erhält einen zusätzlichen Pivot auf seiner Längsachse. Emitter, Anzeigen und Kontaktflächen bleiben getrennt. Kategorie nach Funktion, üblicherweise Interactive; Stil als Tags.
Wenn eine Anwendungsbewegung verlangt ist, implementiere eine sichtbare, tatsächlich abspielbare Animation und exportiere sie für beide Größen. Sie startet ausschließlich durch ein ausdrückliches Anwendungsereignis wie „Kiste greifen“: keine automatische Wiedergabe beim Laden/Ausrüsten und keine Dauerschleife. Pro Aktion einmal abspielen, danach in die ruhende Grundpose zurückkehren; erneute Eingaben während des laufenden Ablaufs nicht beliebig stapeln. Definiere Ruhe-, Anwendungs- und Rückkehrzustand, Achsen, Zeiten und Rotationsgrenzen. Prüfe Kontaktfreiheit in der Bewegung und ob der animierte Arbeitsanker weiter sinnvoll liegt. Eine Bewegungsvorbereitung allein ist dann nicht ausreichend. Einen klaren Aufrufpunkt für die spätere Spielaktion mitliefern. Gameplay-Steuerung, Physik, Kräfte und Trigger nur in einem ausdrücklich beauftragten Zielprojekt integrieren; sie folgen nicht automatisch aus der Modellanimation.

LIEFERUMFANG UND ABNAHME
Erstelle lokale, deterministische Blender-Python-Generatoren, editierbare .blend-Dateien und FBX/GLB für beide Varianten. Bilder oder Fremd-Assets nicht herunterladen; keine Plugins installieren und keine vorhandenen Projekte umstrukturieren. Prüfe die vorhandene Blender-Version und deren tatsächliche API. Erhalte die laufenden Blender-Szenen; neue Ergebnisse in eigenen Szenen anzeigen.
Exports enthalten nur das Asset und nötige Anker/Animationen. Kamera, Licht, Testumgebung, Fadenkreuz und Hilfsobjekte bleiben Präsentation. Liefere Studioansichten des kleinen und großen Modells sowie die abgestimmte Egoperspektiv-Ansicht; bei Bewegung zusätzlich eine Animationsvorschau.
Prüfe Geometrie, UVs, Materialzuweisung, Maße, Pivots, Einheits-Skalierung, Kamera-Clipping und freie Bildmitte. Gespeicherte Modelle erneut öffnen und FBX/GLB unabhängig importieren; Maße, Hierarchien und verlangte Animationsbewegung müssen erhalten bleiben. Renderings visuell prüfen. Berichte klar, was als Blender-Asset geprüft wurde und was im tatsächlichen Spiel noch nicht integriert oder validiert ist.
```
