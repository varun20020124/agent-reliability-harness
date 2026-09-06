"""Reliability metrics over stored trials.

pass@k  - task succeeded on at least one of k trials (standard benchmark metric)
pass^k  - task succeeded on all k trials (what production requires)
"""

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path("results/trials.db")


@dataclass
class ModelSummary:
    config_name: str
    model: str
    n_tasks: int
    k: int
    pass_at_k: float          # fraction of tasks with >=1 success
    pass_pow_k: float         # fraction of tasks with all successes
    mean_trial_accuracy: float
    always_fail: int          # tasks that never succeeded
    flaky: int                # tasks with mixed outcomes
    tokens: int

    @property
    def reliability_gap(self) -> float:
        return self.pass_at_k - self.pass_pow_k


def load_outcomes(run_id="main", path=DEFAULT_PATH):
    """Return {(config, model): {task_id: [outcomes]}}."""
    con = sqlite3.connect(path)
    rows = con.execute(
        "SELECT config_name, model, task_id, trial_index, correct, tokens_used "
        "FROM trials WHERE run_id=? ORDER BY config_name, model, task_id, trial_index",
        (run_id,),
    ).fetchall()
    con.close()

    grouped = defaultdict(lambda: defaultdict(list))
    tokens = defaultdict(int)
    for config, model, task_id, _, correct, tok in rows:
        grouped[(config, model)][task_id].append(bool(correct))
        tokens[(config, model)] += tok or 0

    return grouped, tokens


def summarize(config, model, task_outcomes, tokens) -> ModelSummary:
    tasks = list(task_outcomes.values())
    k = max(len(o) for o in tasks)

    any_success = sum(1 for o in tasks if any(o))
    all_success = sum(1 for o in tasks if all(o))
    never = sum(1 for o in tasks if not any(o))
    flaky = sum(1 for o in tasks if any(o) and not all(o))

    total_trials = sum(len(o) for o in tasks)
    total_correct = sum(sum(o) for o in tasks)

    n = len(tasks)
    return ModelSummary(
        config_name=config,
        model=model,
        n_tasks=n,
        k=k,
        pass_at_k=any_success / n,
        pass_pow_k=all_success / n,
        mean_trial_accuracy=total_correct / total_trials,
        always_fail=never,
        flaky=flaky,
        tokens=tokens,
    )


def all_summaries(run_id="main", path=DEFAULT_PATH) -> list[ModelSummary]:
    grouped, tokens = load_outcomes(run_id, path)
    return [
        summarize(config, model, task_outcomes, tokens[(config, model)])
        for (config, model), task_outcomes in sorted(grouped.items())
    ]


def flaky_tasks(config, model, run_id="main", path=DEFAULT_PATH) -> list[tuple]:
    """Tasks with mixed outcomes, worst first."""
    grouped, _ = load_outcomes(run_id, path)
    outcomes = grouped.get((config, model), {})
    rows = [
        (task_id, sum(o), len(o))
        for task_id, o in outcomes.items()
        if any(o) and not all(o)
    ]
    return sorted(rows, key=lambda r: r[1])