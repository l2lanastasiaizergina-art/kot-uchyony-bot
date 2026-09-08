CREATE TABLE leader_library_progress (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    book_id TEXT NOT NULL,
    current_step INTEGER NOT NULL DEFAULT 0 CHECK (current_step BETWEEN 0 AND 8),
    first_attempt_correct INTEGER NOT NULL DEFAULT 0 CHECK (first_attempt_correct BETWEEN 0 AND 8),
    answers_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed')),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    review_24h_answered_at TEXT,
    review_7d_answered_at TEXT,
    PRIMARY KEY(user_id, book_id)
);

CREATE INDEX idx_leader_library_progress_user_status
    ON leader_library_progress(user_id, status, updated_at DESC);

CREATE TABLE leader_library_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    book_id TEXT NOT NULL,
    step_index INTEGER NOT NULL CHECK (step_index BETWEEN 0 AND 7),
    attempt_number INTEGER NOT NULL CHECK (attempt_number BETWEEN 1 AND 2),
    selected_option INTEGER NOT NULL CHECK (selected_option BETWEEN 0 AND 3),
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    points_awarded INTEGER NOT NULL DEFAULT 0,
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_id, step_index, attempt_number)
);

CREATE INDEX idx_leader_library_answers_user_book
    ON leader_library_answers(user_id, book_id, step_index);

CREATE TABLE leader_library_review_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    book_id TEXT NOT NULL,
    review_kind TEXT NOT NULL CHECK (review_kind IN ('24h', '7d')),
    selected_option INTEGER NOT NULL CHECK (selected_option BETWEEN 0 AND 3),
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, book_id, review_kind)
);
