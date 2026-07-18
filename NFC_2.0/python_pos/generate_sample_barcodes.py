from __future__ import annotations

import json
from pathlib import Path
import re

from barcode import Code128
from barcode.writer import ImageWriter


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return cleaned.strip("_") or "item"


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    catalog_path = base_dir / "product_catalog.json"
    output_dir = base_dir / "sample_barcodes"
    output_dir.mkdir(parents=True, exist_ok=True)

    products = json.loads(catalog_path.read_text(encoding="utf-8"))
    generated_files: list[Path] = []

    for product in products:
        barcode_value = str(product["barcode"]).strip()
        product_name = str(product["name"]).strip()
        file_stem = f"{barcode_value}_{slugify(product_name)}"
        output_path = output_dir / file_stem

        Code128(barcode_value, writer=ImageWriter()).save(
            str(output_path),
            options={
                "module_width": 0.6,
                "module_height": 48,
                "font_size": 26,
                "text_distance": 10,
                "quiet_zone": 12,
                "dpi": 300,
                "write_text": True,
            },
        )
        generated_files.append(output_path.with_suffix(".png"))

    print("Generated sample barcodes:")
    for file_path in generated_files:
        print(file_path)


if __name__ == "__main__":
    main()
