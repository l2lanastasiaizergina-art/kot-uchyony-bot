from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_admin_ids(raw: str) -> frozenset[int]:
    if not raw.strip():
        return frozenset()
    try:
        return frozenset(int(value.strip()) for value in raw.split(",") if value.strip())
    except ValueError as exc:
        raise ValueError("ADMIN_IDS должен содержать Telegram ID через запятую") from exc


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {"1", "true", "yes", "on", "да"}


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    database_path: Path
    content_path: Path
    leader_library_path: Path
    art_culture_path: Path
    log_level: str = "INFO"
    round_size: int = 10
    accept_e_for_yo: bool = False
    webapp_url: str | None = None
    port: int = 8080
    webapp_demo: bool = False

    @classmethod
    def from_env(cls, *, require_token: bool = True) -> Settings:
        token = os.getenv("BOT_TOKEN", "").strip()
        if require_token and not token:
            raise RuntimeError("Не задан BOT_TOKEN. Скопируйте .env.example в .env.")

        round_size = int(os.getenv("ROUND_SIZE", "10"))
        if not 5 <= round_size <= 30:
            raise ValueError("ROUND_SIZE должен быть от 5 до 30")

        return cls(
            bot_token=token,
            admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
            database_path=Path(os.getenv("DATABASE_PATH", "./var/orthogame.sqlite3")),
            content_path=Path(os.getenv("CONTENT_PATH", "./data/words")),
            leader_library_path=Path(
                os.getenv(
                    "LEADER_LIBRARY_PATH",
                    "./data/leader_library/content.ru.json",
                )
            ),
            art_culture_path=Path(
                os.getenv(
                    "ART_CULTURE_PATH",
                    "./data/art_culture/content.ru-en-kz.json.gz",
                )
            ),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            round_size=round_size,
            accept_e_for_yo=_parse_bool(os.getenv("ACCEPT_E_FOR_YO", "false")),
            webapp_url=os.getenv("WEBAPP_URL", "").strip() or None,
            port=int(os.getenv("PORT", "8080")),
            webapp_demo=_parse_bool(os.getenv("WEBAPP_DEMO", "false")),
        )
