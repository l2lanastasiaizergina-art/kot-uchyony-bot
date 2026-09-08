CREATE TABLE english_vocabulary_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    level_code TEXT NOT NULL,
    mode TEXT NOT NULL,
    is_review INTEGER NOT NULL DEFAULT 0 CHECK (is_review IN (0, 1)),
    question_ids_json TEXT NOT NULL,
    current_position INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    current_streak INTEGER NOT NULL DEFAULT 0,
    best_streak INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed')),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE UNIQUE INDEX idx_english_vocabulary_one_active
    ON english_vocabulary_sessions(user_id, level_code, mode, is_review)
    WHERE status = 'active';

CREATE INDEX idx_english_vocabulary_progress
    ON english_vocabulary_sessions(user_id, is_review, level_code, mode, status);

CREATE TABLE english_vocabulary_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES english_vocabulary_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    selected_option_id TEXT NOT NULL CHECK (selected_option_id IN ('A', 'B', 'C', 'D')),
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    points_awarded INTEGER NOT NULL,
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, question_id),
    UNIQUE(session_id, position)
);

CREATE INDEX idx_english_vocabulary_seen
    ON english_vocabulary_answers(user_id, question_id, answered_at DESC);

CREATE TABLE english_vocabulary_reviews (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    level_code TEXT NOT NULL,
    mode TEXT NOT NULL,
    stage INTEGER NOT NULL DEFAULT 0 CHECK (stage BETWEEN 0 AND 3),
    next_due_at TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, question_id)
);

CREATE INDEX idx_english_vocabulary_reviews_due
    ON english_vocabulary_reviews(user_id, active, next_due_at);
