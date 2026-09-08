CREATE TABLE ai_course_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(telegram_id) ON DELETE CASCADE,
    age_code TEXT NOT NULL CHECK (age_code IN ('A1', 'A2', 'A3', 'A4')),
    track_code TEXT CHECK (track_code IS NULL OR track_code IN ('STUDY', 'WORK', 'CREATE')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ai_diagnostic_answers (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    age_code TEXT NOT NULL CHECK (age_code IN ('A1', 'A2', 'A3', 'A4')),
    task_id TEXT NOT NULL,
    competency_id TEXT NOT NULL,
    selected_option INTEGER NOT NULL CHECK (selected_option BETWEEN 0 AND 3),
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 3),
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(user_id, age_code, task_id)
);

CREATE INDEX idx_ai_diagnostic_user_age
    ON ai_diagnostic_answers(user_id, age_code, answered_at);

CREATE TABLE ai_mission_progress (
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    mission_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed')),
    attempts_count INTEGER NOT NULL DEFAULT 0 CHECK (attempts_count BETWEEN 0 AND 2),
    check_completed INTEGER NOT NULL DEFAULT 0 CHECK (check_completed IN (0, 1)),
    first_attempt_correct INTEGER NOT NULL DEFAULT 0 CHECK (first_attempt_correct IN (0, 1)),
    evidence_text TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    PRIMARY KEY(user_id, mission_id)
);

CREATE INDEX idx_ai_mission_progress_user_status
    ON ai_mission_progress(user_id, status, updated_at DESC);

CREATE TABLE ai_mission_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(telegram_id) ON DELETE CASCADE,
    mission_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL CHECK (attempt_number BETWEEN 1 AND 2),
    selected_option INTEGER NOT NULL CHECK (selected_option BETWEEN 0 AND 3),
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, mission_id, attempt_number)
);

CREATE INDEX idx_ai_mission_answers_user_mission
    ON ai_mission_answers(user_id, mission_id);
