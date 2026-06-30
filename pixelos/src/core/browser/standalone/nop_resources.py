# Pixel Software Design � Copyright 2026
#!/usr/bin/env python3
"""NOP Desktop resources — icons, themes, and asset generation."""

import os
import sys
from pathlib import Path

HERE = Path(__file__).parent


def _gen_svg_icon(size=256, color="#e94560"):
    """Generate a simple NOP icon as SVG."""
    r = size // 2
    cx, cy = size // 2, size // 2
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#e94560;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#0f3460;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="{size}" height="{size}" rx="{r*0.2}" fill="url(#bg)"/>
  <text x="{cx}" y="{cy + r*0.15}" text-anchor="middle"
        font-family="monospace" font-size="{r*1.1}" font-weight="bold" fill="white">N</text>
  <text x="{cx}" y="{cy + r*0.45}" text-anchor="middle"
        font-family="monospace" font-size="{r*0.3}" fill="rgba(255,255,255,0.7)">⚡.eth</text>
</svg>'''


def generate_resources():
    """Generate all required resource files."""
    icons_dir = HERE / "icons"
    icons_dir.mkdir(exist_ok=True)

    # SVG icon
    svg_path = icons_dir / "nop.svg"
    svg_path.write_text(_gen_svg_icon())
    print(f"✅ {svg_path}")

    # PNG icon (requires PIL)
    try:
        from PIL import Image, ImageDraw, ImageFont
        for size in [16, 32, 48, 64, 128, 256]:
            img = Image.new("RGBA", (size, size), (233, 69, 96, 255))
            draw = ImageDraw.Draw(img)
            # Draw "N" text
            try:
                font = ImageFont.truetype("arial.ttf", size=int(size * 0.6))
            except Exception:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), "N", font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((size - tw) // 2, (size - th) // 2 - size // 10), "N",
                      fill="white", font=font)
            png_path = icons_dir / f"nop_{size}.png"
            img.save(png_path)
            print(f"✅ {png_path}")
    except ImportError:
        print("⚠️  PIL not installed, skipping PNG generation")
        print("   Install: pip install Pillow")

    # ICO (Windows)
    try:
        from PIL import Image
        img = Image.new("RGBA", (256, 256), (233, 69, 96, 255))
        ico_path = HERE / "nop.ico"
        img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print(f"✅ {ico_path}")
    except Exception:
        print("⚠️  ICO generation skipped")

    # ICNS (macOS)
    if sys.platform == "darwin":
        try:
            from PIL import Image
            iconset = HERE / "nop.iconset"
            iconset.mkdir(exist_ok=True)
            for s in [16, 32, 64, 128, 256, 512]:
                img = Image.new("RGBA", (s, s), (233, 69, 96, 255))
                img.save(iconset / f"icon_{s}x{s}.png")
                img2 = Image.new("RGBA", (s * 2, s * 2), (233, 69, 96, 255))
                img2.save(iconset / f"icon_{s}x{s}@2x.png")
            subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "nop.icns")])
            print(f"✅ {HERE / 'nop.icns'}")
        except Exception as e:
            print(f"⚠️  ICNS generation failed: {e}")


if __name__ == "__main__":
    generate_resources()
