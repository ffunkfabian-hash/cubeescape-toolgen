# Kompatibilitätseinstieg

Die einzige aktuelle Implementierung liegt in `viewer/` (SwiftUI + SceneKit, wie Robogen).
`bash toolgen/mac_viewer/build_viewer.sh [Ausgabe]` leitet an `viewer/build.sh` weiter.
Die App entsteht unter `<Ausgabe>/ToolGenViewer.app`, standardmäßig `output/_quick`.

[Bedienung und Modelle](../../README.md)
