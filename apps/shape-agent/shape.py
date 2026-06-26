"""Shape: governance for AI agents. Minimal version for MicroVM demo."""
from enum import Enum
from dataclasses import dataclass, field
import time


class ToolEffect(Enum):
    READ = "read"
    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"


class Phase(Enum):
    EXPLORE = "explore"
    DECIDE = "decide"
    COMMIT = "commit"


@dataclass
class ToolCall:
    name: str
    args: dict
    effect: ToolEffect
    cost: float
    phase: Phase
    allowed: bool
    reason: str
    timestamp: float = field(default_factory=time.time)


class Agent:
    def __init__(self, name: str, budget: float = 10.0, max_time_seconds: float = 3600):
        self.name = name
        self.budget = budget
        self.max_time_seconds = max_time_seconds
        self.spent = 0.0
        self.start_time = time.time()
        self.phase = Phase.EXPLORE
        self.tools: dict = {}
        self.audit: list[ToolCall] = []

    def tool(self, name: str, effect: ToolEffect, fn, cost: float = 0.0):
        self.tools[name] = {"fn": fn, "effect": effect, "cost": cost}

    @property
    def budget_pct(self) -> float:
        return (self.spent / self.budget) * 100 if self.budget > 0 else 0

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def time_pct(self) -> float:
        return (self.elapsed_seconds / self.max_time_seconds) * 100

    def set_phase(self, phase: Phase):
        self.phase = phase

    def call(self, name: str, **kwargs):
        tool = self.tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        # Governance checks
        reason = self._check_allowed(name, tool)
        allowed = reason == "allowed"

        record = ToolCall(
            name=name, args=kwargs, effect=tool["effect"],
            cost=tool["cost"], phase=self.phase,
            allowed=allowed, reason=reason,
        )
        self.audit.append(record)

        if not allowed:
            raise PermissionError(f"BLOCKED: {name} — {reason}")

        self.spent += tool["cost"]
        return tool["fn"](**kwargs)

    def _check_allowed(self, name: str, tool: dict) -> str:
        # Phase check
        if tool["effect"] != ToolEffect.READ and self.phase != Phase.COMMIT:
            return f"write tool '{name}' requires COMMIT phase (current: {self.phase.value})"

        # Budget check
        if self.budget_pct >= 90:
            return f"budget exhausted ({self.budget_pct:.0f}%)"
        if self.budget_pct >= 75 and tool["effect"] == ToolEffect.IRREVERSIBLE:
            return f"irreversible blocked above 75% budget ({self.budget_pct:.0f}%)"

        # Time check
        if self.time_pct >= 90:
            return f"time limit approaching ({self.elapsed_seconds:.0f}s / {self.max_time_seconds}s)"

        return "allowed"

    def get_audit_summary(self) -> dict:
        return {
            "agent": self.name,
            "phase": self.phase.value,
            "budget": {"limit": self.budget, "spent": self.spent, "pct": self.budget_pct},
            "time": {"elapsed_s": round(self.elapsed_seconds, 1), "limit_s": self.max_time_seconds, "pct": round(self.time_pct, 1)},
            "calls": len(self.audit),
            "blocked": sum(1 for c in self.audit if not c.allowed),
            "log": [
                {"tool": c.name, "allowed": c.allowed, "reason": c.reason, "cost": c.cost}
                for c in self.audit[-10:]
            ],
        }
