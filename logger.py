from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from typing import Any

from config import settings

settings.log_file.parent.mkdir(parents=True, exist_ok=True)


class JsonExtraFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base_message = super().format(record)

        payload = getattr(record, "payload", None)
        if payload is None:
            return base_message

        try:
            payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        except Exception:
            payload_text = str(payload)

        return f"{base_message} | payload={payload_text}"


def _safe_payload(**kwargs: Any) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in kwargs.items():
        try:
            json.dumps(value)
            safe[key] = value
        except Exception:
            safe[key] = str(value)
    return safe


def build_logger() -> logging.Logger:
    logger = logging.getLogger("multi_ticker_bot")
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    formatter = JsonExtraFormatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        settings.log_file,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


logger = build_logger()


def log_debug(message: str, **kwargs: Any) -> None:
    logger.debug(message, extra={"payload": _safe_payload(**kwargs)})


def log_info(message: str, **kwargs: Any) -> None:
    logger.info(message, extra={"payload": _safe_payload(**kwargs)})


def log_warning(message: str, **kwargs: Any) -> None:
    logger.warning(message, extra={"payload": _safe_payload(**kwargs)})


def log_error(message: str, **kwargs: Any) -> None:
    logger.error(message, extra={"payload": _safe_payload(**kwargs)})


def log_exception(message: str, **kwargs: Any) -> None:
    logger.exception(message, extra={"payload": _safe_payload(**kwargs)})


def log_command_start(
    command: str,
    chat_id: int | None = None,
    user_id: int | None = None,
    thread_id: int | None = None,
    symbol: str | None = None,
    asset_type: str | None = None,
    text: str | None = None,
) -> None:
    log_info(
        "COMMAND_START",
        command=command,
        chat_id=chat_id,
        user_id=user_id,
        thread_id=thread_id,
        symbol=symbol,
        asset_type=asset_type,
        text=text,
    )


def log_command_end(
    command: str,
    status: str,
    duration_ms: float | int | None = None,
    chat_id: int | None = None,
    user_id: int | None = None,
    thread_id: int | None = None,
    symbol: str | None = None,
    asset_type: str | None = None,
    price: float | None = None,
    currency: str | None = None,
    source_name: str | None = None,
) -> None:
    log_info(
        "COMMAND_END",
        command=command,
        status=status,
        duration_ms=duration_ms,
        chat_id=chat_id,
        user_id=user_id,
        thread_id=thread_id,
        symbol=symbol,
        asset_type=asset_type,
        price=price,
        currency=currency,
        source_name=source_name,
    )


def log_button_click(
    action: str,
    chat_id: int | None = None,
    user_id: int | None = None,
    thread_id: int | None = None,
    callback_data: str | None = None,
    symbol: str | None = None,
) -> None:
    log_info(
        "BUTTON_CLICK",
        action=action,
        chat_id=chat_id,
        user_id=user_id,
        thread_id=thread_id,
        callback_data=callback_data,
        symbol=symbol,
    )


def log_flow_step(
    flow: str,
    step: str,
    chat_id: int | None = None,
    user_id: int | None = None,
    thread_id: int | None = None,
    symbol: str | None = None,
    value: Any | None = None,
) -> None:
    log_info(
        "FLOW_STEP",
        flow=flow,
        step=step,
        chat_id=chat_id,
        user_id=user_id,
        thread_id=thread_id,
        symbol=symbol,
        value=value,
    )


def log_api_request(
    provider: str,
    endpoint: str,
    method: str = "GET",
    symbol: str | None = None,
    params: dict[str, Any] | None = None,
) -> None:
    log_info(
        "API_REQUEST",
        provider=provider,
        endpoint=endpoint,
        method=method,
        symbol=symbol,
        params=params or {},
    )


def log_api_response(
    provider: str,
    endpoint: str,
    status_code: int | None = None,
    symbol: str | None = None,
    ok: bool = True,
    summary: Any | None = None,
) -> None:
    log_info(
        "API_RESPONSE",
        provider=provider,
        endpoint=endpoint,
        status_code=status_code,
        symbol=symbol,
        ok=ok,
        summary=summary,
    )


def log_data_flow(
    action: str,
    store: str,
    status: str,
    record_id: str | None = None,
    symbol: str | None = None,
    chat_id: int | None = None,
    user_id: int | None = None,
    detail: Any | None = None,
) -> None:
    log_info(
        "DATA_FLOW",
        action=action,
        store=store,
        status=status,
        record_id=record_id,
        symbol=symbol,
        chat_id=chat_id,
        user_id=user_id,
        detail=detail,
    )


def log_state_change(
    name: str,
    old_value: Any | None = None,
    new_value: Any | None = None,
    chat_id: int | None = None,
    user_id: int | None = None,
) -> None:
    log_info(
        "STATE_CHANGE",
        name=name,
        old_value=old_value,
        new_value=new_value,
        chat_id=chat_id,
        user_id=user_id,
    )