"""Run the agent on one task and verify it. Usage: python scripts/smoke_test.py"""

import json
from pathlib import Path

from agent.loop import AgentConfig, solve
from agent.verify import verify


def main():
    task = json.loads(Path("data/tasks.jsonl").read_text().splitlines()[0])
    print(f"Task:     {task['task_id']} ({task['db_id']})")
    print(f"Question: {task['question']}")
    print(f"Gold:     {task['gold_query']}\n")

    config = AgentConfig()
    result = solve(task["db_id"], task["question"], config)

    print(f"Generated: {result.query}")
    print(f"Attempts:  {result.attempts}")
    print(f"Stopped:   {result.stopped_reason}")
    print(f"Budget:    {result.budget}\n")

    if result.query:
        verdict = verify(task["db_id"], task["gold_query"], result.query)
        print(f"Verdict:   {verdict}")


if __name__ == "__main__":
    main()