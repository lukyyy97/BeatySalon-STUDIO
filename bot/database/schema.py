"""SQLite schema. Times are stored as 'HH:MM', dates as 'YYYY-MM-DD' (salon-local time)."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    tg_id        INTEGER PRIMARY KEY,
    full_name    TEXT NOT NULL DEFAULT '',
    username     TEXT,
    contact_name TEXT,
    phone        TEXT,
    is_blocked   INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS services (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    price        INTEGER NOT NULL CHECK (price >= 0),
    duration_min INTEGER NOT NULL CHECK (duration_min > 0),
    is_active    INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS masters (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS master_services (
    master_id  INTEGER NOT NULL REFERENCES masters(id)  ON DELETE CASCADE,
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    PRIMARY KEY (master_id, service_id)
);

-- Weekly template: no row for a weekday == day off. weekday: 0 = Monday ... 6 = Sunday.
CREATE TABLE IF NOT EXISTS work_schedule (
    master_id   INTEGER NOT NULL REFERENCES masters(id) ON DELETE CASCADE,
    weekday     INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    break_start TEXT,
    break_end   TEXT,
    PRIMARY KEY (master_id, weekday)
);

-- Closed day (start_time/end_time NULL) or closed time range for a master.
CREATE TABLE IF NOT EXISTS time_off (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id  INTEGER NOT NULL REFERENCES masters(id) ON DELETE CASCADE,
    date       TEXT NOT NULL,
    start_time TEXT,
    end_time   TEXT,
    reason     TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_time_off_master_date ON time_off(master_id, date);

CREATE TABLE IF NOT EXISTS appointments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_tg_id        INTEGER REFERENCES users(tg_id) ON DELETE SET NULL,
    service_id        INTEGER NOT NULL REFERENCES services(id),
    master_id         INTEGER NOT NULL REFERENCES masters(id),
    date              TEXT NOT NULL,
    start_time        TEXT NOT NULL,
    end_time          TEXT NOT NULL,
    client_name       TEXT NOT NULL,
    client_phone      TEXT NOT NULL DEFAULT '',
    price             INTEGER NOT NULL,
    duration_min      INTEGER NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
    created_by        TEXT NOT NULL DEFAULT 'client' CHECK (created_by IN ('client', 'admin')),
    cancelled_by      TEXT CHECK (cancelled_by IN ('client', 'admin')),
    reminder_24h_sent INTEGER NOT NULL DEFAULT 0,
    reminder_2h_sent  INTEGER NOT NULL DEFAULT 0,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    cancelled_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_appt_master_date ON appointments(master_id, date, status);
CREATE INDEX IF NOT EXISTS idx_appt_user ON appointments(user_tg_id, status, date);
-- Last line of defence against double booking: one active appointment per master/date/start.
CREATE UNIQUE INDEX IF NOT EXISTS uq_appt_active_slot
    ON appointments(master_id, date, start_time) WHERE status = 'active';
"""
