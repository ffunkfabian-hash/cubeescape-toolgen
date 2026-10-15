#!/usr/bin/env bash
# Robogen-style universal native viewer with cached compilation and bundled data/backend.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="${1:-$ROOT/output/_quick}"
BUILD="$HERE/.build"
mkdir -p "$BUILD"
[ -f "$OUT/catalog.json" ] || { echo "missing catalog: run python3 toolgen/generate_tools.py --tier quick" >&2; exit 1; }
VERSION="$(python3 -c "import sys;sys.path.insert(0,'$ROOT/toolgen');from version import VERSION;print(VERSION)")"
ARCHS="${TOOLGEN_ARCHS:-arm64 x86_64}"
STAMP="$(cat "$HERE"/Sources/*.swift "$0" | shasum | cut -c1-16)-$(swiftc --version | shasum | cut -c1-8)-$ARCHS"
if [ -f "$BUILD/ToolGenViewer" ] && [ "$(cat "$BUILD/sources.stamp" 2>/dev/null)" = "$STAMP" ]; then
  echo "sources unchanged - reusing compiled viewer"
else
  pids=()
  for arch in $ARCHS; do
    swiftc -O -parse-as-library -swift-version 5 -target "$arch-apple-macos14.0" \
      -framework SwiftUI -framework SceneKit -framework AppKit -framework Metal -framework UniformTypeIdentifiers \
      "$HERE"/Sources/*.swift -o "$BUILD/ToolGenViewer-$arch" &
    pids+=($!)
  done
  for pid in "${pids[@]}"; do wait "$pid"; done
  binaries=()
  for arch in $ARCHS; do binaries+=("$BUILD/ToolGenViewer-$arch"); done
  lipo -create "${binaries[@]}" -output "$BUILD/ToolGenViewer"
  echo "$STAMP" > "$BUILD/sources.stamp"
fi
TASK_BUNDLE="$(mktemp -d "$BUILD/bundle.XXXXXX")"
trap 'rm -rf "$TASK_BUNDLE"' EXIT
APP="$TASK_BUNDLE/ToolGenViewer.app"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/ViewerData" "$APP/Contents/Resources/backend"
cp "$BUILD/ToolGenViewer" "$APP/Contents/MacOS/ToolGenViewer"
python3 "$ROOT/scripts/bundle_viewer.py" "$OUT" "$APP/Contents/Resources" "$ROOT"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>ToolGenViewer</string>
<key>CFBundleExecutable</key><string>ToolGenViewer</string>
<key>CFBundleDisplayName</key><string>Cube Escape Toolgen</string>
<key>CFBundleIdentifier</key><string>com.cubeescape.toolgenviewer</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>$VERSION</string>
<key>CFBundleVersion</key><string>$VERSION</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSPrincipalClass</key><string>NSApplication</string>
</dict></plist>
PLIST
codesign --force --deep --sign - "$APP"
rm -rf "$OUT/ToolGenViewer.app"
mv "$APP" "$OUT/ToolGenViewer.app"
echo "Built $OUT/ToolGenViewer.app"
