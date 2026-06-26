# Lambda MicroVM Starter Kit

Deploy any web app to an AWS Lambda MicroVM with public access via CloudFront. One command.

```bash
./deploy.sh apps/playground
```

## What this does

1. Packages your app (any Dockerfile + code in a folder)
2. Builds a MicroVM image (Firecracker snapshot)
3. Launches the MicroVM (auto-suspend/resume)
4. Deploys CloudFront + Lambda@Edge for public HTTPS + WebSocket access
5. Prints your public URL

## Quick start

```bash
# Prerequisites: AWS CLI 2.35.10+, authenticated session
# Supported regions: us-east-1, us-east-2, us-west-2, eu-west-1, ap-northeast-1

# Deploy public (browser-accessible via CloudFront)
./deploy.sh apps/playground

# Deploy private (backend API, auth token required)
./deploy.sh apps/code-runner --private
./deploy.sh apps/pdf-generator --private
./deploy.sh apps/shape-agent --private

# After private deploy, test with the example client:
./apps/code-runner/example-client.sh
./apps/shape-agent/example-client.sh
```

## Project structure

```
├── apps/                    # Your applications (pick one to deploy)
│   ├── playground/          # Interactive marimo notebook with data viz
│   ├── code-runner/         # Sandboxed Python code execution API
│   ├── pdf-generator/       # HTML-to-PDF conversion service
│   └── shape-agent/         # AI agent with Shape governance
├── infra/                   # Infrastructure code (Lambda@Edge, future CDK)
│   ├── edge-auth/           # Lambda@Edge function (auth token injection)
│   └── cdk/                 # CDK stack (placeholder for when CFN support lands)
├── deploy.sh                # Main deploy script
├── destroy.sh               # Tear down a deployment
└── TROUBLESHOOTING.md       # Every gotcha and fix
```

## Example apps

### playground — Interactive notebook (public)

