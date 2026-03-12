from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings


class JsonStorage:
    def __init__(self, file_path: Path | None = None) -> None:
        self.file_path = file_path or settings.data_file

    def _ensure_file(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def append(self, entry: dict[str, Any]) -> None:
        self._ensure_file()
        current = json.loads(self.file_path.read_text(encoding="utf-8"))
        current.append(entry)
        self.file_path.write_text(
            json.dumps(current, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def build_event(
        command: str,
        asset_name: str,
        symbol: str,
        chat_id: int,
        thread_id: int | None,
        user_id: int | None,
        username: str | None,
    ) -> dict[str, Any]:
        return {
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "asset_name": asset_name,
            "symbol": symbol,
            "chat_id": chat_id,
            "thread_id": thread_id,
            "user_id": user_id,
            "username": username,
        }