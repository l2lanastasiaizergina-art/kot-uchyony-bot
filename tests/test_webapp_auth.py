import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from ortho_game_bot.webapp.auth import InvalidInitDataError, validate_init_data

BOT_TOKEN = "123456:TEST_TOKEN"


def _signed_init_data() -> str:
    values = {
        "auth_date": str(int(time.time())),
        "query_id": "AAEAAAE",
        "user": json.dumps(
            {
                "id": 42,
                "first_name": "Маша",
                "last_name": "Иванова",
                "username": "masha",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_validate_init_data_returns_verified_user() -> None:
    user = validate_init_data(_signed_init_data(), BOT_TOKEN)
    assert user.id == 42
    assert user.username == "masha"
    assert user.display_name == "Маша Иванова"


def test_validate_init_data_rejects_tampering() -> None:
    tampered = _signed_init_data().replace("masha", "hacker")
    with pytest.raises(InvalidInitDataError):
        validate_init_data(tampered, BOT_TOKEN)
