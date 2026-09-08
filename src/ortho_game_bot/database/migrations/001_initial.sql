CREATE TABLE users (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    display_name TEXT NOT NULL,
    grade INTEGER CHECK (grade BETWEEN 1 AND 11),
    total_score INTEGER NOT NULL DEFAULT 0,
    monthly_score INTEGER NOT NULL DEFAULT 0,
    monthly_period TEXT NOT NULL,
    games_played INTEGER NOT NULL DEFAULT 0,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    wrong_answers INTEGER NOT NULL DEFAULT 0,
    current_streak INTEGER NOT NULL DEFAULT 0,
    best_streak INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_grade_score ON users(grade, total_score DESC);
CREATE INDEX idx_users_total_score ON users(total_score DESC);

CREATE TABLE content_packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL,
    grade INTEGER NOT NULL CHECK (grade BETWEEN 1 AND 11),
    title TEXT NOT NULL,
    source_name TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    checksum TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(slug, version)
);

CREATE TABLE words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_id INTEGER NOT NULL REFERENCES content_packs(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    grade INTEGER NOT NULL CHECK (grade BETWEEN 1 AND 11),
    group_name TEXT NOT NULL,
    rule_text TEXT,
    word TEXT NOT NULL,
    normalized_answer TEXT NOT NULL,
    prompt_text TEXT,
    audio_file_id TEXT,
    orthograms_json TEXT NOT NULL DEFAULT '[]',
    distractors_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    difficulty INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pack_id, external_id)
);

CREATE INDEX idx_words_grade_active ON words(grade, is_active);
CREATE INDEX idx_words_group ON words(grade, group_name);

CREATE TABLE game_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('dictation', 'choice', 'quiz')),
    grade INTEGER NOT NULL CHECK (grade BETWEEN 1 AND 11),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'finished', 'abandoned')),
    questions_total INTEGER NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    score_delta INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    current_streak INTEGER NOT NULL DEFAULT 0,
    best_streak INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE INDEX idx_game_sessions_user_started ON game_sessions(user_id, started_at DESC);

CREATE TABLE game_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
    word_id INTEGER NOT NULL REFERENCES words(id),
    question_index INTEGER NOT NULL,
    prompt_snapshot TEXT,
    correct_answer_snapshot TEXT NOT NULL,
    user_answer TEXT,
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    points_awarded INTEGER NOT NULL,
    duration_ms INTEGER,
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, question_index)
);

CREATE TABLE score_events (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    delta_total INTEGER NOT NULL,
    delta_monthly INTEGER NOT NULL,
    period_key TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_score_events_user_created ON score_events(user_id, created_at DESC);

CREATE TABLE monthly_scores (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    period_key TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    games_played INTEGER NOT NULL DEFAULT 0,
    correct_answers INTEGER NOT NULL DEFAULT 0,
    wrong_answers INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, period_key)
);

CREATE INDEX idx_monthly_scores_period_score ON monthly_scores(period_key, score DESC);

CREATE TABLE quiz_events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    theme TEXT,
    grade_min INTEGER NOT NULL CHECK (grade_min BETWEEN 1 AND 11),
    grade_max INTEGER NOT NULL CHECK (grade_max BETWEEN 1 AND 11),
    starts_at TEXT NOT NULL,
    ends_at TEXT NOT NULL,
    questions_count INTEGER NOT NULL,
    time_limit_seconds INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'scheduled', 'active', 'closed', 'cancelled')),
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (grade_min <= grade_max),
    CHECK (starts_at < ends_at)
);

CREATE TABLE quiz_questions (
    quiz_id TEXT NOT NULL REFERENCES quiz_events(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    word_id INTEGER NOT NULL REFERENCES words(id),
    points INTEGER NOT NULL DEFAULT 10,
    PRIMARY KEY(quiz_id, position),
    UNIQUE(quiz_id, word_id)
);

CREATE TABLE quiz_attempts (
    id TEXT PRIMARY KEY,
    quiz_id TEXT NOT NULL REFERENCES quiz_events(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'finished', 'expired')),
    score INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    duration_ms INTEGER,
    UNIQUE(quiz_id, user_id)
);

CREATE INDEX idx_quiz_attempts_leaderboard
    ON quiz_attempts(quiz_id, score DESC, duration_ms ASC);

CREATE TABLE quiz_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id TEXT NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    word_id INTEGER NOT NULL REFERENCES words(id),
    user_answer TEXT,
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    points_awarded INTEGER NOT NULL,
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(attempt_id, position)
);

CREATE TABLE broadcasts (
    id TEXT PRIMARY KEY,
    created_by INTEGER NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'scheduled', 'sending', 'sent', 'failed')),
    scheduled_at TEXT,
    sent_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE TABLE user_entitlements (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    feature_code TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'expired', 'revoked')),
    source TEXT NOT NULL,
    starts_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(user_id, feature_code)
);
