"""Download Spider dev questions and the SQLite databases they reference.

Usage: python scripts/fetch_spider.py
"""

import json
import shutil
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import hf_hub_download

DB_REPO = "premai-io/spider"
OUT_DIR = Path("data/spider")
DB_DIR = OUT_DIR / "database"
DEV_PATH = OUT_DIR / "dev.jsonl"


def fetch_questions():
    ds = load_dataset("xlangai/spider", split="validation")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with DEV_PATH.open("w") as f:
        for ex in ds:
            f.write(json.dumps({
                "db_id": ex["db_id"],
                "question": ex["question"],
                "query": ex["query"],
            }) + "\n")
    db_ids = sorted(set(ds["db_id"]))
    print(f"Wrote {len(ds)} dev questions to {DEV_PATH}")
    print(f"Databases referenced: {len(db_ids)}")
    return db_ids


def fetch_databases(db_ids):
    DB_DIR.mkdir(parents=True, exist_ok=True)
    ok, failed = [], []

    for db_id in db_ids:
        dest = DB_DIR / db_id / f"{db_id}.sqlite"
        if dest.exists():
            ok.append(db_id)
            continue
        try:
            path = hf_hub_download(
                repo_id=DB_REPO,
                repo_type="dataset",
                filename=f"database/{db_id}/{db_id}.sqlite",
            )
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(path, dest)
            ok.append(db_id)
            print(f"  ok      {db_id}")
        except Exception as e:
            failed.append(db_id)
            print(f"  FAILED  {db_id}: {type(e).__name__}")

    print(f"\nDownloaded {len(ok)}/{len(db_ids)} databases")
    if failed:
        print(f"Failed: {failed}")
    return ok


def main():
    db_ids = fetch_questions()
    print("\nFetching databases...")
    fetch_databases(db_ids)


if __name__ == "__main__":
    main()