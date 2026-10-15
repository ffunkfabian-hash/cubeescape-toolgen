# Änderungen

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