A [marimo](https://marimo.io) reactive Python notebook running inside a MicroVM. Demonstrates interactive data visualization, fleet cost modeling, and system introspection. Deploy as public; users interact via browser.

```bash
./deploy.sh apps/playground
# Opens at https://xxx.cloudfront.net/
```

**Use case:** Data exploration, demos, interactive documentation, personal dev environments.

### code-runner — Sandboxed code execution (private)

A FastAPI service that executes arbitrary Python in isolation. Each request runs in the same VM but subprocess-isolated. Intended as a backend service called by your application (AI coding assistants, CI systems, educational platforms).

```bash
./deploy.sh apps/code-runner --private
./apps/code-runner/example-client.sh
```

**API:**
- `POST /run` — `{"code": "print(1+1)", "timeout": 5}` → `{"stdout": "2\n", "exit_code": 0, "duration_ms": 12}`
- `GET /health` — health check

**Use case:** AI agent tool execution, automated testing, REPL backends, code evaluation in LMS platforms.

### pdf-generator — Document generation (private)

A FastAPI service that converts HTML to PDF using WeasyPrint. Includes an invoice template with Jinja2. Deploy as a backend service your app calls when it needs to generate documents.

```bash
./deploy.sh apps/pdf-generator --private
./apps/pdf-generator/example-client.sh
```

**API:**
- `POST /generate` — `{"html": "<h1>Hello</h1>"}` → PDF binary
- `POST /invoice` — `{"company": "...", "items": [...]}` → formatted invoice PDF

**Use case:** Invoice generation, report rendering, certificate creation, any HTML-to-PDF pipeline.

### shape-agent — Governed AI agent (private)

A FastAPI service demonstrating [Shape](https://github.com/vidanov/shape) governance for AI agents. The agent has tools (lookup, analyze, send email, run code) controlled by lifecycle phases (explore → decide → commit), budget limits, and time constraints.

```bash
./deploy.sh apps/shape-agent --private
./apps/shape-agent/example-client.sh
```

**API:**
- `POST /agent/explore` — call READ tools (writes blocked)
- `POST /agent/decide` — evaluate options (writes blocked)
- `POST /agent/commit` — execute actions (writes allowed, budget-gated)
- `GET /agent/status` — budget, time, audit trail
- `POST /agent/reset` — reset agent state

**Governance rules:**
- READ tools allowed in any phase
- WRITE/IRREVERSIBLE tools blocked outside COMMIT
- Irreversible tools blocked above 75% budget
- All tools blocked above 90% budget or time limit

**Use case:** Multi-tenant AI agent platforms where each user gets an isolated MicroVM with governed tool access. MicroVMs provide the isolation boundary, Shape controls what happens inside.

## Two deployment modes

### Public (`./deploy.sh apps/name`)

Creates CloudFront + Lambda@Edge in front of the MicroVM. Anyone with the URL can access it. Best for:
- Interactive UIs (notebooks, dashboards)
- Demos and showcases
- Internal tools without VPN

### Private (`./deploy.sh apps/name --private`)

Creates only the MicroVM. Access requires an auth token minted via AWS CLI/SDK. Best for:
- Backend APIs called by your application
- Code execution sandboxes
- Services processing sensitive data
- Multi-tenant platforms where your backend manages user→MicroVM routing

## How apps work

Each app is a folder with:
- `Dockerfile` — builds on `public.ecr.aws/lambda/microvms:al2023-minimal`
- Your application code (Python, Node, Go, whatever runs in a container)
- Optional `requirements.txt` for Python apps
- Optional `example-client.sh` for private apps (demonstrates the API)

The Dockerfile must `EXPOSE` a port. The deploy script auto-detects it.

## Create your own app

```bash
mkdir apps/my-app
```

Minimal example (Flask):

```dockerfile
# apps/my-app/Dockerfile
FROM public.ecr.aws/lambda/microvms:al2023-minimal
RUN dnf install -y python3 python3-pip && dnf clean all
RUN pip install --no-cache-dir flask
COPY app.py /app/app.py
WORKDIR /app
EXPOSE 5000
CMD ["python3", "app.py"]
```

```python
# apps/my-app/app.py
from flask import Flask
app = Flask(__name__)

@app.route("/")
def hello():
    return "Running in a Firecracker MicroVM!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
```

Deploy it:

```bash
./deploy.sh apps/my-app
```

## Architecture

```
Browser → CloudFront (caches static assets, passes WebSocket)
              ↓ origin-request
         Lambda@Edge (injects MicroVM auth token)
              ↓
         MicroVM endpoint (Firecracker VM, your app)
```

For private deployments, your backend calls the MicroVM directly with auth tokens (no CloudFront layer).

## VPC connectivity

MicroVMs can access private VPC resources through Lambda Network Connectors. The MicroVM does NOT run inside your VPC (same model as Lambda functions). It connects through managed ENIs:

```bash
aws lambda-microvms run-microvm \
  --image-identifier ... \
  --egress-network-connectors '["arn:aws:lambda:REGION:ACCT:network-connector:my-vpc-connector"]' \
  ...
```

Default is `INTERNET_EGRESS` (public internet). With a VPC connector, outbound goes through your subnets.

## Costs (eu-west-1, Graviton)

| Usage pattern | 2 vCPU / 4 GB | 4 vCPU / 8 GB |
|---------------|---------------|---------------|
| Always-on 24/7 | ~$96/mo | ~$191/mo |
| 4 hours/day, 20 days | ~$11/mo | ~$22/mo |
| Bursty (auto-suspend) | Pay only active seconds | + $0 when suspended |
| CloudFront + Edge | ~$0-1/mo | ~$0-1/mo |

MicroVMs are cost-effective for bursty workloads (<4-5 hrs/day active). For always-on, EC2 is 3-5x cheaper.

## When to use MicroVMs vs Lambda functions

Not every workload needs a MicroVM. Use this decision guide:

| Signal | Use MicroVM | Use Lambda function |
|--------|-------------|---------------------|
| Needs state between requests | ✓ | |
| Runs untrusted/user code | ✓ | |
| Long-running (>15 min) | ✓ | |
| WebSocket / persistent connection | ✓ | |
| Needs full OS (FUSE, eBPF, Docker) | ✓ | |
| High-volume, stateless | | ✓ |
| Event-driven (S3, SQS, etc.) | | ✓ |
| Sub-second billing granularity | | ✓ |
| Auto-scales to thousands | | ✓ |

The `pdf-generator` example works as a MicroVM demo, but for production PDF generation at scale, a Lambda function with a WeasyPrint/Chromium layer is cheaper and simpler (auto-scales, no VM lifecycle to manage). The MicroVM version makes sense when you need persistent template caches, heavy dependencies that exceed Lambda layer limits, or rendering jobs longer than 15 minutes.

## Future app ideas (contributions welcome)

These are use cases where MicroVMs have a clear advantage over Lambda functions:

| App | Why MicroVM fits | Complexity |
|-----|-----------------|------------|
| **jupyter-workspace** | Per-user Jupyter notebook with pip install, persistent filesystem | Medium |
| **playwright-runner** | Browser testing with pre-loaded Chromium (snapshot = no 10s startup) | Medium |
| **llm-sandbox** | Run local LLMs (Ollama/llama.cpp) in isolation per tenant | High |
| **game-server** | Stateful multiplayer sessions (WebSocket, 8hr lifetime) | Medium |
| **dev-environment** | Full VS Code Server/Theia per developer, suspend overnight | High |
| **ci-runner** | Isolated build environments with Docker-in-Docker | Medium |
| **vulnerability-scanner** | Run untrusted security tools against customer code | Low |
| **training-sandbox** | Workshop/training environments that reset per session | Low |

The pattern: if it needs **isolation + state + long runtime**, it's a MicroVM workload. If it's **stateless + short + high-volume**, Lambda functions win.

## Preparing for IaC (CDK/CloudFormation)

Lambda MicroVMs launched June 22, 2026 with API-only support. CloudFormation resource types are expected soon. The `infra/cdk/` directory contains a placeholder stack that manages everything except the MicroVM-specific calls (which use a Custom Resource wrapper). When native CFN support ships, swap the Custom Resource for the native construct.

## Local development

Every app runs locally without AWS:

```bash
cd apps/playground
pip install -r requirements.txt
marimo edit app.py

cd apps/code-runner
pip install -r requirements.txt
uvicorn main:app --port 8080

cd apps/pdf-generator
pip install -r requirements.txt
python main.py
```

## Cleanup

```bash
# Destroy a specific deployment
./destroy.sh my-deployment-name

# Or manually
aws lambda-microvms terminate-microvm --microvm-identifier MICROVM_ID --region eu-west-1
```
