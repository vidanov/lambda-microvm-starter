#!/bin/bash
# deploy.sh — Deploy any app to a Lambda MicroVM with public CloudFront access
#
# Usage: ./deploy.sh <app-folder> [image-name]
# Example: ./deploy.sh apps/playground
#          ./deploy.sh apps/code-runner my-code-service
#
# Prerequisites: AWS CLI 2.35.10+, authenticated session

set -e

APP_DIR="${1:?Usage: ./deploy.sh <app-folder> [image-name]}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}/${APP_DIR}"

if [ ! -f "${APP_DIR}/Dockerfile" ]; then
  echo "ERROR: No Dockerfile found in ${APP_DIR}"
  exit 1
fi

REGION="eu-west-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
IMAGE_NAME="${2:-$(basename ${APP_DIR})}"
BUCKET="microvm-artifacts-${ACCOUNT_ID}-${REGION}"
APP_PORT=$(grep -m1 "^EXPOSE" "${APP_DIR}/Dockerfile" | awk '{print $2}')
APP_PORT="${APP_PORT:-8080}"

echo "╔══════════════════════════════════════╗"
echo "║   Lambda MicroVM Deploy             ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  App:     $(basename ${APP_DIR})"
echo "  Image:   ${IMAGE_NAME}"
echo "  Port:    ${APP_PORT}"
echo "  Region:  ${REGION}"
echo "  Account: ${ACCOUNT_ID}"
echo ""

# --- Step 1: S3 Bucket ---
echo "[1/7] S3 bucket..."
aws s3api create-bucket --bucket ${BUCKET} \
  --create-bucket-configuration LocationConstraint=${REGION} \
  --region ${REGION} 2>/dev/null || true

# --- Step 2: IAM Roles ---
echo "[2/7] IAM roles..."
TRUST='{
  "Version":"2012-10-17",
  "Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole","Condition":{"StringEquals":{"aws:SourceAccount":"'${ACCOUNT_ID}'"}}}]
}'
EDGE_TRUST='{
  "Version":"2012-10-17",
  "Statement":[{"Effect":"Allow","Principal":{"Service":["lambda.amazonaws.com","edgelambda.amazonaws.com"]},"Action":"sts:AssumeRole"}]
}'

aws iam create-role --role-name MicroVMBuildRole --assume-role-policy-document "${TRUST}" 2>/dev/null || true
aws iam put-role-policy --role-name MicroVMBuildRole --policy-name P --policy-document '{
  "Version":"2012-10-17","Statement":[
    {"Effect":"Allow","Action":"s3:GetObject","Resource":"arn:aws:s3:::'${BUCKET}'/*"},
    {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],"Resource":"*"}
  ]}'

aws iam create-role --role-name MicroVMExecutionRole --assume-role-policy-document "${TRUST}" 2>/dev/null || true
aws iam put-role-policy --role-name MicroVMExecutionRole --policy-name P --policy-document '{
  "Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],"Resource":"*"}]}'

aws iam create-role --role-name MicroVMEdgeLambdaRole --assume-role-policy-document "${EDGE_TRUST}" 2>/dev/null || true
aws iam put-role-policy --role-name MicroVMEdgeLambdaRole --policy-name P --policy-document '{
  "Version":"2012-10-17","Statement":[
    {"Effect":"Allow","Action":["logs:CreateLogGroup","logs:CreateLogStream","logs:PutLogEvents"],"Resource":"*"},
    {"Effect":"Allow","Action":"lambda:CreateMicrovmAuthToken","Resource":"*"}
  ]}'

sleep 8

# --- Step 3: Package ---
echo "[3/7] Packaging ${APP_DIR}..."
WORK_DIR=$(mktemp -d)
cp -r "${APP_DIR}/"* "${WORK_DIR}/"
cd "${WORK_DIR}" && zip -r app.zip . -x '*.pyc' '__pycache__/*' 'venv/*' '.git/*'
aws s3 cp "${WORK_DIR}/app.zip" s3://${BUCKET}/images/${IMAGE_NAME}.zip --region ${REGION}

# --- Step 4: Build image ---
echo "[4/7] Building MicroVM image..."
aws lambda-microvms delete-microvm-image \
  --image-identifier arn:aws:lambda:${REGION}:${ACCOUNT_ID}:microvm-image:${IMAGE_NAME} \
  --region ${REGION} 2>/dev/null && echo "  Replacing existing image..." && sleep 60 || true

