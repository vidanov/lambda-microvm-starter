#!/bin/bash
# example-client.sh — Demonstrates calling the code-runner after deployment
#
# Deploy first:  ./deploy.sh apps/code-runner --private
# Then run this: ./apps/code-runner/example-client.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT="${SCRIPT_DIR}/deploy-output-code-runner.json"

if [ ! -f "$OUTPUT" ]; then
  echo "Deploy first: ./deploy.sh apps/code-runner --private"
  exit 1
fi

MICROVM_ID=$(python3 -c "import json; print(json.load(open('$OUTPUT'))['microvmId'])")
ENDPOINT=$(python3 -c "import json; print(json.load(open('$OUTPUT'))['endpoint'])")
PORT=$(python3 -c "import json; print(json.load(open('$OUTPUT'))['port'])")
REGION=$(python3 -c "import json; print(json.load(open('$OUTPUT'))['region'])")

echo "Minting auth token..."
TOKEN=$(aws lambda-microvms create-microvm-auth-token \
  --microvm-identifier ${MICROVM_ID} \
  --expiration-in-minutes 60 \
  --allowed-ports "[{\"port\":${PORT}}]" \
  --region ${REGION} \
  --query 'authToken."X-aws-proxy-auth"' --output text)

echo ""
echo "=== Running: print(sum(range(100))) ==="
curl -s -X POST "https://${ENDPOINT}/run" \
  -H "X-aws-proxy-auth: $TOKEN" \
  -H "X-aws-proxy-port: $PORT" \
  -H "Content-Type: application/json" \
  -d '{"code": "print(sum(range(100)))", "timeout": 5}' | python3 -m json.tool

echo ""
echo "=== Running: fibonacci ==="
curl -s -X POST "https://${ENDPOINT}/run" \
  -H "X-aws-proxy-auth: $TOKEN" \
  -H "X-aws-proxy-port: $PORT" \
  -H "Content-Type: application/json" \
  -d '{"code": "def fib(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a+b\n    return a\nprint(fib(50))", "timeout": 5}' | python3 -m json.tool

echo ""
echo "=== Running: timeout test ==="
curl -s -X POST "https://${ENDPOINT}/run" \
  -H "X-aws-proxy-auth: $TOKEN" \
  -H "X-aws-proxy-port: $PORT" \
  -H "Content-Type: application/json" \
  -d '{"code": "import time; time.sleep(10)", "timeout": 2}' | python3 -m json.tool
