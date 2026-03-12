from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


class AlertService:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or settings.price_alert_file
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

    def add_alert(
        self,
        chat_id: int,
        user_id: int | None,
        symbol: str,
        asset_type: str,
        target_price: float,
        last_price: float | None,
    ) -> dict[str, Any]:
        direction = "up"
        if last_price is not None and target_price < last_price:
            direction = "down"

        rows = self._read()
        alert = {
            "id": f"{chat_id}:{user_id}:{symbol.upper()}:{datetime.now(timezone.utc).timestamp()}",
            "chat_id": chat_id,
            "user_id": user_id,
            "symbol": symbol.upper(),
            "asset_type": asset_type,
            "target_price": target_price,
            "direction": direction,
            "is_active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_triggered_at": None,
        }
        rows.append(alert)
        self._write(rows)
        return alert

    def active_alerts(self) -> list[dict[str, Any]]:
        return [row for row in self._read() if row.get("is_active")]

    def list_active_alerts(self, chat_id: int, user_id: int | None) -> list[dict[str, Any]]:
        return [
            row for row in self.active_alerts()
            if row.get("chat_id") == chat_id and row.get("user_id") == user_id
        ]

    def remove_alert(self, alert_id: str, chat_id: int, user_id: int | None) -> bool:
        rows = self._read()
        filtered = [
            row for row in rows
            if not (
                row.get("id") == alert_id
                and row.get("chat_id") == chat_id
                and row.get("user_id") == user_id
            )
        ]
        changed = len(filtered) != len(rows)
        if changed:
            self._write(filtered)
        return changed

    def mark_triggered(self, alert_id: str) -> bool:
        rows = self._read()
        changed = False

        for row in rows:
            if row.get("id") == alert_id and row.get("is_active"):
                row["last_triggered_at"] = datetime.now(timezone.utc).isoformat()
                changed = True
                break

        if changed:
            self._write(rows)

        return changed