aws lambda-microvms create-microvm-image \
  --name ${IMAGE_NAME} \
  --base-image-arn arn:aws:lambda:${REGION}:aws:microvm-image:al2023-1 \
  --build-role-arn arn:aws:iam::${ACCOUNT_ID}:role/MicroVMBuildRole \
  --code-artifact '{"uri":"s3://'${BUCKET}'/images/'${IMAGE_NAME}'.zip"}' \
  --additional-os-capabilities '["ALL"]' \
  --resources '[{"minimumMemoryInMiB":4096}]' \
  --region ${REGION} > /dev/null

echo "  Building (this takes 2-4 minutes)..."
while true; do
  STATE=$(aws lambda-microvms get-microvm-image \
    --image-identifier arn:aws:lambda:${REGION}:${ACCOUNT_ID}:microvm-image:${IMAGE_NAME} \
    --region ${REGION} --query 'state' --output text 2>/dev/null)
  [ "$STATE" = "CREATED" ] && break
  [ "$STATE" = "CREATE_FAILED" ] && echo "  ERROR: Build failed. Check CloudWatch /aws/lambda-microvms/" && exit 1
  sleep 15
done
echo "  Image ready."

# --- Step 5: Run MicroVM ---
echo "[5/7] Launching MicroVM..."
RUN_OUT=$(aws lambda-microvms run-microvm \
  --image-identifier arn:aws:lambda:${REGION}:${ACCOUNT_ID}:microvm-image:${IMAGE_NAME} \
  --image-version 1.0 \
  --execution-role-arn arn:aws:iam::${ACCOUNT_ID}:role/MicroVMExecutionRole \
  --idle-policy '{"maxIdleDurationSeconds":1800,"suspendedDurationSeconds":28800,"autoResumeEnabled":true}' \
  --region ${REGION})

MICROVM_ID=$(echo $RUN_OUT | python3 -c "import json,sys; print(json.load(sys.stdin)['microvmId'])")
ENDPOINT=$(echo $RUN_OUT | python3 -c "import json,sys; print(json.load(sys.stdin)['endpoint'])")

while true; do
  S=$(aws lambda-microvms get-microvm --microvm-identifier ${MICROVM_ID} --region ${REGION} --query 'state' --output text)
  [ "$S" = "RUNNING" ] && break
  [ "$S" = "TERMINATED" ] && echo "  ERROR: MicroVM terminated. Check execution role." && exit 1
  sleep 3
done
echo "  Running: ${MICROVM_ID}"

# --- Step 6: Lambda@Edge ---
echo "[6/7] Deploying Lambda@Edge..."
EDGE_DIR=$(mktemp -d)
cat > ${EDGE_DIR}/lambda_function.py << PYEOF
import json, urllib.request, ssl, time
import botocore.session, botocore.auth, botocore.awsrequest
MICROVM_ID = "${MICROVM_ID}"
REGION = "${REGION}"
PORT = "${APP_PORT}"
_c = {"t": None, "e": 0}
def get_token():
    if time.time() < _c["e"] - 120: return _c["t"]
    s = botocore.session.get_session()
    cr = s.get_credentials().get_frozen_credentials()
    url = f"https://lambda.{REGION}.amazonaws.com/2025-09-09/microvms/{MICROVM_ID}/auth-token"
    b = json.dumps({"expirationInMinutes":60,"allowedPorts":[{"allPorts":{}}]}).encode()
    r = botocore.awsrequest.AWSRequest(method="POST",url=url,data=b,headers={"Content-Type":"application/json"})
    botocore.auth.SigV4Auth(cr,"lambda",REGION).add_auth(r)
    with urllib.request.urlopen(urllib.request.Request(url,data=b,method="POST",headers=dict(r.headers)),context=ssl.create_default_context(),timeout=4) as resp:
        _c["t"]=json.loads(resp.read())["authToken"]["X-aws-proxy-auth"]; _c["e"]=time.time()+3600
    return _c["t"]
def handler(event, context):
    req = event["Records"][0]["cf"]["request"]
    t = get_token()
    req["headers"]["x-aws-proxy-auth"]=[{"key":"X-aws-proxy-auth","value":t}]
    req["headers"]["x-aws-proxy-port"]=[{"key":"X-aws-proxy-port","value":PORT}]
    return req
PYEOF

cd ${EDGE_DIR} && zip edge.zip lambda_function.py
aws lambda create-function --function-name microvm-edge-auth --runtime python3.12 \
  --handler lambda_function.handler --role arn:aws:iam::${ACCOUNT_ID}:role/MicroVMEdgeLambdaRole \
  --zip-file fileb://${EDGE_DIR}/edge.zip --timeout 5 --memory-size 256 \
  --region us-east-1 2>/dev/null || \
