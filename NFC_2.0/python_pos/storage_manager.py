from __future__ import annotations

import json
from pathlib import Path

from receipt_generator import Receipt


class StorageManager:
    """Handles local receipt storage and serial-ready JSON payloads."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_receipt_json(self, receipt: Receipt) -> Path:
        file_path = self.base_dir / f"Receipt_{receipt.receipt_id}.json"
        with file_path.open("w", encoding="utf-8") as file_handle:
            json.dump(receipt.to_dict(), file_handle, indent=2)
        return file_path

    def build_receipt_serial_payload(self, receipt: Receipt, base_url: str = "") -> dict:
        payload = receipt.to_dict()
        cleaned_base_url = base_url.strip()
        if cleaned_base_url:
            payload["receipt_url"] = f"{cleaned_base_url.rstrip('/')}/{receipt.receipt_id}"
        return payload
