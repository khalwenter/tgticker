from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


class WatchlistService:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or settings.watchlist_file
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def _read(self) -> list[dict[str, Any]]:
        self._ensure_file()
        raw = self.file_path.read_text(encoding="utf-8").strip()

        if not raw:
            self._write([])
            return []

        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        self._write([])
        return []

    def _write(self, rows: list[dict[str, Any]]) -> None:
        self.file_path.write_text(
            json.dumps(rows, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_item(
        self,
        chat_id: int,
        user_id: int | None,
        symbol: str,
        asset_type: str,
        quantity: float,
        added_price: float,
        currency: str,
    ) -> dict[str, Any]:
        rows = self._read()
        item = {
            "id": f"{chat_id}:{user_id}:{symbol.upper()}:{datetime.now(timezone.utc).timestamp()}",
            "chat_id": chat_id,
            "user_id": user_id,
            "symbol": symbol.upper(),
            "asset_type": asset_type,
            "quantity": quantity,
            "added_price": added_price,
            "currency": currency,
            "added_at": datetime.now(timezone.utc).isoformat(),
        }
        rows.append(item)
        self._write(rows)
        return item

    def list_items(self, chat_id: int, user_id: int | None) -> list[dict[str, Any]]:
        rows = self._read()
        return [
            row for row in rows
            if row.get("chat_id") == chat_id and row.get("user_id") == user_id
        ]

    def remove_item(self, item_id: str, chat_id: int, user_id: int | None) -> bool:
        rows = self._read()
        filtered = [
            row for row in rows
            if not (
                row.get("id") == item_id
                and row.get("chat_id") == chat_id
                and row.get("user_id") == user_id
            )
        ]
        changed = len(filtered) != len(rows)
        if changed:
            self._write(filtered)
        return changed