"""Tests for Shape governance logic. Run: python -m pytest apps/shape-agent/test_shape.py"""
import sys
sys.path.insert(0, ".")
from shape import Agent, ToolEffect, Phase
import pytest


def noop(**kwargs):
    return {"ok": True, **kwargs}


def test_read_allowed_in_explore():
    agent = Agent("test", budget=10)
    agent.tool("read_db", effect=ToolEffect.READ, fn=noop, cost=0.01)
    agent.set_phase(Phase.EXPLORE)
    result = agent.call("read_db")
    assert result == {"ok": True}


def test_write_blocked_in_explore():
    agent = Agent("test", budget=10)
    agent.tool("write_db", effect=ToolEffect.REVERSIBLE, fn=noop, cost=0.01)
    agent.set_phase(Phase.EXPLORE)
    with pytest.raises(PermissionError):
        agent.call("write_db")


def test_write_allowed_in_commit():
    agent = Agent("test", budget=10)
    agent.tool("write_db", effect=ToolEffect.REVERSIBLE, fn=noop, cost=0.01)
    agent.set_phase(Phase.COMMIT)
    result = agent.call("write_db")
    assert result == {"ok": True}


def test_budget_blocks_at_90_percent():
    agent = Agent("test", budget=1.0)
    agent.tool("expensive", effect=ToolEffect.READ, fn=noop, cost=0.1)
    agent.set_phase(Phase.EXPLORE)
    # Spend 90% manually
    agent.spent = 0.91
    with pytest.raises(PermissionError, match="budget exhausted"):
        agent.call("expensive")


def test_irreversible_blocked_above_75_percent():
    agent = Agent("test", budget=1.0)
    agent.tool("send_email", effect=ToolEffect.IRREVERSIBLE, fn=noop, cost=0.1)
    agent.set_phase(Phase.COMMIT)
    agent.spent = 0.76
    with pytest.raises(PermissionError, match="irreversible blocked"):
        agent.call("send_email")


def test_audit_trail():
    agent = Agent("test", budget=10)
    agent.tool("read", effect=ToolEffect.READ, fn=noop, cost=0.05)
    agent.set_phase(Phase.EXPLORE)
    agent.call("read")
    agent.call("read")
    summary = agent.get_audit_summary()
    assert summary["calls"] == 2
    assert summary["blocked"] == 0
    assert summary["budget"]["spent"] == 0.10


def test_budget_tracking():
    agent = Agent("test", budget=5.0)
    agent.tool("action", effect=ToolEffect.READ, fn=noop, cost=0.50)
    agent.set_phase(Phase.EXPLORE)
    for _ in range(3):
        agent.call("action")
    assert agent.spent == 1.50
    assert agent.budget_pct == 30.0
