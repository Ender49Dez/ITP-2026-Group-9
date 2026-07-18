from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path

from receipt_generator import normalize_money


@dataclass(frozen=True, slots=True)
class CatalogItem:
    barcode: str
    name: str
    price: Decimal


class ProductCatalogManager:
    """Loads and looks up barcode or PLU items from a local JSON catalog."""

    def __init__(self, catalog_path: str | Path) -> None:
        self.catalog_path = Path(catalog_path)
        self._items: dict[str, CatalogItem] = {}
        self.load_error: str | None = None
        self.reload()

    @property
    def item_count(self) -> int:
        return len(self._items)

    def reload(self) -> None:
        self._items.clear()
        self.load_error = None

        if not self.catalog_path.exists():
            self.load_error = f"Product catalog not found: {self.catalog_path.name}"
            return

        try:
            raw_items = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            self.load_error = f"Unable to load product catalog: {error}"
            return

        if not isinstance(raw_items, list):
            self.load_error = "The product catalog must contain a JSON list of items."
            return

        for raw_item in raw_items:
            try:
                barcode = self._clean_barcode(raw_item["barcode"])
                name = str(raw_item["name"]).strip()
                price = self._parse_price(raw_item["price"])
                if not name:
                    raise ValueError("Product name cannot be empty.")
            except (KeyError, TypeError, ValueError):
                continue

            self._items[barcode] = CatalogItem(barcode=barcode, name=name, price=price)

    def lookup(self, barcode: str) -> CatalogItem | None:
        cleaned_barcode = self._clean_barcode(barcode)
        return self._items.get(cleaned_barcode)

    def _clean_barcode(self, barcode: str) -> str:
        cleaned_barcode = str(barcode).strip()
        if not cleaned_barcode:
            raise ValueError("Barcode cannot be empty.")
        return cleaned_barcode

    def _parse_price(self, price: object) -> Decimal:
        try:
            return normalize_money(price)
        except (InvalidOperation, ValueError, TypeError) as error:
            raise ValueError("Catalog price must be a valid number.") from error
