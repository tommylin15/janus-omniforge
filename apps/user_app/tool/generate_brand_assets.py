from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "branding" / "janus_app_icon_512.webp"
APP_PNG = ROOT / "assets" / "branding" / "janus_app_icon_512.png"
WEB_ICONS = ROOT / "web" / "icons"
WEB_ICON_192 = WEB_ICONS / "Icon-192.png"
WEB_ICON_512 = WEB_ICONS / "Icon-512.png"
WEB_MASKABLE_512 = WEB_ICONS / "maskable-512.png"
APPLE_TOUCH = ROOT / "web" / "apple-touch-icon.png"
FAVICON = ROOT / "web" / "favicon.png"
THEME_BLUE = (11, 79, 214, 255)


def _save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)


def main() -> None:
    source = Image.open(SOURCE).convert("RGBA")
    if source.width < 512 or source.height < 512:
        raise SystemExit(f"branding source is too small: {source.size}")

    icon_512 = source.resize((512, 512), Image.Resampling.LANCZOS)
    icon_192 = icon_512.resize((192, 192), Image.Resampling.LANCZOS)
    apple_touch = icon_512.resize((180, 180), Image.Resampling.LANCZOS)
    favicon = icon_512.resize((64, 64), Image.Resampling.LANCZOS)

    maskable = Image.new("RGBA", (512, 512), THEME_BLUE)
    safe_icon = icon_512.resize((384, 384), Image.Resampling.LANCZOS)
    maskable.alpha_composite(safe_icon, ((512 - 384) // 2, (512 - 384) // 2))

    _save_png(icon_512, APP_PNG)
    _save_png(icon_192, WEB_ICON_192)
    _save_png(icon_512, WEB_ICON_512)
    _save_png(maskable, WEB_MASKABLE_512)
    _save_png(apple_touch, APPLE_TOUCH)
    _save_png(favicon, FAVICON)

    print(f"generated Janus branding assets from {SOURCE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
