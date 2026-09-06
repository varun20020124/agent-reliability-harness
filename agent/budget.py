"""Per-task resource budget."""

import time
from dataclasses import dataclass, field


class BudgetExceeded(Exception):
    pass


@dataclass
class Budget:
    max_model_calls: int = 8
    max_tokens: int = 20_000
    max_seconds: float = 120.0

    calls_used: int = 0
    tokens_used: int = 0
    started_at: float = field(default_factory=time.monotonic)

    def check(self) -> None:
        """Raise if any limit is already exhausted."""
        if self.calls_used >= self.max_model_calls:
            raise BudgetExceeded(f"model calls: {self.calls_used}")
        if self.tokens_used >= self.max_tokens:
            raise BudgetExceeded(f"tokens: {self.tokens_used}")
        elapsed = time.monotonic() - self.started_at
        if elapsed >= self.max_seconds:
            raise BudgetExceeded(f"wall clock: {elapsed:.1f}s")

    def record(self, tokens: int) -> None:
        self.calls_used += 1
        self.tokens_used += tokens

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    def as_dict(self) -> dict:
        return {
            "calls_used": self.calls_used,
            "tokens_used": self.tokens_used,
            "seconds_used": round(self.elapsed, 2),
        }