#!/bin/bash
# example-client.sh — Demonstrates the Shape-governed agent API
#
# Deploy first:  ./deploy.sh apps/shape-agent --private
# Then run this: ./apps/shape-agent/example-client.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT="${SCRIPT_DIR}/deploy-output-shape-agent.json"

if [ ! -f "$OUTPUT" ]; then
  echo "Deploy first: ./deploy.sh apps/shape-agent --private"
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

H1="X-aws-proxy-auth: $TOKEN"
H2="X-aws-proxy-port: $PORT"
BASE="https://${ENDPOINT}"

echo ""
echo "=== 1. EXPLORE: lookup customer (READ tool, allowed) ==="
curl -s -X POST "$BASE/agent/explore" -H "$H1" -H "$H2" \
  -H "Content-Type: application/json" \
  -d '{"tool": "lookup_customer"}' | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  Result: {d.get(\"result\")}'); print(f'  Budget: {d[\"status\"][\"budget\"][\"pct\"]:.0f}%')"

echo ""
echo "=== 2. EXPLORE: try to send email (IRREVERSIBLE, should be BLOCKED) ==="
curl -s -X POST "$BASE/agent/explore" -H "$H1" -H "$H2" \
  -H "Content-Type: application/json" \
  -d '{"tool": "send_email", "args": {"to": "x@y.com"}}' | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  Error: {d.get(\"error\", \"none\")}')"

echo ""
echo "=== 3. COMMIT: send email (IRREVERSIBLE, allowed in commit phase) ==="
curl -s -X POST "$BASE/agent/commit" -H "$H1" -H "$H2" \
  -H "Content-Type: application/json" \
  -d '{"tool": "send_email", "args": {"to": "customer@acme.com"}}' | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'  Result: {d.get(\"result\")}'); print(f'  Budget: {d[\"status\"][\"budget\"][\"pct\"]:.0f}%')"

echo ""
echo "=== 4. Agent status (full audit trail) ==="
curl -s "$BASE/agent/status" -H "$H1" -H "$H2" | python3 -m json.tool

echo ""
echo "=== 5. Reset agent ==="
curl -s -X POST "$BASE/agent/reset" -H "$H1" -H "$H2" | python3 -c "import json,sys; print(f'  Reset: {json.load(sys.stdin)[\"reset\"]}')"
