#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Build NOP Browser for Linux (AppImage + .deb)
# Uses PyInstaller + linuxdeploy for AppImage.
#
# Requirements:
#   sudo apt install python3-pip python3-pyqt6 python3-pyqt6.qwebengine
#   pip install pyinstaller
#
# Usage:
#   ./build_linux.sh                # PyInstaller build
#   ./build_linux.sh --appimage     # Create AppImage
#   ./build_linux.sh --deb          # Create .deb package
# ─────────────────────────────────────────────────────────────

set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$HERE/../../../.."
ENTRY="$HERE/nop_desktop.py"
APP_NAME="NOPBrowser"
DIST_DIR="$HERE/dist"
ICON="$HERE/nop.png"

echo "🔨 NOP Browser — Linux Build"
echo "══════════════════════════════"

mkdir -p "$DIST_DIR"

# ── PyInstaller ──────────────────────────────────────────
echo "🏗️  Running PyInstaller..."
PYINST_ARGS=(
    pyinstaller
    --clean --noconfirm
    --name "$APP_NAME"
    --distpath "$DIST_DIR"
    --workpath "$HERE/build"
    --add-data "$PROJECT_ROOT/core/browser:core/browser"
    --hidden-import PyQt6.QtWebEngineCore
    --hidden-import PyQt6.QtWebEngineWidgets
    --hidden-import urllib.request
    --hidden-import urllib.parse
    --hidden-import json re
)

python3 "${PYINST_ARGS[@]}" "$ENTRY"

BINARY="$DIST_DIR/$APP_NAME/$APP_NAME"
DESKTOP="$DIST_DIR/$APP_NAME/$APP_NAME.desktop"

# ── Create .desktop file ─────────────────────────────────
cat > "$DESKTOP" << EOF
[Desktop Entry]
Type=Application
Name=NOP Browser
Comment=Navigateur Web3 PixelOS — .eth .pixel .ipfs
Exec=$BINARY
Icon=$ICON
Terminal=false
Categories=Network;WebBrowser;
Keywords=web3;browser;eth;pixel;ipfs
EOF
chmod +x "$DESKTOP"

# ── Create icon if missing ───────────────────────────────
if [ ! -f "$ICON" ]; then
    echo "⚠️  Icon not found, creating placeholder..."
    python3 -c "
from PIL import Image
img = Image.new('RGBA', (256, 256), (233, 69, 96, 255))
img.save('$ICON')
    " 2>/dev/null || true
fi

# ── AppImage with linuxdeploy ────────────────────────────
if [ "$1" == "--appimage" ]; then
    echo "📦 Creating AppImage..."
    APPDIR="$DIST_DIR/$APP_NAME.AppDir"
    mkdir -p "$APPDIR/usr/bin"
    mkdir -p "$APPDIR/usr/share/applications"
    mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

    cp "$BINARY" "$APPDIR/usr/bin/"
    cp "$DESKTOP" "$APPDIR/usr/share/applications/"
    cp "$ICON" "$APPDIR/usr/share/icons/hicolor/256x256/apps/nop-browser.png"
    cp "$ICON" "$APPDIR/nop-browser.png"

    # Download linuxdeploy
    if ! command -v linuxdeploy &>/dev/null; then
        wget -q "https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage" \
            -O /tmp/linuxdeploy
        chmod +x /tmp/linuxdeploy
        LINUXDEPLOY=/tmp/linuxdeploy
    else
        LINUXDEPLOY=linuxdeploy
    fi

    # Create AppImage via linuxdeploy
    "$LINUXDEPLOY" --appdir "$APPDIR" --output appimage
    APPDIR_PARENT="$(dirname "$APPDIR")"
    find "$APPDIR_PARENT" -name "*$APP_NAME*.AppImage" -exec mv {} "$DIST_DIR/$APP_NAME.AppImage" \;

    if [ -f "$DIST_DIR/$APP_NAME.AppImage" ]; then
        echo "✅ AppImage: $DIST_DIR/$APP_NAME.AppImage"
    fi
fi

# ── .deb package ─────────────────────────────────────────
if [ "$1" == "--deb" ]; then
    echo "📦 Creating .deb package..."
    DEB_DIR="$DIST_DIR/deb/$APP_NAME"
    mkdir -p "$DEB_DIR/DEBIAN"
    mkdir -p "$DEB_DIR/usr/bin"
    mkdir -p "$DEB_DIR/usr/share/applications"
    mkdir -p "$DEB_DIR/usr/share/icons/hicolor/256x256/apps"

    cp "$BINARY" "$DEB_DIR/usr/bin/nop-browser"
    cp "$DESKTOP" "$DEB_DIR/usr/share/applications/"
    cp "$ICON" "$DEB_DIR/usr/share/icons/hicolor/256x256/apps/nop-browser.png"

    # Control file
    cat > "$DEB_DIR/DEBIAN/control" << EOF
Package: nop-browser
Version: 1.0.0
Architecture: amd64
Maintainer: PixelOS <dev@pixelos.org>
Description: NOP Browser — Navigateur Web3 PixelOS
 Résolution .eth .pixel .ipfs .bit .pxl
 Blocage pubs/traceurs, pont Wallet.
Depends: python3-pyqt6, python3-pyqt6.qwebengine
Section: web
Priority: optional
Homepage: https://pixelos.org
EOF

    # Post-install script
    cat > "$DEB_DIR/DEBIAN/postinst" << 'POST'
#!/bin/bash
set -e
update-desktop-database -q 2>/dev/null || true
echo "✅ NOP Browser installé. Lancez avec: nop-browser"
POST
    chmod +x "$DEB_DIR/DEBIAN/postinst"

    dpkg-deb --build "$DEB_DIR" "$DIST_DIR/nop-browser_1.0.0_amd64.deb"
    echo "✅ .deb: $DIST_DIR/nop-browser_1.0.0_amd64.deb"
fi

echo ""
echo "✅ Build complete!"
ls -lh "$DIST_DIR/" 2>/dev/null || true
