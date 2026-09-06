"""Incremental storage for trial results."""

import json
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path("results/trials.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS trials (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL,
    config_name   TEXT NOT NULL,
    model         TEXT NOT NULL,
    task_id       TEXT NOT NULL,
    db_id         TEXT NOT NULL,
    trial_index   INTEGER NOT NULL,
    correct       INTEGER NOT NULL,
    reason        TEXT,
    query         TEXT,
    attempts      INTEGER,
    stopped_reason TEXT,
    calls_used    INTEGER,
    tokens_used   INTEGER,
    seconds_used  REAL,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_run ON trials(run_id, config_name, model);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_trial
    ON trials(run_id, config_name, model, task_id, trial_index);
"""


class TrialStore:
    def __init__(self, path: Path = DEFAULT_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path)
        self.con.executescript(SCHEMA)
        self.con.commit()

    def already_done(self, run_id, config_name, model, task_id, trial_index) -> bool:
        row = self.con.execute(
            "SELECT 1 FROM trials WHERE run_id=? AND config_name=? AND model=? "
            "AND task_id=? AND trial_index=?",
            (run_id, config_name, model, task_id, trial_index),
        ).fetchone()
        return row is not None

    def record(self, run_id, config_name, model, task, trial_index,
               verdict, result) -> None:
        self.con.execute(
            "INSERT OR IGNORE INTO trials "
            "(run_id, config_name, model, task_id, db_id, trial_index, "
            " correct, reason, query, attempts, stopped_reason, "
            " calls_used, tokens_used, seconds_used) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id, config_name, model, task["task_id"], task["db_id"],
                trial_index,
                1 if verdict.get("correct") else 0,
                verdict.get("reason"),
                result.query,
                result.attempts,
                result.stopped_reason,
                result.budget.get("calls_used"),
                result.budget.get("tokens_used"),
                result.budget.get("seconds_used"),
            ),
        )
        self.con.commit()

    def totals(self) -> dict:
        row = self.con.execute(
            "SELECT count(*), sum(correct), sum(tokens_used) FROM trials"
        ).fetchone()
        return {"trials": row[0], "correct": row[1] or 0, "tokens": row[2] or 0}

    def close(self):
        self.con.close()