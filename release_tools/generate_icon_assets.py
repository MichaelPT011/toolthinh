"""Generate release icon assets for Windows and macOS builds."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "assets" / "build"
PNG_PATH = OUTPUT_DIR / "app_icon_1024.png"
ICO_PATH = OUTPUT_DIR / "app_icon.ico"


def _draw_icon(size: int = 1024) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    outer = int(size * 0.06)
    screen_margin = int(size * 0.15)
    corner = int(size * 0.18)

    draw.rounded_rectangle(
        [outer, outer, size - outer, size - outer],
        radius=corner,
        fill=(17, 24, 39, 255),
    )
    draw.rounded_rectangle(
        [screen_margin, screen_margin, size - screen_margin, size - screen_margin * 1.22],
        radius=int(size * 0.12),
        fill=(244, 247, 250, 255),
    )

    stand_top = int(size * 0.72)
    draw.rounded_rectangle(
        [int(size * 0.42), stand_top, int(size * 0.58), int(size * 0.84)],
        radius=int(size * 0.03),
        fill=(244, 247, 250, 255),
    )
    draw.rounded_rectangle(
        [int(size * 0.28), int(size * 0.82), int(size * 0.72), int(size * 0.9)],
        radius=int(size * 0.04),
        fill=(244, 247, 250, 255),
    )

    play = [
        (int(size * 0.43), int(size * 0.33)),
        (int(size * 0.43), int(size * 0.58)),
        (int(size * 0.63), int(size * 0.455)),
    ]
    draw.polygon(play, fill=(17, 24, 39, 255))
    return image


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image = _draw_icon(1024)
    image.save(PNG_PATH, "PNG")
    image.save(ICO_PATH, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
