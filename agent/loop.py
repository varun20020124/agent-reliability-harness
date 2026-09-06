"""The text-to-SQL agent loop.

Configurable so ablations can disable individual components without
changing the code path.
"""

import os
import re
from dataclasses import dataclass, field

from dotenv import load_dotenv
from openai import OpenAI

from agent.budget import Budget, BudgetExceeded
from agent.tools import get_schema, run_query

load_dotenv()

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = OpenAI()
    return _client


@dataclass
class AgentConfig:
    model: str = "gpt-4o-mini"
    temperature: float = 0.7

    use_schema: bool = True          # ablation: schema tool
    schema_samples: bool = True      # ablation: sample rows in schema
    use_retry: bool = True           # ablation: execution-feedback retry
    max_retries: int = 3

    max_model_calls: int = 8
    max_tokens: int = 20_000
    max_seconds: float = 120.0

    def budget(self) -> Budget:
        return Budget(
            max_model_calls=self.max_model_calls,
            max_tokens=self.max_tokens,
            max_seconds=self.max_seconds,
        )


@dataclass
class TrialResult:
    query: str | None
    attempts: int
    stopped_reason: str
    budget: dict
    transcript: list = field(default_factory=list)


SYSTEM_PROMPT = """You are a SQL expert. Write a single SQLite query that \
answers the user's question.

Respond with ONLY the SQL query inside a ```sql code block. No explanation."""

RETRY_PROMPT = """Your query produced this result:

{result}

If this correctly answers the question, reply with the same query. \
If not, write a corrected query. Respond with ONLY the SQL in a ```sql block."""


def _extract_sql(text: str) -> str | None:
    """Pull SQL out of a fenced code block, or fall back to the raw text."""
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    stripped = text.strip()
    if stripped.lower().startswith("select") or stripped.lower().startswith("with"):
        return stripped
    return None


def _call_model(client, config: AgentConfig, messages: list, budget: Budget) -> str:
    budget.check()
    response = client.chat.completions.create(
        model=config.model,
        messages=messages,
        temperature=config.temperature,
    )
    usage = response.usage
    budget.record(usage.total_tokens if usage else 0)
    return response.choices[0].message.content or ""


def solve(db_id: str, question: str, config: AgentConfig) -> TrialResult:
    """Run the agent on one task. Never raises; failures are reported."""
    client = _get_client()
    budget = config.budget()
    transcript = []

    user_parts = [f"Question: {question}"]
    if config.use_schema:
        schema = get_schema(db_id, include_samples=config.schema_samples)
        user_parts.insert(0, f"Database schema:\n\n{schema}\n")
    else:
        user_parts.insert(0, f"Database: {db_id} (schema not provided)\n")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n".join(user_parts)},
    ]

    query = None
    attempts = 0
    stopped_reason = "unknown"

    max_attempts = 1 + (config.max_retries if config.use_retry else 0)

    try:
        for attempt in range(max_attempts):
            attempts = attempt + 1

            reply = _call_model(client, config, messages, budget)
            transcript.append({"role": "assistant", "content": reply})

            candidate = _extract_sql(reply)
            if candidate is None:
                stopped_reason = "no sql in response"
                if not config.use_retry:
                    break
                messages.append({"role": "assistant", "content": reply})
                messages.append({
                    "role": "user",
                    "content": "No SQL found. Respond with only a ```sql block.",
                })
                continue

            query = candidate

            if not config.use_retry:
                stopped_reason = "submitted (no retry)"
                break

            result = run_query(db_id, query)
            transcript.append({"role": "tool", "content": result})

            if not result.startswith("ERROR"):
                stopped_reason = "executed successfully"
                break

            if attempt == max_attempts - 1:
                stopped_reason = "retries exhausted"
                break

            messages.append({"role": "assistant", "content": reply})
            messages.append({
                "role": "user",
                "content": RETRY_PROMPT.format(result=result),
            })

    except BudgetExceeded as e:
        stopped_reason = f"budget exceeded: {e}"
    except Exception as e:
        stopped_reason = f"error: {type(e).__name__}: {e}"

    return TrialResult(
        query=query,
        attempts=attempts,
        stopped_reason=stopped_reason,
        budget=budget.as_dict(),
        transcript=transcript,
    )