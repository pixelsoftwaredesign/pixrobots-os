# Pixel Software Design � Copyright 2026
#!/usr/bin/env python3
"""Build NOP Browser for Windows (PyInstaller).

Usage:
  python build_windows.py           # 64-bit EXE in dist/
  python build_windows.py --onefile  # Single EXE
  python build_windows.py --console  # Show console (debug)

Requirements:
  pip install pyinstaller
  pip install PyQt6 PyQt6-WebEngine
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


HERE = Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent.parent.parent  # pixelos/
DIST_DIR = HERE / "dist"
SPEC_DIR = HERE / "build"

APP_NAME = "NOPBrowser"
ICON = HERE / "nop.ico"
ENTRY = HERE / "nop_desktop.py"

PYINSTALLER_ARGS = [
    "pyinstaller",
    "--clean",
    "--noconfirm",
    "--name", APP_NAME,
    "--distpath", str(DIST_DIR),
    "--workpath", str(SPEC_DIR),
    "--add-data", f"{PROJECT_ROOT / 'core' / 'browser'};core/browser",
    "--hidden-import", "PyQt6.QtWebEngineCore",
    "--hidden-import", "PyQt6.QtWebEngineWidgets",
    "--hidden-import", "urllib.request",
    "--hidden-import", "urllib.parse",
    "--hidden-import", "json",
    "--hidden-import", "re",
]

if ICON.exists():
    PYINSTALLER_ARGS.extend(["--icon", str(ICON)])

if "--onefile" in sys.argv:
    PYINSTALLER_ARGS.append("--onefile")

if "--console" not in sys.argv:
    PYINSTALLER_ARGS.append("--windowed")  # no console


def build():
    print(f"🔨 Building NOP Browser for Windows...")
    print(f"   Entry: {ENTRY}")
    print(f"   Dist:  {DIST_DIR}\n")

    if not ENTRY.exists():
        print(f"❌ Entry point not found: {ENTRY}")
        sys.exit(1)

    # Check PyInstaller
    try:
        subprocess.run(["pyinstaller", "--version"], capture_output=True)
    except FileNotFoundError:
        print("❌ PyInstaller not found. Install: pip install pyinstaller")
        sys.exit(1)

    cmd = PYINSTALLER_ARGS + [str(ENTRY)]
    print(f"   Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("\n❌ Build failed")
        sys.exit(1)

    # Check outputs
    exe = DIST_DIR / APP_NAME / f"{APP_NAME}.exe"
    onefile_exe = DIST_DIR / f"{APP_NAME}.exe"

    if exe.exists():
        size_mb = exe.stat().st_size / 1024 / 1024
        print(f"\n✅ Windows build complete!")
        print(f"   {exe}  ({size_mb:.1f} MB)")
        print(f"   Run: {exe}")
    elif onefile_exe.exists():
        size_mb = onefile_exe.stat().st_size / 1024 / 1024
        print(f"\n✅ Windows one-file build complete!")
        print(f"   {onefile_exe}  ({size_mb:.1f} MB)")
    else:
        print("\n⚠️  Build completed but EXE not found at expected path")
        print(f"   Check {DIST_DIR}")

    # Cleanup spec
    spec = HERE / f"{APP_NAME}.spec"
    if spec.exists():
        spec.unlink()


if __name__ == "__main__":
    build()
