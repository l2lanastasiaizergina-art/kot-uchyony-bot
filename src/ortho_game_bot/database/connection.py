from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from importlib import resources
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


class Database:
    """Асинхронный фасад над SQLite без глобального соединения.

    Каждая операция открывает короткоживущее соединение. Синхронная работа
    sqlite3 выполняется через asyncio.to_thread и не блокирует event loop бота.
    """

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    async def migrate(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._migrate_sync)

    def _migrate_sync(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            migration_root = resources.files("ortho_game_bot.database.migrations")
            for migration in sorted(migration_root.iterdir(), key=lambda item: item.name):
                if migration.suffix != ".sql":
                    continue
                exists = connection.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = ?", (migration.name,)
                ).fetchone()
                if exists:
                    continue
                connection.executescript(migration.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)", (migration.name,)
                )

    async def read_one(self, sql: str, parameters: Sequence[Any] = ()) -> sqlite3.Row | None:
        return await asyncio.to_thread(self._read_one_sync, sql, parameters)

    def _read_one_sync(self, sql: str, parameters: Sequence[Any]) -> sqlite3.Row | None:
        with closing(self._connect()) as connection:
            return connection.execute(sql, parameters).fetchone()

    async def read_all(self, sql: str, parameters: Sequence[Any] = ()) -> list[sqlite3.Row]:
        return await asyncio.to_thread(self._read_all_sync, sql, parameters)

    def _read_all_sync(self, sql: str, parameters: Sequence[Any]) -> list[sqlite3.Row]:
        with closing(self._connect()) as connection:
            return list(connection.execute(sql, parameters).fetchall())

    async def write(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        return await asyncio.to_thread(self._write_sync, operation)

    def _write_sync(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                result = operation(connection)
                connection.commit()
                return result
            except Exception:
                connection.rollback()
                raise
