#!/usr/bin/env bash
# Build all PixOS Android apps and package them into a single bundle
set -e

APPS=("pixcore-android" "pixos" "pixos-messenger" "pixconnect" "pixos-livestream" "pixos-office" "pixos-phone" "pixos-nop")
OUTPUT="dist"
mkdir -p "$OUTPUT"

echo "=== Building PixOS Ecosystem ==="

# 1. Build SDK first (publish to local Maven)
echo "[1/8] pixcore-android SDK..."
cd pixcore-android
./gradlew publishToMavenLocal --no-daemon
cd ..

# 2-8. Build all apps
for APP in "${APPS[@]:1}"; do
    echo "[*] Building $APP..."
    cd "$APP"
    ./gradlew assembleDebug --no-daemon
    cp app/build/outputs/apk/debug/*.apk "../$OUTPUT/"
    cd ..
done

echo "=== Bundle ==="
cd "$OUTPUT"
zip -j "pixos-bundle.zip" *.apk
echo "Bundle: $OUTPUT/pixos-bundle.zip"
ls -lh *.apk
