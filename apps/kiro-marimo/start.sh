#!/bin/bash
# Sync notebooks from S3 on startup, start marimo

BUCKET="${NOTEBOOK_BUCKET:-}"
PREFIX="${NOTEBOOK_PREFIX:-notebooks}"

# Pull from S3 if bucket is configured
if [ -n "$BUCKET" ]; then
    aws s3 sync "s3://${BUCKET}/${PREFIX}/" /app/notebooks/ 2>/dev/null || true
    # Background sync every 60s
    while true; do sleep 60; aws s3 sync /app/notebooks/ "s3://${BUCKET}/${PREFIX}/" --quiet 2>/dev/null; done &
fi

# Start marimo in edit mode
exec marimo edit /app/notebooks/ --host 0.0.0.0 --port 2718 --headless --no-token
