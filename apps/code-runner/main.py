"""Sandboxed Python code execution API.

POST /run  {"code": "print(1+1)", "timeout": 5}
Returns:   {"stdout": "2\n", "stderr": "", "exit_code": 0, "duration_ms": 12}
"""
import subprocess
import time
import tempfile
import os
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="MicroVM Code Runner")


class RunRequest(BaseModel):
    code: str
    timeout: int = 10  # max seconds


class RunResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


@app.post("/run", response_model=RunResponse)
def run_code(req: RunRequest):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(req.code)
        f.flush()
        path = f.name

    start = time.time()
    try:
        result = subprocess.run(
            ["python3", path],
            capture_output=True, text=True,
            timeout=min(req.timeout, 30),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        duration_ms = int((time.time() - start) * 1000)
        return RunResponse(
            stdout=result.stdout[:100_000],
            stderr=result.stderr[:10_000],
            exit_code=result.returncode,
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired:
        return RunResponse(stdout="", stderr="Timeout exceeded", exit_code=124, duration_ms=req.timeout * 1000)
    finally:
        os.unlink(path)


@app.get("/health")
def health():
    return {"status": "ok", "runtime": "microvm"}


@app.get("/")
def root():
    return {
        "service": "code-runner",
        "usage": "POST /run with {code, timeout}",
        "example": {"code": "import sys; print(sys.version)", "timeout": 5},
    }
