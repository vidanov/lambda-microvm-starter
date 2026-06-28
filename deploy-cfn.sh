#!/bin/bash
# deploy-cfn.sh — Deploy MicroVM image via CloudFormation
#
# Usage: ./deploy-cfn.sh <app-folder> [--stack-name NAME]
# Example: ./deploy-cfn.sh apps/playground
#          ./deploy-cfn.sh apps/code-runner --stack-name my-runner
#
# This creates the MicroVM image as a CloudFormation-managed resource.
# Running MicroVMs are still launched via CLI (they're ephemeral per-user resources).

set -e

# Parse args
STACK_NAME=""
POSITIONAL=()
for arg in "$@"; do
  case $arg in
    --stack-name) STACK_NAME="$2"; shift ;;
    *) POSITIONAL+=("$arg") ;;
  esac
  shift 2>/dev/null || true
done

APP_DIR="${POSITIONAL[0]:?Usage: ./deploy-cfn.sh <app-folder> [--stack-name NAME]}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${SCRIPT_DIR}/${APP_DIR}"

if [ ! -f "${APP_DIR}/Dockerfile" ]; then
  echo "ERROR: No Dockerfile found in ${APP_DIR}"
  exit 1
fi

REGION="eu-west-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
APP_NAME=$(basename ${APP_DIR})
STACK_NAME="${STACK_NAME:-microvm-${APP_NAME}}"
BUCKET="microvm-artifacts-${ACCOUNT_ID}-${REGION}"

echo "╔══════════════════════════════════════╗"
echo "║   Lambda MicroVM Deploy (CFN)       ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  App:     ${APP_NAME}"
echo "  Stack:   ${STACK_NAME}"
echo "  Region:  ${REGION}"
echo ""

# --- Step 1: Ensure S3 bucket exists ---
echo "[1/4] S3 bucket..."
aws s3api create-bucket --bucket ${BUCKET} \
  --create-bucket-configuration LocationConstraint=${REGION} \
  --region ${REGION} 2>/dev/null || true

# --- Step 2: Package and upload code ---
echo "[2/4] Packaging ${APP_DIR}..."
WORK_DIR=$(mktemp -d)
cp -r "${APP_DIR}/"* "${WORK_DIR}/"
cd "${WORK_DIR}" && zip -r app.zip . -x '*.pyc' '__pycache__/*' 'venv/*' '.git/*'
aws s3 cp "${WORK_DIR}/app.zip" s3://${BUCKET}/images/${APP_NAME}.zip --region ${REGION}

# --- Step 3: Deploy CloudFormation stack ---
echo "[3/4] Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file "${SCRIPT_DIR}/infra/cfn/microvm-image.yaml" \
  --stack-name ${STACK_NAME} \
  --parameter-overrides AppName=${APP_NAME} ArtifactBucket=${BUCKET} \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ${REGION}

# --- Step 4: Get outputs ---
echo "[4/4] Getting stack outputs..."
IMAGE_ARN=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`ImageArn`].OutputValue' --output text)
EXEC_ROLE=$(aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`ExecutionRoleArn`].OutputValue' --output text)

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║   IMAGE DEPLOYED (CloudFormation)               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  📦 Image ARN:   ${IMAGE_ARN}"
echo "  🔑 Exec Role:   ${EXEC_ROLE}"
echo "  📁 Stack:       ${STACK_NAME}"
echo ""
echo "  Launch a MicroVM from this image:"
echo "  aws lambda-microvms run-microvm \\"
echo "    --image-identifier ${IMAGE_ARN} \\"
echo "    --execution-role-arn ${EXEC_ROLE} \\"
echo "    --region ${REGION}"
echo ""
echo "  Tear down:  aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${REGION}"
echo ""
