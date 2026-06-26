#!/bin/bash
# example-client.sh — Demonstrates calling the PDF generator after deployment
#
# Deploy first:  ./deploy.sh apps/pdf-generator --private
# Then run this: ./apps/pdf-generator/example-client.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT="${SCRIPT_DIR}/deploy-output-pdf-generator.json"

if [ ! -f "$OUTPUT" ]; then
  echo "Deploy first: ./deploy.sh apps/pdf-generator --private"
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
echo "=== Generating invoice PDF ==="
curl -s -X POST "https://${ENDPOINT}/invoice" \
  -H "X-aws-proxy-auth: $TOKEN" \
  -H "X-aws-proxy-port: $PORT" \
  -H "Content-Type: application/json" \
  -d '{
    "company": "MicroVM Corp",
    "recipient": "Acme Inc.",
    "invoice_number": "INV-2026-042",
    "items": [
      {"description": "MicroVM compute (4 vCPU, 80 hrs)", "quantity": 80, "unit_price": 0.11},
      {"description": "Snapshot storage (2 GB, 30 days)", "quantity": 1, "unit_price": 0.19},
      {"description": "CloudFront data transfer", "quantity": 1, "unit_price": 0.85}
    ],
    "notes": "Auto-generated from Lambda MicroVM usage metrics."
  }' --output invoice.pdf

echo "  Saved: invoice.pdf ($(wc -c < invoice.pdf) bytes)"
echo "  Open:  open invoice.pdf"
