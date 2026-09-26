from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "web" / "icons" / "Icon-512.png"
APP_PNG = ROOT / "assets" / "branding" / "janus_app_icon_512.png"
WEB_ICONS = ROOT / "web" / "icons"
WEB_ICON_192 = WEB_ICONS / "Icon-192.png"
WEB_MASKABLE_512 = WEB_ICONS / "maskable-512.png"
APPLE_TOUCH = ROOT / "web" / "apple-touch-icon.png"
FAVICON = ROOT / "web" / "favicon.png"
THEME_BLUE = (11, 79, 214, 255)


def _save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")
    if source.size != (512, 512):
        raise SystemExit(f"PWA icon source must be 512x512: {source.size}")

    icon_192 = source.resize((192, 192), Image.Resampling.LANCZOS)
    apple_touch = source.resize((180, 180), Image.Resampling.LANCZOS)
    favicon = source.resize((64, 64), Image.Resampling.LANCZOS)

    maskable = Image.new("RGBA", (512, 512), THEME_BLUE)
    safe_icon = source.resize((384, 384), Image.Resampling.LANCZOS)
    maskable.alpha_composite(safe_icon, ((512 - 384) // 2, (512 - 384) // 2))

    _save_png(source, APP_PNG)
    _save_png(icon_192, WEB_ICON_192)
    _save_png(maskable, WEB_MASKABLE_512)
    _save_png(apple_touch, APPLE_TOUCH)
    _save_png(favicon, FAVICON)

    print(f"generated Janus install assets from {SOURCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
