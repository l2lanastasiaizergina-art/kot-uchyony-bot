from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class InvalidInitDataError(ValueError):
    """Telegram Mini App initData не прошло проверку."""


@dataclass(frozen=True, slots=True)
class TelegramWebUser:
    id: int
    username: str | None
    display_name: str


def validate_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86_400,
) -> TelegramWebUser:
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", "")
    if not received_hash:
        raise InvalidInitDataError("Отсутствует подпись Telegram")

    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise InvalidInitDataError("Неверная подпись Telegram")

    try:
        auth_date = int(values["auth_date"])
        user_payload = json.loads(values["user"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidInitDataError("Некорректные данные Telegram") from exc
    if abs(time.time() - auth_date) > max_age_seconds:
        raise InvalidInitDataError("Сессия Telegram устарела")

    first_name = str(user_payload.get("first_name", "")).strip()
    last_name = str(user_payload.get("last_name", "")).strip()
    display_name = " ".join(part for part in (first_name, last_name) if part) or "Игрок"
    return TelegramWebUser(
        id=int(user_payload["id"]),
        username=user_payload.get("username"),
        display_name=display_name,
    )
