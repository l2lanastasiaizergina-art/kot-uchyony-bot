from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

from ortho_game_bot.utils.rate_limit import SlidingWindowLimiter


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, *, limit: int = 8, window_seconds: float = 2.0) -> None:
        self.limiter = SlidingWindowLimiter(limit=limit, window_seconds=window_seconds)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if user is None or self.limiter.allow(user.id):
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            await event.answer("Слишком быстро — дай Коту секунду 🐾")
        return None
