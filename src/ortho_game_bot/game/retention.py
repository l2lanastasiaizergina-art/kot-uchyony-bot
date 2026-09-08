from __future__ import annotations

from dataclasses import dataclass

MAX_BOOSTED_ROUNDS_PER_DAY = 3


@dataclass(frozen=True, slots=True)
class DailyReward:
    raw_points: int
    multiplier_percent: int
    bonus_points: int
    awarded_points: int
    boosted: bool


@dataclass(frozen=True, slots=True)
class League:
    code: str
    title: str
    minimum_points: int


LEAGUES = (
    League("kitten", "Котёнок", 0),
    League("tracker", "Следопыт", 500),
    League("expert", "Знаток", 1_500),
    League("professor", "Профессор", 3_500),
    League("sage", "Мудрец", 7_000),
    League("legend", "Легенда", 12_000),
)


def daily_multiplier_percent(streak_days: int) -> int:
    """Множитель регулярности: ×2 достигается на седьмой день."""
    if streak_days >= 7:
        return 200
    if streak_days >= 5:
        return 150
    if streak_days >= 3:
        return 125
    if streak_days >= 2:
        return 110
    return 100


def calculate_daily_reward(
    *, raw_points: int, streak_days: int, boosted_rounds_used: int
) -> DailyReward:
    """Умножает только положительные баллы первых трёх раундов за день."""
    eligible = raw_points > 0 and boosted_rounds_used < MAX_BOOSTED_ROUNDS_PER_DAY
    multiplier = daily_multiplier_percent(streak_days) if eligible else 100
    awarded = (raw_points * multiplier + 50) // 100 if raw_points > 0 else raw_points
    return DailyReward(
        raw_points=raw_points,
        multiplier_percent=multiplier,
        bonus_points=awarded - raw_points,
        awarded_points=awarded,
        boosted=eligible and multiplier > 100,
    )


def qualifies_for_daily_streak(*, answers_attempted: int) -> bool:
    """Открытие приложения не считается: нужно закончить минимум один раунд."""
    return answers_attempted >= 10


def league_for_score(points: int) -> League:
    score = max(0, points)
    return next(league for league in reversed(LEAGUES) if score >= league.minimum_points)

