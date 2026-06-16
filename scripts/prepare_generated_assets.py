from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "frontend" / "public" / "assets"
GENERATED = ASSET_ROOT / "generated"
PORTRAITS = ASSET_ROOT / "portraits"


def copy_environment(source: Path) -> Path:
    GENERATED.mkdir(parents=True, exist_ok=True)
    out = GENERATED / "noir-table-room.png"
    shutil.copy2(source, out)
    return out


def slice_cast_sheet(source: Path) -> list[Path]:
    PORTRAITS.mkdir(parents=True, exist_ok=True)
    image = Image.open(source).convert("RGB")
    width, height = image.size
    cell_w = width / 7
    outputs = []
    names = ["you", "luna", "rook", "jett", "vesper", "dante", "selene"]
    for idx, name in enumerate(names):
        left = int(idx * cell_w)
        right = int((idx + 1) * cell_w)
        crop = image.crop((left, 0, right, height))
        # Trim a little background while preserving full bust framing.
        crop = crop.resize((512, 512), Image.Resampling.LANCZOS)
        out = PORTRAITS / f"{idx + 1}-{name}.png"
        crop.save(out)
        outputs.append(out)
    sheet_out = GENERATED / "cast-sheet.png"
    shutil.copy2(source, sheet_out)
    return outputs


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: prepare_generated_assets.py <environment.png> <cast-sheet.png>")
    env = copy_environment(Path(sys.argv[1]))
    portraits = slice_cast_sheet(Path(sys.argv[2]))
    print(env)
    for portrait in portraits:
        print(portrait)


if __name__ == "__main__":
    main()
