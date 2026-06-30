#!/usr/bin/env python3
"""Script d'amorçage — curl pip install PixelOS en une ligne."""

def bootstrap():
    import os, sys, subprocess, json, urllib.request, urllib.error
    from pathlib import Path

    VERSION = "2.1.0"
    REPO = "https://api.github.com/repos/agricol/pixelos/zipball/main"

    print(f"🌱 PixelOS Zero-Touch Bootstrap v{VERSION}")
    print(f"   OS: {sys.platform}  Python: {sys.version.split()[0]}")

    target = Path("/opt/pixelos")
    if target.exists():
        print("   PixelOS déjà installé, mise à jour...")
    else:
        target.mkdir(parents=True, exist_ok=True)

    # Télécharger et extraire
    print("   Téléchargement...")
    try:
        req = urllib.request.Request(REPO)
        with urllib.request.urlopen(req, timeout=60) as r:
            zip_data = r.read()
        zip_path = target / "source.zip"
        zip_path.write_bytes(zip_data)

        import zipfile
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(target)
        zip_path.unlink()

        # Déplacer les fichiers du sous-dossier vers la racine
        for child in target.iterdir():
            if child.is_dir() and child.name.startswith("agricol-pixelos-"):
                for src in child.iterdir():
                    dest = target / src.name
                    if src.is_dir():
                        import shutil
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.move(str(src), str(dest))
                    else:
                        src.rename(dest)
                child.rmdir()
                break
    except Exception as e:
        print(f"   ⚠️  Téléchargement échoué: {e}")
        print("   Utilisation du dossier local...")

    # Lancer l'installateur
    sys.path.insert(0, str(target / "src"))
    from core.boot.installer import ZeroTouchInstaller

    installer = ZeroTouchInstaller()
    result = installer.run()
    print(json.dumps(result, indent=2))

    if result.get("success"):
        print("\n✅ PixelOS installé avec succès!")
    else:
        print(f"\n⚠️  Installation partielle ({len(result.get('errors',[]))} erreurs)")


if __name__ == "__main__":
    bootstrap()
