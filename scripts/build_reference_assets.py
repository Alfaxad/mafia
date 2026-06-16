from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT.parent / "ai-native"
ASSET_DIR = ROOT / "src" / "mafia" / "ui" / "assets"
PORTRAITS = ASSET_DIR / "portraits"
REFERENCE = ASSET_DIR / "reference"


PORTRAIT_CROPS = {
    "p1-you": (642, 130, 822, 318),
    "p2-luna": (900, 160, 1096, 360),
    "p3-rook": (995, 336, 1190, 536),
    "p4-jett": (795, 486, 990, 690),
    "p5-vesper": (496, 492, 700, 700),
    "p6-dante": (316, 332, 514, 536),
    "p7-selene": (456, 138, 662, 338),
}


def save_portrait(source: Image.Image, name: str, crop: tuple[int, int, int, int]) -> None:
    image = source.crop(crop).resize((288, 288), Image.Resampling.LANCZOS).convert("RGBA")
    # Preserve the portrait, but mask it into a game-token circle.
    mask = Image.new("L", image.size, 0)
    mask = ImageOps.fit(mask, image.size)
    circle = Image.new("L", image.size, 0)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(circle)
    draw.ellipse((4, 4, image.size[0] - 4, image.size[1] - 4), fill=255)
    image.putalpha(circle)
    # Slightly lift contrast for small in-game sizes.
    rgb = Image.new("RGBA", image.size, (0, 0, 0, 0))
    rgb.alpha_composite(image)
    enhanced = ImageEnhance.Contrast(rgb).enhance(1.08)
    enhanced.save(PORTRAITS / f"{name}.png")


def main() -> None:
    PORTRAITS.mkdir(parents=True, exist_ok=True)
    REFERENCE.mkdir(parents=True, exist_ok=True)
    ui1 = Image.open(SOURCE_DIR / "ui-1.png").convert("RGB")
    ui3 = Image.open(SOURCE_DIR / "ui-3.png").convert("RGB")
    ui4 = Image.open(SOURCE_DIR / "ui-4.png").convert("RGB")
    ui5 = Image.open(SOURCE_DIR / "ui-5.png").convert("RGB")

    for name, crop in PORTRAIT_CROPS.items():
        save_portrait(ui1, name, crop)

    # Background and panel references. These are not full screenshots; they are
    # cropped atmospheric surfaces used behind code-native controls.
    ui1.crop((270, 70, 1310, 830)).resize((1400, 900), Image.Resampling.LANCZOS).save(
        REFERENCE / "table-room.png"
    )
    ui4.crop((260, 60, 1320, 820)).resize((1400, 900), Image.Resampling.LANCZOS).save(
        REFERENCE / "hot-seat-room.png"
    )
    ui5.crop((330, 35, 1280, 820)).resize((1400, 900), Image.Resampling.LANCZOS).save(
        REFERENCE / "endgame-room.png"
    )
    ui3.crop((1090, 525, 1295, 790)).resize((420, 520), Image.Resampling.LANCZOS).save(
        REFERENCE / "assistant-panel.png"
    )


if __name__ == "__main__":
    main()
