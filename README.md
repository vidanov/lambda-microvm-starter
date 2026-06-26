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

# Deploy the interactive playground
./deploy.sh apps/playground

# Deploy the code runner
./deploy.sh apps/code-runner

# Deploy with a custom name
./deploy.sh apps/pdf-generator my-pdf-service
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

## How apps work

Each app is a folder with:
- `Dockerfile` — builds on `public.ecr.aws/lambda/microvms:al2023-minimal`
- Your application code (Python, Node, Go, whatever runs in a container)
- Optional `requirements.txt` for Python apps

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

## Costs (eu-west-1, Graviton)

| Usage pattern | 2 vCPU / 4 GB | 4 vCPU / 8 GB |
|---------------|---------------|---------------|
| Always-on 24/7 | ~$96/mo | ~$191/mo |
| 4 hours/day, 20 days | ~$11/mo | ~$22/mo |
| Bursty (auto-suspend) | Pay only active seconds | + $0 when suspended |
| CloudFront + Edge | ~$0-1/mo | ~$0-1/mo |

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
