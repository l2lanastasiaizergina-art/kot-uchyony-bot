ALTER TABLE users ADD COLUMN daily_streak INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN longest_daily_streak INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN last_qualifying_date TEXT;
ALTER TABLE users ADD COLUMN timezone_name TEXT NOT NULL DEFAULT 'Europe/Moscow';
ALTER TABLE users ADD COLUMN selected_cosmetic_id TEXT;

CREATE TABLE daily_activity (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    activity_date TEXT NOT NULL,
    answers_attempted INTEGER NOT NULL DEFAULT 0,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    raw_points INTEGER NOT NULL DEFAULT 0,
    bonus_points INTEGER NOT NULL DEFAULT 0,
    boosted_rounds INTEGER NOT NULL DEFAULT 0,
    streak_qualified INTEGER NOT NULL DEFAULT 0 CHECK (streak_qualified IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, activity_date)
);

CREATE INDEX idx_daily_activity_date ON daily_activity(activity_date);

CREATE TABLE review_queue (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    word_id INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'learning'
        CHECK (status IN ('learning', 'review', 'mastered')),
    repetitions INTEGER NOT NULL DEFAULT 0,
    lapses INTEGER NOT NULL DEFAULT 0,
    interval_days INTEGER NOT NULL DEFAULT 1,
    next_review_at TEXT NOT NULL,
    last_answer_correct INTEGER CHECK (last_answer_correct IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, word_id)
);

CREATE INDEX idx_review_queue_due ON review_queue(user_id, next_review_at, status);

CREATE TABLE achievement_definitions (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    icon TEXT NOT NULL,
    category TEXT NOT NULL,
    threshold INTEGER,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE user_achievements (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    achievement_code TEXT NOT NULL REFERENCES achievement_definitions(code),
    progress INTEGER NOT NULL DEFAULT 0,
    unlocked_at TEXT,
    notified_at TEXT,
    PRIMARY KEY(user_id, achievement_code)
);

CREATE TABLE seasons (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'scheduled', 'active', 'closed')),
    CHECK (starts_at < ends_at)
);

CREATE TABLE season_scores (
    season_id TEXT NOT NULL REFERENCES seasons(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    league_code TEXT NOT NULL DEFAULT 'kitten',
    league_points INTEGER NOT NULL DEFAULT 0,
    promoted_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(season_id, user_id)
);

CREATE INDEX idx_season_leaderboard
    ON season_scores(season_id, league_code, league_points DESC);

CREATE TABLE cosmetics (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('cat', 'hat', 'glasses', 'badge', 'room')),
    asset_key TEXT NOT NULL UNIQUE,
    unlock_type TEXT NOT NULL CHECK (unlock_type IN ('level', 'achievement', 'event', 'premium')),
    unlock_value TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
);

CREATE TABLE user_cosmetics (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    cosmetic_id TEXT NOT NULL REFERENCES cosmetics(id),
    acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_equipped INTEGER NOT NULL DEFAULT 0 CHECK (is_equipped IN (0, 1)),
    PRIMARY KEY(user_id, cosmetic_id)
);

CREATE TABLE learning_groups (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    invite_code TEXT NOT NULL UNIQUE,
    grade INTEGER CHECK (grade BETWEEN 1 AND 11),
    owner_user_id INTEGER NOT NULL REFERENCES users(telegram_id),
    organization_name TEXT,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE group_members (
    group_id TEXT NOT NULL REFERENCES learning_groups(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'teacher', 'admin')),
    public_alias TEXT NOT NULL,
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(group_id, user_id)
);

CREATE TABLE notification_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
    daily_reminder_enabled INTEGER NOT NULL DEFAULT 0 CHECK (daily_reminder_enabled IN (0, 1)),
    quiz_reminder_enabled INTEGER NOT NULL DEFAULT 1 CHECK (quiz_reminder_enabled IN (0, 1)),
    quiet_hours_start TEXT,
    quiet_hours_end TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO achievement_definitions(code, title, description, icon, category, threshold) VALUES
    ('first_round', 'Первая охота', 'Завершить первый раунд', '🐾', 'games', 1),
    ('streak_3', 'Разогрел лапы', 'Заниматься 3 дня подряд', '🔥', 'streak', 3),
    ('streak_7', 'Неделя ума', 'Заниматься 7 дней подряд', '⚡', 'streak', 7),
    ('streak_30', 'Железная привычка', 'Заниматься 30 дней подряд', '🏅', 'streak', 30),
    ('perfect_round', 'Без единой ошибки', 'Ответить правильно на весь раунд', '💎', 'accuracy', 10),
    ('fix_100', 'Охотник за ошибками', 'Исправить 100 собственных ошибок', '🎯', 'review', 100);

