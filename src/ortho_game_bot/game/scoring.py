from dataclasses import dataclass

CORRECT_POINTS = 10
WRONG_POINTS = -2
STREAK_MILESTONES = {3: 2, 5: 3, 10: 5}


@dataclass(frozen=True, slots=True)
class ScoreResult:
    points: int
    streak_after: int
    bonus: int


def calculate_answer_score(*, is_correct: bool, streak_before: int) -> ScoreResult:
    """Начисляет +10, штрафует на 2 и выдаёт бонусы на сериях 3/5/10."""
    if not is_correct:
        return ScoreResult(points=WRONG_POINTS, streak_after=0, bonus=0)
    streak_after = max(0, streak_before) + 1
    bonus = STREAK_MILESTONES.get(streak_after, 0)
    return ScoreResult(
        points=CORRECT_POINTS + bonus,
        streak_after=streak_after,
        bonus=bonus,
    )

