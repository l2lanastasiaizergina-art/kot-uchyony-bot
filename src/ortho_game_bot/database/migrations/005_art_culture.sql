CREATE TABLE art_culture_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    module_id TEXT NOT NULL,
    age_mode TEXT NOT NULL CHECK (age_mode IN ('child', 'teen', 'adult')),
    language TEXT NOT NULL CHECK (language IN ('ru', 'en', 'kz')),
    question_ids_json TEXT NOT NULL,
    current_position INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    foundation_correct INTEGER NOT NULL DEFAULT 0,
    foundation_total INTEGER NOT NULL DEFAULT 0,
    visual_correct INTEGER NOT NULL DEFAULT 0,
    visual_total INTEGER NOT NULL DEFAULT 0,
    analysis_correct INTEGER NOT NULL DEFAULT 0,
    analysis_total INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed')),
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE UNIQUE INDEX idx_art_culture_one_active_session
    ON art_culture_sessions(user_id, module_id, age_mode)
    WHERE status = 'active';

CREATE INDEX idx_art_culture_user_mode_status
    ON art_culture_sessions(user_id, age_mode, status, module_id, updated_at DESC);

CREATE TABLE art_culture_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES art_culture_sessions(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    question_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    selected_option_id TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('1_FOUNDATION', '2_VISUAL', '3_ANALYSIS')),
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    points_awarded INTEGER NOT NULL DEFAULT 0,
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, question_id),
    UNIQUE(session_id, position)
);

CREATE INDEX idx_art_culture_answers_user_question
    ON art_culture_answers(user_id, question_id, answered_at DESC);
