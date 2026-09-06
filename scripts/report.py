"""Print the reliability report. Usage: python scripts/report.py"""

from benchmark.reliability import all_summaries, flaky_tasks

BASELINE = "baseline"


def main():
    summaries = all_summaries()

    print("BASELINE — reliability by model\n")
    print(f"{'model':<16} {'pass@k':>8} {'pass^k':>8} {'gap':>7} "
          f"{'flaky':>7} {'never':>7}")
    print("-" * 58)
    for s in summaries:
        if s.config_name != BASELINE:
            continue
        print(f"{s.model:<16} {s.pass_at_k:>7.1%} {s.pass_pow_k:>8.1%} "
              f"{s.reliability_gap:>6.1%} {s.flaky:>7} {s.always_fail:>7}")

    print("\n\nABLATIONS (gpt-4.1-nano)\n")
    print(f"{'config':<16} {'pass@k':>8} {'pass^k':>8} {'trial acc':>11} "
          f"{'flaky':>7}")
    print("-" * 54)
    for s in sorted(summaries, key=lambda s: s.config_name):
        if s.model != "gpt-4.1-nano":
            continue
        print(f"{s.config_name:<16} {s.pass_at_k:>7.1%} {s.pass_pow_k:>8.1%} "
              f"{s.mean_trial_accuracy:>10.1%} {s.flaky:>7}")

    print("\n\nFLAKY TASKS (baseline, gpt-4.1-nano)\n")
    for task_id, wins, k in flaky_tasks(BASELINE, "gpt-4.1-nano"):
        print(f"  {task_id}  {wins}/{k}")


if __name__ == "__main__":
    main()