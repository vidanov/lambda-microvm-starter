#!/bin/bash
# destroy.sh — Tear down a MicroVM deployment
# Usage: ./destroy.sh <image-name>

set -e
IMAGE_NAME="${1:?Usage: ./destroy.sh <image-name>}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="eu-west-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

OUTPUT_FILE="${SCRIPT_DIR}/deploy-output-${IMAGE_NAME}.json"
if [ ! -f "$OUTPUT_FILE" ]; then
  echo "No deploy output found for '${IMAGE_NAME}'. Looking up resources..."
  MICROVM_ID=""
  CF_ID=""
else
  MICROVM_ID=$(python3 -c "import json; print(json.load(open('${OUTPUT_FILE}'))['microvmId'])")
  CF_ID=$(python3 -c "import json; print(json.load(open('${OUTPUT_FILE}'))['cloudfrontId'])")
fi

echo "Destroying: ${IMAGE_NAME}"

# Terminate MicroVM
if [ -n "$MICROVM_ID" ]; then
  echo "  Terminating MicroVM ${MICROVM_ID}..."
  aws lambda-microvms terminate-microvm --microvm-identifier ${MICROVM_ID} --region ${REGION} 2>/dev/null || true
  sleep 5
fi

# Delete image
echo "  Deleting MicroVM image..."
aws lambda-microvms delete-microvm-image \
  --image-identifier arn:aws:lambda:${REGION}:${ACCOUNT_ID}:microvm-image:${IMAGE_NAME} \
  --region ${REGION} 2>/dev/null || true

# Disable + delete CloudFront
if [ -n "$CF_ID" ]; then
  echo "  Disabling CloudFront ${CF_ID}..."
  ETAG=$(aws cloudfront get-distribution-config --id ${CF_ID} --query 'ETag' --output text 2>/dev/null || echo "")
  if [ -n "$ETAG" ]; then
    aws cloudfront get-distribution-config --id ${CF_ID} --query 'DistributionConfig' > /tmp/cf-dis.json
    python3 -c "import json; c=json.load(open('/tmp/cf-dis.json')); c['Enabled']=False; json.dump(c,open('/tmp/cf-dis.json','w'))"
    aws cloudfront update-distribution --id ${CF_ID} --distribution-config file:///tmp/cf-dis.json --if-match "$ETAG" > /dev/null 2>&1 || true
    echo "  Waiting for CloudFront to disable (1-2 min)..."
    sleep 90
    ETAG=$(aws cloudfront get-distribution --id ${CF_ID} --query 'ETag' --output text)
    aws cloudfront delete-distribution --id ${CF_ID} --if-match "$ETAG" 2>/dev/null || echo "  CloudFront may need more time to delete."
  fi
fi

rm -f "${OUTPUT_FILE}"
echo "Done."
