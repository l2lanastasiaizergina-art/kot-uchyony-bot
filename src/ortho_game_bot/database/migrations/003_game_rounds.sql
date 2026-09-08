CREATE TABLE game_session_questions (
    session_id TEXT NOT NULL REFERENCES game_sessions(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    word_id INTEGER NOT NULL REFERENCES words(id),
    options_json TEXT NOT NULL,
    PRIMARY KEY(session_id, position),
    UNIQUE(session_id, word_id)
);

CREATE INDEX idx_game_session_questions_word
    ON game_session_questions(word_id);

ALTER TABLE game_sessions ADD COLUMN completion_applied INTEGER NOT NULL DEFAULT 0
    CHECK (completion_applied IN (0, 1));

