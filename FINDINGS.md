# Findings

## Summary

Agent benchmarks report **pass@k** — did the agent succeed at least once in k attempts. Production requires **pass^k** — did it succeed on *every* attempt. This project measures both for a text-to-SQL agent under deterministic verification, across three models, 40 Spider tasks, and three ablations.

Three results:

1. **The reliability gap grows with k and does not converge.** pass@15 was 87.5% while pass^15 was 67.5% — a 20-point gap, up from 12.5 points at k=5. pass@k is stable across k; pass^k keeps falling.

2. **Per-task reliability measured at k=5 is not reproducible.** Two independent runs of the identical configuration identified overlapping-but-different sets of flaky tasks. The *count* was stable; the *identity* was not.

3. **The least reliable tasks are benchmark defects, not model failures.** Of the four tasks with the lowest success rates, three are underspecified in distinct ways. This was only discoverable by reading individual failures.

---

## Setup

**Agent.** A text-to-SQL loop: receives a natural-language question and database schema, writes a query, executes it, and on execution error reads the error and revises. Temperature 0.7 — deliberately nonzero, since at temperature 0 pass^k would trivially equal pass@k, and production systems do not run at 0.

**Verification.** Deterministic. Execute the candidate query and the gold query, compare result multisets. Row order compared only when the gold query contains ORDER BY; column order ignored; duplicates preserved; numeric strings and numbers compared as numbers. No LLM judge, no rubric.

**Budget.** Hard per-task caps — 8 model calls, 20K tokens, 120 seconds. Without these, "reliability" is confounded with how long the agent is allowed to flail.

**Tasks.** 40 Spider dev tasks, evenly spread across 19 databases, fixed seed. Tasks whose gold query returns zero rows were excluded: an agent can "succeed" on those by writing a query that returns nothing for entirely the wrong reason.

**Models.** gpt-4o-mini, gpt-4.1-mini, gpt-4.1-nano. Three models spanning a capability range, so the results can distinguish "agent loops are unreliable" from "this particular model is unreliable."

---

## Result 1: the reliability gap grows with k

Baseline, gpt-4.1-nano, 40 tasks:

| k | pass@k | pass^k | gap |
|---|---|---|---|
| 5 | 87.5% | 75.0% | 12.5 pts |
| 15 | 87.5% | 67.5% | 20.0 pts |

pass@k is unchanged — the set of tasks the model *can* solve does not depend on how many times you ask. pass^k falls, because every additional trial is another chance to observe a failure.

The gap has not converged at k=15. Anyone reporting pass^5 is reporting an optimistic number and cannot say how optimistic without running more trials.

### Across models (k=5, baseline)

| model | pass@k | pass^k | gap | flaky | never |
|---|---|---|---|---|---|
| gpt-4o-mini | 87.5% | 85.0% | 2.5 pts | 1 | 5 |
| gpt-4.1-mini | 87.5% | 87.5% | 0.0 pts | 0 | 5 |
| gpt-4.1-nano | 87.5% | 75.0% | 12.5 pts | 5 | 5 |

All three models solve the same set of tasks. They differ in whether they solve them *consistently*. At this difficulty level the reliability gap tracks model weakness — the strongest model is deterministic, the weakest is flaky.

---

## Result 2: per-task flakiness is not reproducible at k=5

Two independent runs, identical configuration and tasks, gpt-4.1-nano:

| run | flaky tasks identified |
|---|---|
| run 1 | t002, t014, t025, t035 |
| run 2 | t002, t007, t024, t025, t039 |

Two of five overlap. (One difference, t014, is attributable to a verifier fix between runs — see Problems. The rest is run-to-run variance.)

At k=15 the distribution explains why:

| task | successes | rate |
|---|---|---|
| t002 | 4/15 | 27% |
| t025 | 6/15 | 40% |
| t024 | 7/15 | 47% |
| t007 | 9/15 | 60% |
| t035 | 10/15 | 67% |
| t026 | 12/15 | 80% |
| t039 | 12/15 | 80% |
| t014 | 13/15 | 87% |

The distribution is continuous, not bimodal. Each task has its own success probability spread across the range — these are not tasks the model can or cannot do.

A task at p=0.87 has roughly a 50% chance of producing five consecutive successes, so it looks perfectly reliable half the time. That is exactly t014's behaviour across the two k=5 runs.

**8 tasks are flaky at k=15 versus 4-5 at k=5.** Low-k evaluation systematically undercounts unreliable tasks *and* misidentifies which ones they are. Per-task reliability at small k is a sample, not a property.

---

## Result 3: the least reliable tasks are benchmark defects

Inspecting the four worst tasks by hand:

**t002 — 4/15. Underspecified ordering.**

> "Show the name of the conductor that has conducted the most number of orchestras."
> `... GROUP BY T2.Conductor_ID ORDER BY COUNT(*) DESC LIMIT 1`

All twelve conductors in the database have conducted exactly one orchestra. There are twelve equally correct answers; the gold query returns whichever row SQLite emits first. The agent's queries were semantically equivalent to the gold — differing only by including `Name` in the GROUP BY, which changed the query plan and therefore which tied row surfaced.

This task measures SQLite's query planner, not the agent.

**t025 — 6/15. Information missing from the question.**

> Question: `... the cartoon "The Rise of the Blue Beetle"`
> Gold: `WHERE T2.Title = "The Rise of the Blue Beetle!"`

The gold query matches a title with a trailing exclamation mark that the question omits. An agent that copies the title from the question exactly returns zero rows. Success requires guessing the punctuation or having seen it in sampled rows — which is why removing sample rows (see ablations) hurt.

**t024 — 7/15. Ambiguous phrasing.**

