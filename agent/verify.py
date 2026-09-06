"""Deterministic verification of generated SQL against gold queries.

A result counts as correct only if executing the candidate produces the same
multiset of rows as the gold query. Row order is compared only when the gold
query specifies ORDER BY.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

DB_DIR = Path("data/spider/database")


@dataclass
class ExecutionResult:
    ok: bool
    rows: list | None = None
    error: str | None = None


def _connect(db_id: str) -> sqlite3.Connection:
    db_path = DB_DIR / db_id / f"{db_id}.sqlite"
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
    con.text_factory = lambda b: b.decode(errors="replace")
    return con


def execute(db_id: str, query: str) -> ExecutionResult:
    """Run a query read-only. Never raises; errors are returned."""
    try:
        con = _connect(db_id)
    except Exception as e:
        return ExecutionResult(ok=False, error=f"connection failed: {e}")

    try:
        rows = con.execute(query).fetchall()
        return ExecutionResult(ok=True, rows=rows)
    except Exception as e:
        return ExecutionResult(ok=False, error=f"{type(e).__name__}: {e}")
    finally:
        con.close()


def _normalize_value(v) -> str:
    """Render a cell as a comparable string.

    Spider databases store many numeric columns as TEXT, so a gold query's
    max(age) returns "9" while a candidate's max(CAST(age AS INTEGER))
    returns 9. These are the same answer and must compare equal. Numeric
    strings are therefore parsed and formatted the same way as numbers.
    """
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return f"{round(float(v), 6):g}"

    s = str(v).strip()
    try:
        return f"{round(float(s), 6):g}"
    except ValueError:
        return s


def _normalize_rows(rows, order_matters: bool):
    """Rows become sorted tuples; the row list is sorted unless order matters."""
    normalized = [
        tuple(sorted(_normalize_value(v) for v in row))
        for row in rows
    ]
    if order_matters:
        return normalized
    return sorted(normalized)


def results_match(gold_rows, candidate_rows, order_matters: bool) -> bool:
    if gold_rows is None or candidate_rows is None:
        return False
    if len(gold_rows) != len(candidate_rows):
        return False
    return (_normalize_rows(gold_rows, order_matters)
            == _normalize_rows(candidate_rows, order_matters))


def verify(db_id: str, gold_query: str, candidate_query: str) -> dict:
    """Return a verdict dict for one candidate query."""
    if not candidate_query or not candidate_query.strip():
        return {"correct": False, "reason": "empty query"}

    gold = execute(db_id, gold_query)
    if not gold.ok:
        return {"correct": False, "reason": f"gold failed: {gold.error}"}

    candidate = execute(db_id, candidate_query)
    if not candidate.ok:
        return {"correct": False, "reason": "candidate error",
                "error": candidate.error}

    # Guard against trivially-empty matches (see task selection).
    if len(gold.rows) == 0:
        return {"correct": False, "reason": "gold returned no rows"}

    order_matters = "order by" in gold_query.lower()
    correct = results_match(gold.rows, candidate.rows, order_matters)

    return {
        "correct": correct,
        "reason": "match" if correct else "result mismatch",
        "gold_row_count": len(gold.rows),
        "candidate_row_count": len(candidate.rows),
        "order_sensitive": order_matters,
    }