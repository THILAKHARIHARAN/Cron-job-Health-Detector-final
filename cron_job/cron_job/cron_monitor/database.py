import sqlite3
from contextlib import contextmanager
from pathlib import Path


DB_PATH = Path(__file__).with_name("monitor.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS project_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT DEFAULT '',
    owner TEXT DEFAULT '',
    description TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS cron_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    category TEXT NOT NULL,
    assignee TEXT DEFAULT '',
    schedule TEXT DEFAULT '',
    cmd TEXT DEFAULT '',
    status TEXT DEFAULT 'Healthy',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS job_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    exit_code INTEGER NOT NULL,
    stdout TEXT DEFAULT '',
    stderr TEXT DEFAULT '',
    anomaly_score REAL DEFAULT 0,
    anomaly_reason TEXT DEFAULT '',
    done TEXT DEFAULT '',
    person TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_job_runs_job_name ON job_runs(job_name);
CREATE INDEX IF NOT EXISTS idx_job_runs_started_at ON job_runs(started_at);
"""


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Ensure schema upgrades are applied to existing DB
        try:
            conn.execute("ALTER TABLE job_runs ADD COLUMN done TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE job_runs ADD COLUMN person TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        # Seed default project settings if not present
        try:
            conn.execute(
                "INSERT OR IGNORE INTO project_settings (id, name, owner, description) VALUES (1, 'Cron-Job Health Dashboard', 'System Operator', 'Monitor silent cron failures with clear, honest insights.')"
            )
        except sqlite3.OperationalError:
            pass


def row_to_dict(row):
    return dict(row) if row is not None else None