> "What is maximum and minimum death toll caused each time?"
> Gold: `SELECT max(killed), min(killed) FROM death`

The gold reads this as a single global maximum and minimum. Several trials read "each time" as per-battle grouping and produced a grouped result. Both are defensible readings of the English. The agent is not being inconsistent about SQL — it is being inconsistent about which of two valid interpretations to commit to.

**t007 — 9/15.** Same `ORDER BY COUNT(*) DESC LIMIT 1` shape as t002, but the data has a clear winner (United States, 4, versus 1 for all others), so tie ambiguity does not explain it. Cause not established.

**Three distinct defect types among four tasks: underspecified ordering, missing information, and ambiguous phrasing.** The bottom of the reliability distribution measures benchmark quality, not agent behaviour — and this is invisible in any aggregate number.

---

## Ablations

Paired ablations on identical tasks and seeds, gpt-4.1-nano, k=5. One component changed per run.

| config | pass@k | pass^k | trial accuracy | flaky |
|---|---|---|---|---|
| baseline | 87.5% | 75.0% | 82.5% | 5 |
| no_retry | 90.0% | 65.0% | 81.0% | 10 |
| no_samples | 80.0% | 72.5% | 75.0% | 3 |
| no_schema | 22.5% | 17.5% | 19.5% | 2 |

**no_retry — retry reduces variance, not capability.** pass@k is unchanged or slightly higher without retry; pass^k drops 10 points and the flaky count doubles. Retry does not make more tasks solvable — it appears to make solved tasks more consistent. Sample sizes here are small and this warrants more trials.

The mechanism is worth stating: **599 of 600 baseline trials ended in successful execution.** Only one hit an execution error. Since retry only fires on execution errors, it almost never engages. The dominant failure mode is a query that runs cleanly and answers the wrong question — a semantic error that execution feedback is structurally incapable of detecting.

**no_schema — removing schema collapses performance.** 82.5% to 19.5% trial accuracy. Unsurprising in direction; the magnitude is the point. Note the failure *character* also changes: without schema the model fails consistently rather than intermittently, producing fewer flaky tasks and more total failures.

**no_samples — sample rows affect consistency more than capability.** pass@k drops 7.5 points; pass^k drops only 2.5. Two sample rows per table cost few tokens and help the model guess value formats correctly.

---

## Problems encountered

### A bug in the verifier inflated the unreliability numbers

Spider stores many numeric columns as TEXT. A gold query's `max(age)` returns the string `"9"`; a candidate's `max(CAST(age AS INTEGER))` returns the integer `9`. The original normalization rendered these as `"9"` and `"9.0"` and reported a mismatch.

Task t014 appeared 40% reliable as a result. Three of its five "failures" used `CAST` and returned the correct answer — arguably the better SQL.

Found by pulling the generated queries for a flaky task and reading them, not from any test failure. The existing eight verifier tests all passed; none covered text-versus-numeric coercion.

Fixed by parsing numeric strings before comparison, adding a regression test, and re-running every configuration under a new run ID. The original run was retained so the effect of the fix is measurable.

**Every number in this project depends on the verifier being correct.** That is why it was written and tested before the agent — and it still had a bug that only manual inspection of failures surfaced.

### The run hung indefinitely on a network stall

The main run stopped progressing at trial 392. The OpenAI client had no timeout configured and was blocked in an SSL read that would never return.

Fixed with `OpenAI(timeout=30.0, max_retries=2)`. Recovery cost nothing because results are written to SQLite incrementally with a unique constraint on (run_id, config, model, task, trial) — re-running the identical command skipped the 392 completed trials and resumed. Without that, the stall would have cost the entire run.

### Empty gold results are a false-positive channel

If a gold query returns zero rows, an agent can match it by writing a query that returns nothing for an entirely unrelated reason — a typo in a join condition, for instance. One task was excluded at selection time for this reason, and the verifier also rejects any comparison where the gold returns no rows.

---

## Limitations

**Task difficulty is low.** All three models achieve 87.5% pass@k, so the models are not separated by capability and the reliability gap is measured near the ceiling. Harder tasks (Spider provides difficulty labels; BIRD is harder still) would give more room.

**k=15 is still small.** The gap had not converged. A task at p=0.9 needs many more than 15 trials for a stable estimate, and the per-task rates reported here carry wide confidence intervals.

**Ablations ran on one model.** The ablation effects may not generalize across the capability range.

**Cause of t007's flakiness is not established.** Reported as unexplained rather than assigned a plausible-sounding explanation.

**Single benchmark.** All findings are on Spider. The outcome-validity defects found here are Spider's; whether other agent benchmarks have comparable rates is untested, though the categories (tie ambiguity, missing information, ambiguous phrasing) are generic enough to expect elsewhere.

---

## Reproducing

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
echo 'OPENAI_API_KEY=sk-...' > .env

python scripts/fetch_spider.py      # dev questions + 20 SQLite databases
python scripts/select_tasks.py      # fixed 40-task subset, seed 20260906
pytest tests/                       # verifier tests

python scripts/run_trials.py --config baseline --trials 5 --run-id v2
python scripts/run_trials.py --config no_retry --models gpt-4.1-nano --trials 5 --run-id v2
python scripts/run_trials.py --config no_samples --models gpt-4.1-nano --trials 5 --run-id v2
python scripts/run_trials.py --config no_schema --models gpt-4.1-nano --trials 5 --run-id v2
python scripts/run_trials.py --config baseline --models gpt-4.1-nano --trials 15 --run-id k15

python scripts/report.py
```

Runs are resumable — re-running an identical command skips completed trials. Total cost for all runs reported here was approximately 1.8M tokens, under two dollars.
