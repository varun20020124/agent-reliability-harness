"""Generate figures for the README.

Usage: python scripts/plot_results.py
"""

import sqlite3
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt

DB_PATH = Path("results/trials.db")
DOCS_DIR = Path("docs")

GREEN = "#2E7D32"
RED = "#C62828"
BLUE = "#1565C0"
GREY = "#757575"
ORANGE = "#EF6C00"


def task_outcomes(run_id, config, model):
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT task_id, correct FROM trials "
        "WHERE run_id=? AND config_name=? AND model=? "
        "ORDER BY task_id, trial_index",
        (run_id, config, model),
    ).fetchall()
    con.close()
    out = defaultdict(list)
    for task_id, correct in rows:
        out[task_id].append(bool(correct))
    return out


def rates(outcomes):
    tasks = list(outcomes.values())
    n = len(tasks)
    return (sum(1 for o in tasks if any(o)) / n,
            sum(1 for o in tasks if all(o)) / n)


def plot_by_model():
    models = ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4.1-nano"]
    at_k, pow_k = [], []
    for m in models:
        a, p = rates(task_outcomes("v2", "baseline", m))
        at_k.append(a * 100)
        pow_k.append(p * 100)

    x = range(len(models))
    width = 0.36

    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.bar([i - width / 2 for i in x], at_k, width,
           label="pass@k (succeeded at least once)", color=GREY)
    ax.bar([i + width / 2 for i in x], pow_k, width,
           label="pass^k (succeeded every time)", color=GREEN)

    for i, (a, p) in enumerate(zip(at_k, pow_k)):
        ax.text(i - width / 2, a + 1, f"{a:.1f}", ha="center", fontsize=9)
        ax.text(i + width / 2, p + 1, f"{p:.1f}", ha="center", fontsize=9)

    ax.set_xticks(list(x))
    ax.set_xticklabels(models)
    ax.set_ylabel("Percent of tasks")
    ax.set_ylim(0, 100)
    ax.set_title("Same tasks solved; different consistency (k=5)")
    ax.legend(fontsize=9)
    fig.tight_layout()

    out = DOCS_DIR / "pass_at_k_vs_pass_pow_k.png"
    fig.savefig(out, dpi=150)
    print(f"Wrote {out}")


def plot_gap_vs_k():
    a5, p5 = rates(task_outcomes("v2", "baseline", "gpt-4.1-nano"))
    a15, p15 = rates(task_outcomes("k15", "baseline", "gpt-4.1-nano"))

    ks = [5, 15]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.plot(ks, [a5 * 100, a15 * 100], "s--", color=GREY,
            label="pass@k", markersize=8)
    ax.plot(ks, [p5 * 100, p15 * 100], "o-", color=RED,
            label="pass^k", markersize=8)

    ax.annotate(f"{(a5 - p5) * 100:.1f} pt gap", (5, (a5 + p5) / 2 * 100),
                xytext=(6, (a5 + p5) / 2 * 100), fontsize=9)
    ax.annotate(f"{(a15 - p15) * 100:.1f} pt gap", (15, (a15 + p15) / 2 * 100),
                xytext=(12.5, (a15 + p15) / 2 * 100 - 6), fontsize=9)

    ax.set_xlabel("Trials per task (k)")
    ax.set_ylabel("Percent of tasks")
    ax.set_xticks(ks)
    ax.set_ylim(50, 100)
    ax.set_title("The reliability gap grows with k (gpt-4.1-nano)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()

    out = DOCS_DIR / "gap_vs_k.png"
    fig.savefig(out, dpi=150)
    print(f"Wrote {out}")


def plot_task_distribution():
    outcomes = task_outcomes("k15", "baseline", "gpt-4.1-nano")
    pairs = sorted(((sum(o) / len(o)) * 100, t) for t, o in outcomes.items())
    values = [v for v, _ in pairs]

    colors = [RED if v == 0 else GREEN if v == 100 else ORANGE for v in values]

    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(range(len(values)), values, color=colors, width=0.85)

    ax.axhline(100, color=GREY, linestyle=":", linewidth=1)
    ax.set_xlabel("Task (sorted by success rate)")
    ax.set_ylabel("Success rate over 15 trials (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Per-task reliability is continuous, not binary (k=15)")

    n_flaky = sum(1 for v in values if 0 < v < 100)
    ax.text(0.5, 50, f"{n_flaky} tasks partially succeed",
            fontsize=10, color=ORANGE)
    fig.tight_layout()

    out = DOCS_DIR / "task_reliability_distribution.png"
    fig.savefig(out, dpi=150)
    print(f"Wrote {out}")


def plot_ablations():
    configs = ["baseline", "no_retry", "no_samples", "no_schema"]
    at_k, pow_k = [], []
    for c in configs:
        a, p = rates(task_outcomes("v2", c, "gpt-4.1-nano"))
        at_k.append(a * 100)
        pow_k.append(p * 100)

    x = range(len(configs))
    width = 0.36

    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar([i - width / 2 for i in x], at_k, width, label="pass@k", color=GREY)
    ax.bar([i + width / 2 for i in x], pow_k, width, label="pass^k", color=BLUE)

    ax.set_xticks(list(x))
    ax.set_xticklabels(configs)
    ax.set_ylabel("Percent of tasks")
    ax.set_ylim(0, 100)
    ax.set_title("Ablations (gpt-4.1-nano, k=5)")
    ax.legend(fontsize=9)
    fig.tight_layout()

    out = DOCS_DIR / "ablations.png"
    fig.savefig(out, dpi=150)
    print(f"Wrote {out}")


def main():
    DOCS_DIR.mkdir(exist_ok=True)
    plot_by_model()
    plot_gap_vs_k()
    plot_task_distribution()
    plot_ablations()


if __name__ == "__main__":
    main()
