#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Build NOP Browser for macOS (Apple Silicon + Intel)
# Uses PyInstaller to create a standalone .app bundle.
#
# Requirements:
#   brew install python-tk
#   pip install pyinstaller PyQt6 PyQt6-WebEngine
#
# Usage:
#   ./build_macos.sh                # Universal ARM64+x86_64 .app
#   ./build_macos.sh --onefile      # Single .app file
#   ./build_macos.sh --notarize     # Notarize for distribution
#   ./build_macos.sh --dmg          # Create DMG
# ─────────────────────────────────────────────────────────────

set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$HERE/../../../.."
ENTRY="$HERE/nop_desktop.py"
APP_NAME="NOPBrowser"
DIST_DIR="$HERE/dist"
ICON="$HERE/nop.icns"

echo "🔨 NOP Browser — macOS Build"
echo "══════════════════════════════"

# Detect architecture
ARCH=$(uname -m)
echo "🏗️  Architecture: $ARCH"

# Create icon if missing
if [ ! -f "$ICON" ]; then
    echo "⚠️  Icon not found: $ICON"
    echo "   Creating placeholder..."
    mkdir -p "$HERE/nop.iconset"
    for s in 16 32 64 128 256 512; do
        # Generate solid color PNG via python
        python3 -c "
from PIL import Image
img = Image.new('RGBA', ($s, $s), (233, 69, 96, 255))
img.save('$HERE/nop.iconset/icon_${s}x${s}.png')
img = Image.new('RGBA', ($s*2, $s*2), (233, 69, 96, 255))
img.save('$HERE/nop.iconset/icon_${s}x${s}@2x.png')
        " 2>/dev/null || true
    done
    iconutil -c icns "$HERE/nop.iconset" -o "$ICON" 2>/dev/null || true
fi

# ── PyInstaller ──────────────────────────────────────────
PYINST_ARGS=(
    pyinstaller
    --clean --noconfirm
    --name "$APP_NAME"
    --distpath "$DIST_DIR"
    --workpath "$HERE/build"
    --windowed
    --add-data "$PROJECT_ROOT/core/browser:core/browser"
    --hidden-import PyQt6.QtWebEngineCore
    --hidden-import PyQt6.QtWebEngineWidgets
    --hidden-import urllib.request
    --hidden-import urllib.parse
    --hidden-import json re
)

if [ -f "$ICON" ]; then
    PYINST_ARGS+=(--icon "$ICON")
fi

if [ "$1" == "--onefile" ]; then
    PYINST_ARGS+=(--onefile)
fi

echo "🏗️  Running PyInstaller..."
python3 "${PYINST_ARGS[@]}" "$ENTRY"

# ── Fix library paths for Apple Silicon ──────────────────
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
if [ -d "$APP_BUNDLE" ]; then
    echo "📦 .app bundle: $APP_BUNDLE"

    # Remove quarantine attribute
    xattr -dr com.apple.quarantine "$APP_BUNDLE" 2>/dev/null || true

    # Sign for local execution
    codesign --deep --force --verify --verbose --sign "-" "$APP_BUNDLE" 2>/dev/null || true

    APP_SIZE=$(du -sh "$APP_BUNDLE" | cut -f1)
    echo "   Size: $APP_SIZE"
    echo "   Run: open \"$APP_BUNDLE\""
fi

# ── Create DMG ───────────────────────────────────────────
if [ "$1" == "--dmg" ] || [ "$2" == "--dmg" ]; then
    echo "📀 Creating DMG..."
    DMG_PATH="$DIST_DIR/$APP_NAME.dmg"
    create-dmg \
        --volname "$APP_NAME" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "$APP_NAME.app" 175 190 \
        --hide-extension "$APP_NAME.app" \
        --app-drop-link 425 190 \
        "$DMG_PATH" \
        "$APP_BUNDLE" \
        2>/dev/null || {
            # Fallback: hdiutil
            hdiutil create -volname "$APP_NAME" -srcfolder "$APP_BUNDLE" \
                -ov -format UDZO "$DIST_DIR/$APP_NAME.dmg"
        }
    echo "✅ DMG: $DMG_PATH"
fi

# ── Notarize ─────────────────────────────────────────────
if [ "$1" == "--notarize" ] || [ "$2" == "--notarize" ]; then
    echo "🔏 Notarizing..."
    DMG_PATH="$DIST_DIR/$APP_NAME.dmg"
    if [ -f "$DMG_PATH" ]; then
        xcrun notarytool submit "$DMG_PATH" \
            --apple-id "${APPLE_ID:?Set APPLE_ID}" \
            --team-id "${TEAM_ID:?Set TEAM_ID}" \
            --password "${APP_PASSWORD:?Set APP_PASSWORD}" \
            --wait
        xcrun stapler staple "$DMG_PATH"
        echo "✅ Notarized"
    fi
fi

echo ""
echo "✅ Build complete!"
echo "   $DIST_DIR/"
ls -lh "$DIST_DIR" 2>/dev/null || true
