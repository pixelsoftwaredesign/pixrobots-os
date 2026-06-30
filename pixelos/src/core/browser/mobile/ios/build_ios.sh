#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Build NOP Browser for iOS
# Requirements: Xcode 14+, iOS 15.0+ target
#
# Usage:
#   ./build_ios.sh              # Build for simulator
#   ./build_ios.sh --device     # Build for physical device (needs signing)
#   ./build_ios.sh --archive    # Create .xcarchive for App Store
# ─────────────────────────────────────────────────────────────

set -e

PROJECT_NAME="NopBrowser"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
DERIVED_DATA="$BUILD_DIR/DerivedData"

mkdir -p "$BUILD_DIR"

echo "🔨 NOP Browser — iOS Build"
echo "═══════════════════════════"

if [ "$1" == "--archive" ]; then
    echo "📦 Creating .xcarchive..."
    xcodebuild archive \
        -project "$SCRIPT_DIR/$PROJECT_NAME.xcodeproj" \
        -scheme "$PROJECT_NAME" \
        -configuration Release \
        -archivePath "$BUILD_DIR/$PROJECT_NAME.xcarchive" \
        -derivedDataPath "$DERIVED_DATA" \
        CODE_SIGN_STYLE=Manual \
        CODE_SIGN_IDENTITY="" \
        PROVISIONING_PROFILE_SPECIFIER=""

    echo "✅ Archive: $BUILD_DIR/$PROJECT_NAME.xcarchive"

elif [ "$1" == "--device" ]; then
    echo "📱 Building for iOS device (release)..."
    xcodebuild \
        -project "$SCRIPT_DIR/$PROJECT_NAME.xcodeproj" \
        -scheme "$PROJECT_NAME" \
        -configuration Release \
        -destination 'generic/platform=iOS' \
        -derivedDataPath "$DERIVED_DATA" \
        CODE_SIGN_STYLE=Automatic \
        build

    echo "✅ Build complete. Find .app in $DERIVED_DATA"

else
    echo "📱 Building for iOS simulator (debug)..."
    xcodebuild \
        -project "$SCRIPT_DIR/$PROJECT_NAME.xcodeproj" \
        -scheme "$PROJECT_NAME" \
        -configuration Debug \
        -destination 'platform=iOS Simulator,name=iPhone 15,OS=17.0' \
        -derivedDataPath "$DERIVED_DATA" \
        build

    APP_PATH=$(find "$DERIVED_DATA" -name "*.app" -type d | head -1)
    if [ -n "$APP_PATH" ]; then
        echo "✅ Build complete: $APP_PATH"
        echo "   Run with: xcrun simctl install booted \"$APP_PATH\""
    fi
fi

echo ""
echo "📊 Build files:"
ls -la "$BUILD_DIR" 2>/dev/null || true
