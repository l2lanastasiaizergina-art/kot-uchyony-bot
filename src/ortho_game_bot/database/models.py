from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class User:
    telegram_id: int
    username: str | None
    display_name: str
    grade: int | None
    total_score: int
    monthly_score: int
    monthly_period: str
    games_played: int
    correct_answers: int
    wrong_answers: int
    current_streak: int
    best_streak: int
    daily_streak: int
    longest_daily_streak: int
    last_qualifying_date: str | None
    timezone_name: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class LeaderboardEntry:
    position: int
    telegram_id: int
    username: str | None
    display_name: str
    grade: int | None
    score: int


@dataclass(frozen=True, slots=True)
class ScoreApplication:
    applied: bool
    total_score: int
    monthly_score: int


@dataclass(frozen=True, slots=True)
class GameWord:
    id: int
    external_id: str
    grade: int
    group_name: str
    rule_text: str | None
    answer: str
    orthograms: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ChoiceQuestion:
    session_id: str
    position: int
    total: int
    word_id: int
    options: tuple[str, ...]
    group_name: str
    rule_text: str | None


@dataclass(frozen=True, slots=True)
class AnswerOutcome:
    session_id: str
    position: int
    total: int
    selected_answer: str
    correct_answer: str
    is_correct: bool
    points: int
    streak_after: int
    score_so_far: int
    correct_count: int
    wrong_count: int
    finished: bool


@dataclass(frozen=True, slots=True)
class RoundSnapshot:
    session_id: str
    user_id: int
    questions_total: int
    raw_score: int
    correct_count: int
    wrong_count: int
    best_streak: int
    completion_applied: bool


@dataclass(frozen=True, slots=True)
class RoundCompletion:
    applied: bool
    daily_streak: int
    multiplier_percent: int
    bonus_points: int
    awarded_points: int
    total_score: int
    monthly_score: int
    league_title: str
