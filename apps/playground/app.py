import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import pandas as pd
    import numpy as np
    import sys, os, psutil, platform
    return mo, pd, np, sys, os, psutil, platform


@app.cell
def _(mo):
    mo.md("""
# 🔥 Lambda MicroVM Playground

This notebook runs inside a **Firecracker MicroVM** on AWS, accessed through CloudFront.
Edit cells, run code, explore data. The VM auto-suspends when you leave and resumes when you return.
""")
    return


@app.cell
def _(mo):
    n_rows = mo.ui.slider(10, 500, value=100, step=10, label="Simulated data points")
    n_rows
    return (n_rows,)


@app.cell
def _(mo, pd, np, n_rows):
    np.random.seed(42)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n_rows.value, freq="h"),
        "cpu_pct": np.random.beta(2, 5, n_rows.value) * 100,
        "mem_gb": np.random.normal(4.2, 0.8, n_rows.value).clip(1, 8),
        "rps": np.random.poisson(150, n_rows.value),
        "region": np.random.choice(["eu-west-1", "us-east-1", "ap-northeast-1"], n_rows.value),
    })
    mo.vstack([
        mo.md(f"### Simulated MicroVM fleet telemetry ({n_rows.value} samples)"),
        df,
    ])
    return (df,)


@app.cell
def _(mo, df):
    mo.vstack([
        mo.md("### Summary by region"),
        df.groupby("region").agg(
            avg_cpu=("cpu_pct", "mean"),
            avg_mem=("mem_gb", "mean"),
            avg_rps=("rps", "mean"),
            count=("rps", "count"),
        ).round(1),
    ])
    return


@app.cell
def _(mo, np):
    active = np.array([5,3,2,2,2,3,8,25,45,52,48,50,55,53,48,42,38,30,22,18,15,12,8,6])
    cost_suspend = (active * 0.028).sum()
    cost_always = active.max() * 0.028 * 24
    mo.md(f"""
### 💰 Cost model: suspend/resume vs always-on

A fleet that scales with demand: **${cost_suspend:.2f}/day** (suspend idle VMs)
vs keeping peak capacity running: **${cost_always:.2f}/day** (always-on)

**Savings: {(1 - cost_suspend/cost_always)*100:.0f}%** from auto-suspend alone.
""")
    return


@app.cell
def _(mo, sys, os, psutil, platform):
    mem = psutil.virtual_memory()
    mo.accordion({
        "⚙️ VM runtime info": mo.md(f"""
| | |
|---|---|
| Python | `{sys.version.split()[0]}` |
| Arch | `{platform.machine()}` / {platform.system()} |
| CPUs | {os.cpu_count()} |
| RAM | {mem.total / 1024**3:.1f} GB total, {mem.available / 1024**3:.1f} GB free |
| PID | {os.getpid()} |

Firecracker VM with full `/proc`, network, and pip access.
""")
    })
    return


if __name__ == "__main__":
    app.run()
