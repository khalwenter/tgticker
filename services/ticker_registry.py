from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TickerRegistry:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self._ensure_file()

    def _ensure_file(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        self._ensure_file()
        return json.loads(self.file_path.read_text(encoding="utf-8"))

    def save(self, tickers: list[dict[str, Any]]) -> None:
        self.file_path.write_text(
            json.dumps(tickers, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_by_command(self, command: str) -> dict[str, Any] | None:
        command = command.strip().lower()
        for item in self.load():
            if item["command"] == command:
                return item
        return None

    def add_ticker(self, command: str, symbol: str, asset_type: str) -> dict[str, Any]:
        command = command.strip().lower()
        symbol = symbol.strip().upper()
        asset_type = asset_type.strip().lower()

        tickers = self.load()

        for item in tickers:
            if item["command"] == command:
                raise ValueError(f"Command '{command}' already exists.")
            if item["symbol"] == symbol:
                raise ValueError(f"Symbol '{symbol}' already exists.")

        new_item = {
            "command": command,
            "symbol": symbol,
            "asset_type": asset_type,
        }
        tickers.append(new_item)
        self.save(tickers)
        return new_item

    def delete_ticker(self, command: str) -> bool:
        command = command.strip().lower()
        tickers = self.load()
        filtered = [item for item in tickers if item["command"] != command]

        if len(filtered) == len(tickers):
            return False

        self.save(filtered)
        return True