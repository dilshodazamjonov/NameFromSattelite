from __future__ import annotations

import string
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "data" / "templates"
IMAGE_SIZE = 256


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for font_path in candidates:
        path = Path(font_path)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def fit_font(letter: str) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    canvas = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), "white")
    draw = ImageDraw.Draw(canvas)

    for size in range(220, 40, -4):
        font = load_font(size)
        bbox = draw.textbbox((0, 0), letter, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        if width <= IMAGE_SIZE * 0.78 and height <= IMAGE_SIZE * 0.78:
            return font

    return load_font(96)


def create_template(letter: str) -> Image.Image:
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), "white")
    draw = ImageDraw.Draw(image)
    font = fit_font(letter)
    bbox = draw.textbbox((0, 0), letter, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    x = (IMAGE_SIZE - width) / 2 - bbox[0]
    y = (IMAGE_SIZE - height) / 2 - bbox[1]
    draw.text((x, y), letter, fill="black", font=font)
    return image


def main() -> None:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    for letter in string.ascii_uppercase:
        image = create_template(letter)
        image.save(TEMPLATE_DIR / f"{letter}.png")
    print(f"Generated 26 templates in {TEMPLATE_DIR}")


if __name__ == "__main__":
    main()
