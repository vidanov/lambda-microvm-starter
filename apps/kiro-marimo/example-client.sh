#!/bin/bash
# Example: deploy kiro-marimo with S3 notebook persistence
#
# Usage:
#   ./deploy.sh apps/kiro-marimo
#
# For S3 persistence, set environment variables when running the MicroVM:
#
#   aws lambda-microvms run-microvm \
#     --image-identifier kiro-marimo \
#     --environment-variables '{"NOTEBOOK_BUCKET":"your-bucket","NOTEBOOK_PREFIX":"notebooks"}' \
#     ...
#
# The MicroVM's execution role needs:
#   s3:GetObject, s3:PutObject, s3:ListBucket on your bucket
#
# IAM policy to attach to the runtime role:
# {
#   "Effect": "Allow",
#   "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket", "s3:DeleteObject"],
#   "Resource": [
#     "arn:aws:s3:::your-bucket",
#     "arn:aws:s3:::your-bucket/*"
#   ]
# }
#
# Once running, open the marimo editor in your browser.
# Use Kiro CLI via shell access to create new notebooks:
#
#   kiro chat "Create a marimo notebook that analyzes CSV files from S3"
#
# The notebook will appear in marimo's file browser automatically.

echo "Deploy with: ./deploy.sh apps/kiro-marimo"
echo ""
echo "To add S3 persistence, modify the run-microvm call in deploy.sh to include:"
echo '  --environment-variables {"NOTEBOOK_BUCKET":"your-bucket","NOTEBOOK_PREFIX":"notebooks"}'