aws lambda update-function-code --function-name microvm-edge-auth \
  --zip-file fileb://${EDGE_DIR}/edge.zip --region us-east-1 > /dev/null

sleep 3
EDGE_ARN=$(aws lambda publish-version --function-name microvm-edge-auth --region us-east-1 --query 'FunctionArn' --output text)

# --- Step 7: CloudFront ---
echo "[7/7] CloudFront distribution..."
cat > /tmp/cf-config.json << EOF
{
  "CallerReference": "${IMAGE_NAME}-$(date +%s)",
  "Comment": "MicroVM: ${IMAGE_NAME}",
  "Enabled": true,
  "Origins": {"Quantity":1,"Items":[{
    "Id":"microvm","DomainName":"${ENDPOINT}",
    "CustomOriginConfig":{"HTTPPort":80,"HTTPSPort":443,"OriginProtocolPolicy":"https-only","OriginSslProtocols":{"Quantity":1,"Items":["TLSv1.2"]}}
  }]},
  "DefaultCacheBehavior": {
    "TargetOriginId":"microvm","ViewerProtocolPolicy":"redirect-to-https",
    "AllowedMethods":{"Quantity":7,"Items":["GET","HEAD","OPTIONS","PUT","POST","PATCH","DELETE"],"CachedMethods":{"Quantity":2,"Items":["GET","HEAD"]}},
    "CachePolicyId":"4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
    "OriginRequestPolicyId":"b689b0a8-53d0-40ab-baf2-68738e2966ac",
    "LambdaFunctionAssociations":{"Quantity":1,"Items":[{"LambdaFunctionARN":"${EDGE_ARN}","EventType":"origin-request","IncludeBody":true}]},
    "Compress":true
  },
  "CacheBehaviors": {"Quantity":1,"Items":[{
    "PathPattern":"/assets/*","TargetOriginId":"microvm","ViewerProtocolPolicy":"redirect-to-https",
    "AllowedMethods":{"Quantity":2,"Items":["GET","HEAD"],"CachedMethods":{"Quantity":2,"Items":["GET","HEAD"]}},
    "CachePolicyId":"658327ea-f89d-4fab-a63d-7e88639e58f6",
    "OriginRequestPolicyId":"b689b0a8-53d0-40ab-baf2-68738e2966ac",
    "LambdaFunctionAssociations":{"Quantity":1,"Items":[{"LambdaFunctionARN":"${EDGE_ARN}","EventType":"origin-request","IncludeBody":false}]},
    "Compress":true,"SmoothStreaming":false,"FieldLevelEncryptionId":""
  }]}
}
EOF

CF_OUT=$(aws cloudfront create-distribution --distribution-config file:///tmp/cf-config.json)
CF_ID=$(echo $CF_OUT | python3 -c "import json,sys; print(json.load(sys.stdin)['Distribution']['Id'])")
CF_DOMAIN=$(echo $CF_OUT | python3 -c "import json,sys; print(json.load(sys.stdin)['Distribution']['DomainName'])")

echo "  Waiting for CloudFront deployment..."
while true; do
  STATUS=$(aws cloudfront get-distribution --id ${CF_ID} --query 'Distribution.Status' --output text)
  [ "$STATUS" = "Deployed" ] && break
  sleep 20
done

# --- Output ---
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   DEPLOYED SUCCESSFULLY                         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  🌐 URL:          https://${CF_DOMAIN}/"
echo "  🖥️  MicroVM:      ${MICROVM_ID}"
echo "  📦 Image:        ${IMAGE_NAME}"
echo "  🌍 CloudFront:   ${CF_ID}"
echo ""
echo "  Auto-suspends after 30 min idle. Resumes on next request."
echo ""
echo "  Terminate:  ./destroy.sh ${IMAGE_NAME}"
echo ""

cat > "${SCRIPT_DIR}/deploy-output-${IMAGE_NAME}.json" << EOF
{
  "url": "https://${CF_DOMAIN}/",
  "microvmId": "${MICROVM_ID}",
  "endpoint": "${ENDPOINT}",
  "imageName": "${IMAGE_NAME}",
  "cloudfrontId": "${CF_ID}",
  "cloudfrontDomain": "${CF_DOMAIN}",
  "edgeArn": "${EDGE_ARN}",
  "port": "${APP_PORT}",
  "region": "${REGION}"
}
EOF
