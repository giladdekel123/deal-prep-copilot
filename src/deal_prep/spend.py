"""Model spending guard (owner-approved caps; spec Decision 27, §6A cost rule).

Every model call is estimated BEFORE it is sent (conservative input estimate + the full output
ceiling) and refused if it would exceed the per-briefing cap or the daily cap. Actual cost is
computed from the usage the provider reports and recorded in a daily ledger (runs/, gitignored).
Estimates are planning numbers, not invoices.
"""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from deal_prep import config

LEDGER_PATH = config.PROJECT_ROOT / "runs" / "openai_spend_ledger.json"
CHARS_PER_TOKEN = 3.0  # conservative (real English text is closer to 4)

# USD per 1M tokens, from developers.openai.com/api/docs/pricing as read on 2026-11-06 (Standard tier).
PRICES = {
    "gpt-6.1-terra": {"input": 1.00, "cached_input": 0.05, "output": 5.00},
    "gpt-6-luna": {"input": 0.10, "cached_input": 0.01, "output": 0.50},
}


class SpendLimitExceeded(RuntimeError):
    """Raised before sending a model call that would exceed an approved cap."""


def estimate_cost(model: str, input_chars: int, max_output_tokens: int) -> float:
    if model not in PRICES:
        raise SpendLimitExceeded(f"no approved price for model {model!r}; call refused")
    p = PRICES[model]
    return (input_chars / CHARS_PER_TOKEN) / 1e6 * p["input"] + max_output_tokens / 1e6 * p["output"]


def actual_cost(model: str, usage: dict) -> float:
    p = PRICES[model]
    cached = usage.get("cached_input_tokens", 0) or 0
    fresh = max(usage["input_tokens"] - cached, 0)
    return fresh / 1e6 * p["input"] + cached / 1e6 * p["cached_input"] + usage["output_tokens"] / 1e6 * p["output"]


@dataclass
class SpendGuard:
    run_cap_usd: float = 0.10
    daily_cap_usd: float = 1.00
    ledger_path: Path = LEDGER_PATH
    run_spent_usd: float = 0.0
    calls: list = field(default_factory=list)

    def _today(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _ledger(self) -> dict:
        try:
            return json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def spent_today(self) -> float:
        return self._ledger().get(self._today(), {}).get("usd", 0.0)

    def check(self, model: str, estimate_usd: float) -> None:
        if model not in PRICES:
            raise SpendLimitExceeded(f"no approved price for model {model!r}; call refused")
        if self.run_spent_usd + estimate_usd > self.run_cap_usd:
            raise SpendLimitExceeded(f"estimated ${estimate_usd:.4f} would exceed the per-briefing cap "
                                     f"(${self.run_cap_usd:.2f}; already ${self.run_spent_usd:.4f}); call refused")
        if self.spent_today() + estimate_usd > self.daily_cap_usd:
            raise SpendLimitExceeded(f"estimated ${estimate_usd:.4f} would exceed the daily cap "
                                     f"(${self.daily_cap_usd:.2f}; already ${self.spent_today():.4f}); call refused")

    def record(self, model: str, role: str, estimate_usd: float, usage: dict) -> float:
        cost = actual_cost(model, usage)
        self.run_spent_usd += cost
        self.calls.append({"model": model, "role": role, "estimate_usd": round(estimate_usd, 6),
                           "actual_usd": round(cost, 6), **usage})
        ledger = self._ledger()
        day = ledger.setdefault(self._today(), {"usd": 0.0, "calls": 0})
        day["usd"] = round(day["usd"] + cost, 6)
        day["calls"] += 1
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text(json.dumps(ledger, indent=1), encoding="utf-8")
        return cost
