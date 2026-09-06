"""Tools available to the agent."""

import sqlite3
from pathlib import Path

DB_DIR = Path("data/spider/database")
MAX_PREVIEW_ROWS = 5
MAX_RESULT_CHARS = 2000


def get_schema(db_id: str, include_samples: bool = True) -> str:
    """Return CREATE TABLE statements, optionally with sample rows."""
    db_path = DB_DIR / db_id / f"{db_id}.sqlite"
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode(errors="replace")

    parts = []
    tables = con.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'"
    ).fetchall()

    for name, ddl in tables:
        parts.append(ddl.strip() if ddl else f"-- table {name}")
        if include_samples:
            try:
                rows = con.execute(
                    f'SELECT * FROM "{name}" LIMIT 2'
                ).fetchall()
                if rows:
                    parts.append(f"-- sample rows: {rows}")
            except Exception:
                pass

    con.close()
    return "\n\n".join(parts)


def run_query(db_id: str, query: str) -> str:
    """Execute a query read-only and return a truncated text result."""
    db_path = DB_DIR / db_id / f"{db_id}.sqlite"
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        con.text_factory = lambda b: b.decode(errors="replace")
        rows = con.execute(query).fetchall()
        con.close()
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}"

    if not rows:
        return "OK: query returned 0 rows"

    preview = rows[:MAX_PREVIEW_ROWS]
    text = f"OK: {len(rows)} rows. First {len(preview)}:\n"
    text += "\n".join(str(r) for r in preview)
    return text[:MAX_RESULT_CHARS]