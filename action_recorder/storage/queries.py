"""SQL queries as constants for ActionRecorder Pro."""

SCHEMA_VERSION = 1

CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    region_left     INTEGER NOT NULL DEFAULT 0,
    region_top      INTEGER NOT NULL DEFAULT 0,
    region_width    INTEGER NOT NULL DEFAULT 0,
    region_height   INTEGER NOT NULL DEFAULT 0,
    monitor_index   INTEGER NOT NULL DEFAULT 0,
    dpi_scale       REAL NOT NULL DEFAULT 1.0,
    duration_ms     INTEGER NOT NULL DEFAULT 0,
    action_count    INTEGER NOT NULL DEFAULT 0,
    is_template     INTEGER NOT NULL DEFAULT 0,
    tags            TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    default_speed   REAL NOT NULL DEFAULT 1.0,
    loop_count      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    sequence_order  INTEGER NOT NULL,
    action_type     TEXT NOT NULL,
    timestamp_ns    INTEGER NOT NULL,
    abs_x           INTEGER,
    abs_y           INTEGER,
    region_x        INTEGER,
    region_y        INTEGER,
    button          TEXT,
    scroll_dx       INTEGER DEFAULT 0,
    scroll_dy       INTEGER DEFAULT 0,
    key_name        TEXT,
    key_char        TEXT,
    modifiers       TEXT DEFAULT '[]',
    screenshot_path TEXT,
    metadata_json   TEXT DEFAULT '{}',
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_actions_session_order
    ON actions(session_id, sequence_order);

CREATE INDEX IF NOT EXISTS idx_actions_session_time
    ON actions(session_id, timestamp_ns);

CREATE TABLE IF NOT EXISTS patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    symbol_sequence TEXT NOT NULL,
    action_types    TEXT NOT NULL DEFAULT '[]',
    avg_duration_ms INTEGER NOT NULL DEFAULT 0,
    frequency       INTEGER NOT NULL DEFAULT 1,
    confidence      REAL NOT NULL DEFAULT 0.5,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    is_active       INTEGER NOT NULL DEFAULT 1,
    user_confirmed  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prediction_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id      INTEGER NOT NULL,
    predicted_at    TEXT NOT NULL DEFAULT (datetime('now')),
    was_accepted    INTEGER,
    match_score     REAL NOT NULL,
    context_json    TEXT DEFAULT '{}',
    FOREIGN KEY (pattern_id) REFERENCES patterns(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

DEFAULT_SETTINGS = {
    "hotkey_record": "F9",
    "hotkey_pause": "F10",
    "hotkey_stop": "F11",
    "hotkey_replay": "F5",
    "screenshot_interval_ms": "2000",
    "mouse_throttle_px": "3",
    "assistant_enabled": "1",
    "assistant_confidence_threshold": "0.7",
    "replay_speed": "1.0",
    "mouse_move_recording": "1",
}

# Session queries
INSERT_SESSION = """
INSERT INTO sessions (name, region_left, region_top, region_width, region_height,
                      monitor_index, dpi_scale, duration_ms, action_count,
                      is_template, tags, notes, default_speed, loop_count)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_SESSION_BY_ID = "SELECT * FROM sessions WHERE id = ?"
SELECT_ALL_SESSIONS = "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?"
UPDATE_SESSION = """
UPDATE sessions SET name=?, updated_at=datetime('now'), duration_ms=?,
    action_count=?, is_template=?, tags=?, notes=?, default_speed=?, loop_count=?
WHERE id=?
"""
DELETE_SESSION = "DELETE FROM sessions WHERE id = ?"
SEARCH_SESSIONS = "SELECT * FROM sessions WHERE name LIKE ? OR tags LIKE ? ORDER BY created_at DESC"

# Action queries
INSERT_ACTION = """
INSERT INTO actions (session_id, sequence_order, action_type, timestamp_ns,
                     abs_x, abs_y, region_x, region_y, button, scroll_dx, scroll_dy,
                     key_name, key_char, modifiers, screenshot_path, metadata_json)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_ACTIONS_BY_SESSION = """
SELECT * FROM actions WHERE session_id = ? ORDER BY sequence_order
"""

SELECT_ACTIONS_TIME_RANGE = """
SELECT * FROM actions WHERE session_id = ? AND timestamp_ns BETWEEN ? AND ?
ORDER BY sequence_order
"""

# Pattern queries
INSERT_PATTERN = """
INSERT INTO patterns (name, description, symbol_sequence, action_types,
                      avg_duration_ms, frequency, confidence, is_active, user_confirmed)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_ALL_PATTERNS = "SELECT * FROM patterns WHERE is_active = 1 ORDER BY confidence DESC"
SELECT_ALL_PATTERNS_INCLUDE_INACTIVE = "SELECT * FROM patterns ORDER BY confidence DESC"

UPDATE_PATTERN_CONFIDENCE = """
UPDATE patterns SET confidence = ?, frequency = ?, updated_at = datetime('now')
WHERE id = ?
"""

DELETE_PATTERN = "DELETE FROM patterns WHERE id = ?"

# Prediction log queries
INSERT_PREDICTION_LOG = """
INSERT INTO prediction_log (pattern_id, was_accepted, match_score, context_json)
VALUES (?, ?, ?, ?)
"""

SELECT_PREDICTION_LOG = """
SELECT pl.*, p.name as pattern_name FROM prediction_log pl
JOIN patterns p ON pl.pattern_id = p.id
ORDER BY pl.predicted_at DESC LIMIT ?
"""

# Settings queries
GET_SETTING = "SELECT value FROM settings WHERE key = ?"
SET_SETTING = """
INSERT OR REPLACE INTO settings (key, value, updated_at)
VALUES (?, ?, datetime('now'))
"""
GET_ALL_SETTINGS = "SELECT key, value FROM settings"
