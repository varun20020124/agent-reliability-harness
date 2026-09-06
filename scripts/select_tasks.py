# scripts/select_tasks.py
"""Select a fixed, reproducible subset of Spider dev tasks.

Usage: python scripts/select_tasks.py
"""

import json
import random
import sqlite3
from collections import defaultdict
from pathlib import Path

SEED = 20260906
N_TASKS = 40
EXCLUDE_DBS = {"wta_1"}  # 105MB; slow queries confound wall-clock budgets

DEV_PATH = Path("data/spider/dev.jsonl")
DB_DIR = Path("data/spider/database")
OUT_PATH = Path("data/tasks.jsonl")


def gold_returns_rows(db_id: str, query: str) -> bool:
    """Does the gold query execute and return a non-empty result?"""
    db_path = DB_DIR / db_id / f"{db_id}.sqlite"
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.text_factory = lambda b: b.decode(errors="replace")
        rows = con.execute(query).fetchall()
        con.close()
        return len(rows) > 0
    except Exception:
        return False


def main():
    rng = random.Random(SEED)
    examples = [json.loads(line) for line in DEV_PATH.open()]

    by_db = defaultdict(list)
    for ex in examples:
        if ex["db_id"] in EXCLUDE_DBS:
            continue
        by_db[ex["db_id"]].append(ex)

    # Even spread across databases so results aren't dominated by one schema.
    db_ids = sorted(by_db)
    per_db = N_TASKS // len(db_ids)
    remainder = N_TASKS - per_db * len(db_ids)

    selected = []
    skipped_empty = 0

    for i, db_id in enumerate(db_ids):
        want = per_db + (1 if i < remainder else 0)
        pool = by_db[db_id][:]
        rng.shuffle(pool)

        taken = 0
        for ex in pool:
            if taken >= want:
                break
            if not gold_returns_rows(ex["db_id"], ex["query"]):
                skipped_empty += 1
                continue
            selected.append(ex)
            taken += 1

    rng.shuffle(selected)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        for i, ex in enumerate(selected, start=1):
            f.write(json.dumps({
                "task_id": f"t{i:03d}",
                "db_id": ex["db_id"],
                "question": ex["question"],
                "gold_query": ex["query"],
            }) + "\n")

    counts = defaultdict(int)
    for ex in selected:
        counts[ex["db_id"]] += 1

    print(f"Selected {len(selected)} tasks -> {OUT_PATH}")
    print(f"Skipped {skipped_empty} tasks whose gold query returned no rows")
    print("\nPer database:")
    for db_id in sorted(counts):
        print(f"  {db_id:<32} {counts[db_id]}")


if __name__ == "__main__":
    main()