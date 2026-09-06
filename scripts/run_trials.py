"""Run agent trials across models and configurations.

Usage:
  python scripts/run_trials.py --config baseline --models gpt-4o-mini \
      --tasks 3 --trials 2
  python scripts/run_trials.py --config baseline --trials 5
"""

import argparse
import json
import time
from pathlib import Path

from agent.loop import AgentConfig, solve
from agent.verify import verify
from benchmark.store import TrialStore

TASKS_PATH = Path("data/tasks.jsonl")

# Named configurations. Ablations differ from baseline by one component.
CONFIGS = {
    "baseline":     dict(use_schema=True,  use_retry=True,  schema_samples=True),
    "no_retry":     dict(use_schema=True,  use_retry=False, schema_samples=True),
    "no_schema":    dict(use_schema=False, use_retry=True,  schema_samples=True),
    "no_samples":   dict(use_schema=True,  use_retry=True,  schema_samples=False),
    "tight_budget": dict(use_schema=True,  use_retry=True,  schema_samples=True,
                         max_model_calls=2, max_seconds=30.0),
}

DEFAULT_MODELS = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano"]


def load_tasks(limit=None):
    tasks = [json.loads(line) for line in TASKS_PATH.open()]
    return tasks[:limit] if limit else tasks


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="baseline", choices=list(CONFIGS))
    p.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    p.add_argument("--tasks", type=int, default=None, help="limit task count")
    p.add_argument("--trials", type=int, default=5, help="trials per task")
    p.add_argument("--run-id", default="main")
    args = p.parse_args()

    tasks = load_tasks(args.tasks)
    store = TrialStore()

    total = len(args.models) * len(tasks) * args.trials
    print(f"config={args.config}  models={args.models}")
    print(f"{len(tasks)} tasks x {args.trials} trials = {total} runs\n")

    done = 0
    started = time.monotonic()

    for model in args.models:
        config = AgentConfig(model=model, **CONFIGS[args.config])

        for task in tasks:
            outcomes = []
            for trial in range(args.trials):
                done += 1

                if store.already_done(args.run_id, args.config, model,
                                      task["task_id"], trial):
                    outcomes.append("-")
                    continue

                result = solve(task["db_id"], task["question"], config)
                verdict = (verify(task["db_id"], task["gold_query"], result.query)
                           if result.query
                           else {"correct": False, "reason": result.stopped_reason})

                store.record(args.run_id, args.config, model, task, trial,
                             verdict, result)
                outcomes.append("X" if verdict.get("correct") else ".")

            elapsed = time.monotonic() - started
            rate = done / elapsed if elapsed else 0
            eta = (total - done) / rate if rate else 0
            print(f"  {model:<16} {task['task_id']} "
                  f"[{''.join(outcomes)}]  {done}/{total}  eta {eta/60:.1f}m")

    totals = store.totals()
    print(f"\nStored {totals['trials']} trials, "
          f"{totals['correct']} correct, {totals['tokens']:,} tokens")
    store.close()


if __name__ == "__main__":
    main()