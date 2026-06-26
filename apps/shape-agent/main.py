"""Shape-governed AI agent sandbox.

Demonstrates an agent with budget, time, and phase governance running inside a MicroVM.
Each API call simulates an agent step with full audit trail.

POST /agent/explore  {"query": "lookup customer"}
POST /agent/decide   {"action": "send_email", "to": "user@example.com"}
POST /agent/commit   {"action": "send_email", "to": "user@example.com"}
GET  /agent/status   → budget, time, phase, audit log
POST /agent/reset    → reset agent state
"""
import time
from fastapi import FastAPI
from pydantic import BaseModel
from shape import Agent, ToolEffect, Phase

app = FastAPI(title="Shape-Governed Agent (MicroVM)")

# --- Simulated tools ---

def lookup_customer(**kwargs):
    time.sleep(0.1)  # simulate latency
    return {"id": "C-1234", "name": "Acme Corp", "email": "contact@acme.com", "tier": "enterprise"}

def analyze_risk(**kwargs):
    time.sleep(0.2)
    return {"risk_score": 0.3, "recommendation": "approve", "confidence": 0.87}

def update_record(**kwargs):
    time.sleep(0.1)
    return {"updated": True, "record_id": kwargs.get("id", "unknown")}

def send_email(**kwargs):
    time.sleep(0.3)
    return {"sent": True, "to": kwargs.get("to"), "message_id": "msg-7a3b"}

def run_code(**kwargs):
    import subprocess
    result = subprocess.run(["python3", "-c", kwargs.get("code", "")], capture_output=True, text=True, timeout=5)
    return {"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}


# --- Agent setup ---

def create_agent() -> Agent:
    agent = Agent("microvm-agent", budget=5.0, max_time_seconds=300)
    agent.tool("lookup_customer", effect=ToolEffect.READ, fn=lookup_customer, cost=0.01)
    agent.tool("analyze_risk", effect=ToolEffect.READ, fn=analyze_risk, cost=0.05)
    agent.tool("update_record", effect=ToolEffect.REVERSIBLE, fn=update_record, cost=0.02)
    agent.tool("send_email", effect=ToolEffect.IRREVERSIBLE, fn=send_email, cost=0.10)
    agent.tool("run_code", effect=ToolEffect.REVERSIBLE, fn=run_code, cost=0.03)
    return agent

_agent = create_agent()


# --- API ---

class ExploreRequest(BaseModel):
    tool: str = "lookup_customer"
    args: dict = {}

class CommitRequest(BaseModel):
    tool: str
    args: dict = {}


@app.post("/agent/explore")
def explore(req: ExploreRequest):
    _agent.set_phase(Phase.EXPLORE)
    try:
        result = _agent.call(req.tool, **req.args)
        return {"phase": "explore", "tool": req.tool, "result": result, "status": _agent.get_audit_summary()}
    except (PermissionError, ValueError) as e:
        return {"phase": "explore", "tool": req.tool, "error": str(e), "status": _agent.get_audit_summary()}


@app.post("/agent/decide")
def decide(req: ExploreRequest):
    _agent.set_phase(Phase.DECIDE)
    try:
        result = _agent.call(req.tool, **req.args)
        return {"phase": "decide", "tool": req.tool, "result": result, "status": _agent.get_audit_summary()}
    except (PermissionError, ValueError) as e:
        return {"phase": "decide", "tool": req.tool, "error": str(e), "status": _agent.get_audit_summary()}


@app.post("/agent/commit")
def commit(req: CommitRequest):
    _agent.set_phase(Phase.COMMIT)
    try:
        result = _agent.call(req.tool, **req.args)
        return {"phase": "commit", "tool": req.tool, "result": result, "status": _agent.get_audit_summary()}
    except (PermissionError, ValueError) as e:
        return {"phase": "commit", "tool": req.tool, "error": str(e), "status": _agent.get_audit_summary()}


@app.get("/agent/status")
def status():
    return _agent.get_audit_summary()


@app.post("/agent/reset")
def reset():
    global _agent
    _agent = create_agent()
    return {"reset": True, "status": _agent.get_audit_summary()}


@app.get("/health")
def health():
    return {"status": "ok", "service": "shape-agent"}


@app.get("/")
def root():
    return {
        "service": "shape-agent",
        "description": "AI agent governed by Shape (budget, time, phases)",
        "try_this": [
            "POST /agent/explore {tool: 'lookup_customer'}",
            "POST /agent/explore {tool: 'analyze_risk'}",
            "POST /agent/commit  {tool: 'send_email', args: {to: 'x@y.com'}}",
            "POST /agent/commit  {tool: 'update_record', args: {id: 'C-1234'}}",
            "GET  /agent/status",
            "POST /agent/reset",
        ],
        "governance": {
            "budget": "$5.00 per session",
            "time_limit": "300 seconds",
            "rules": [
                "READ tools allowed in any phase",
                "WRITE tools blocked outside COMMIT phase",
                "IRREVERSIBLE tools blocked above 75% budget",
                "ALL tools blocked above 90% budget or time",
            ],
        },
    }
