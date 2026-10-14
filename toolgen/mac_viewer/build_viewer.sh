#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/.build"
APP_DIR="$BUILD_DIR/ToolGenViewer.app"
MACOS_DIR="$APP_DIR/Contents/MacOS"
RES_DIR="$APP_DIR/Contents/Resources"

mkdir -p "$MACOS_DIR" "$RES_DIR"
mkdir -p "$RES_DIR/toolgen"

cd "$SCRIPT_DIR"
swift build -c release

cp ".build/release/ToolGenViewer" "$MACOS_DIR/ToolGenViewer"
chmod +x "$MACOS_DIR/ToolGenViewer"
cp "$SCRIPT_DIR/../build_toolset.py" "$SCRIPT_DIR/../tool_contract.py" "$SCRIPT_DIR/../blender_worker.py" "$RES_DIR/toolgen/"

cat > "$APP_DIR/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>ToolGenViewer</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleDisplayName</key>
    <string>Cube Escape ToolGen Viewer</string>
    <key>CFBundleIdentifier</key>
    <string>de.ffunk.ToolGenViewer</string>
    <key>CFBundleVersion</key>
    <string>0.1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>0.1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>14.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
EOF

echo "Built app bundle: $APP_DIR"
