#!/bin/bash
# Install orchestrator Lambda dependencies before CDK deploy.
# Run this once, or after changing requirements.
set -e
cd "$(dirname "$0")"

echo "Installing boto3 + botocore..."
pip install boto3 botocore -t . --upgrade -q

echo "Copying lambda-microvms service model..."
AWS_CLI_BOTOCORE=$(find /usr/local/bin/../aws-cli -path "*/botocore/data" -type d 2>/dev/null | head -1)
if [ -z "$AWS_CLI_BOTOCORE" ]; then
  AWS_CLI_BOTOCORE=$(find "$(which aws | xargs dirname)/.." -path "*/botocore/data" -type d 2>/dev/null | head -1)
fi

if [ -n "$AWS_CLI_BOTOCORE" ] && [ -d "$AWS_CLI_BOTOCORE/lambda-microvms" ]; then
  cp -r "$AWS_CLI_BOTOCORE/lambda-microvms" botocore/data/
  echo "  Copied from $AWS_CLI_BOTOCORE/lambda-microvms"
else
  echo "  WARNING: lambda-microvms service model not found in AWS CLI."
  echo "  Ensure AWS CLI 2.35.10+ is installed."
  exit 1
fi

echo "Cleaning up..."
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true

echo "Done. $(du -sh . | cut -f1) total."
