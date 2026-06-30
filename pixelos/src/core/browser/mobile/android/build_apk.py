#!/usr/bin/env python3
"""Build NOP Browser Android APK.

Requirements:
  - Android SDK (ANDROID_HOME or ANDROID_SDK_ROOT set)
  - JDK 11+
  - Gradle (or use gradlew)

Usage:
  python build_apk.py              # assembleRelease
  python build_apk.py --debug      # assembleDebug
  python build_apk.py --install    # install on device
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


HERE = Path(__file__).parent
PROJECT = HERE  # android project root
APK_DIR = PROJECT / "app" / "build" / "outputs" / "apk"


def check_prereqs():
    # Check Android SDK
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk:
        print("❌ ANDROID_HOME or ANDROID_SDK_ROOT not set")
        print("   Set it to your Android SDK path, e.g.:")
        print('   export ANDROID_HOME=$HOME/Android/Sdk')
        sys.exit(1)
    print(f"✅ Android SDK: {sdk}")

    # Check Java
    try:
        r = subprocess.run(["java", "-version"], capture_output=True, text=True)
        print(f"✅ Java: {r.stderr.split(chr(10))[0]}")
    except FileNotFoundError:
        print("❌ Java not found. Install JDK 11+.")
        sys.exit(1)

    # Check gradle
    gradlew = PROJECT / "gradlew"
    if not gradlew.exists():
        print("⚠️  gradlew not found, using system gradle")
    return True


def build(debug=False):
    print(f"\n🔨 Building {'debug' if debug else 'release'} APK...\n")

    gradlew = PROJECT / "gradlew"
    if gradlew.exists():
        cmd = [str(gradlew)]
    else:
        cmd = ["gradle"]

    task = "assembleDebug" if debug else "assembleRelease"
    cmd.append(task)

    env = os.environ.copy()
    env["ANDROID_HOME"] = env.get("ANDROID_HOME") or env.get("ANDROID_SDK_ROOT", "")

    result = subprocess.run(cmd, cwd=str(PROJECT), env=env)
    if result.returncode != 0:
        print("❌ Build failed")
        sys.exit(1)

    flavor = "debug" if debug else "release"
    apk = APK_DIR / flavor / f"app-{flavor}.apk"
    unsigned = APK_DIR / flavor / f"app-{flavor}-unsigned.apk"

    if apk.exists():
        print(f"\n✅ APK built: {apk}")
        print(f"   Size: {apk.stat().st_size / 1024 / 1024:.1f} MB")
    elif unsigned.exists():
        print(f"\n✅ APK built (unsigned): {unsigned}")
        print("   Sign with: apksigner sign --ks my-release-key.jks " + str(unsigned))
    else:
        print("\n⚠️  APK not found. Check build output.")
        sys.exit(1)


def install():
    apk_paths = list(APK_DIR.rglob("app-*.apk"))
    if not apk_paths:
        print("❌ No APK found. Build first.")
        sys.exit(1)

    newest = max(apk_paths, key=lambda p: p.stat().st_mtime)
    print(f"📱 Installing {newest}...")
    subprocess.run(["adb", "install", "-r", str(newest)])
    print("✅ Installed")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if "--install" in sys.argv:
        check_prereqs()
        install()
        return

    debug = "--debug" in sys.argv
    check_prereqs()
    build(debug=debug)

    if "--install" in sys.argv:
        install()


if __name__ == "__main__":
    main()
