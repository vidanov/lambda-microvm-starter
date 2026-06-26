---
created: 2026-06-25
tags: [aws, microvm, lambda, troubleshooting, reference]
---

# Lambda MicroVMs: difficulties and solutions

Everything we hit while making a marimo notebook run publicly via Lambda MicroVMs + CloudFront.

## 1. AWS CLI version too old

**Symptom**: `Found invalid choice 'lambda-microvms'`

**Cause**: The `lambda-microvms` CLI subcommand was added in AWS CLI 2.35.10. Older versions don't have it.

**Fix**:
```bash
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o /tmp/AWSCLIV2.pkg
sudo installer -pkg /tmp/AWSCLIV2.pkg -target /
```

## 2. IAM trust policy: "We were unable to assume the role provided"

**Symptom**: Image build or MicroVM run fails immediately with role assume error.

**Cause**: The `ArnLike` condition in the trust policy references `microvm-image/*`, but the service can't satisfy this condition before the resource exists.

**Fix**: Use a simpler trust policy with only `SourceAccount`:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole",
    "Condition": {
      "StringEquals": {"aws:SourceAccount": "ACCOUNT_ID"}
    }
  }]
}
```

Applies to both build role AND execution role.

## 3. Image deletion is slow

**Symptom**: `A MicroVM image with the name 'X' already exists` when trying to recreate.

**Cause**: Deletion takes 30-60 seconds. The name is reserved until fully deleted.

**Fix**: Wait and retry. Poll with:
```bash
aws lambda-microvms get-microvm-image --image-identifier ARN --region REGION --query 'state'
```
When it returns `ResourceNotFoundException`, the name is free.

## 4. Cannot delete image with running MicroVMs

**Symptom**: `Cannot delete MicroVM image with running MicroVMs`

**Fix**: Terminate all MicroVMs first, wait for termination, then delete image.

## 5. /proc permission errors

**Symptom**: `[Errno 1] Operation not permitted: '/proc/self/fd/...'`

**Cause**: MicroVMs run with restricted Linux capabilities by default. Some Python libraries (psutil, etc.) read /proc.

**Fix**: Add `--additional-os-capabilities '["ALL"]'` when creating the image:
```bash
aws lambda-microvms create-microvm-image ... --additional-os-capabilities '["ALL"]'
```

## 6. Marimo "kernel not found"

**Symptom**: Page loads but shows "kernel not found" or cells don't execute.

**Cause**: Marimo's kernel runs over WebSocket. If the WebSocket connection can't be established (proxy doesn't support it, or no session exists yet), the kernel never starts.

**Fix**: Ensure WebSocket passthrough works. With CloudFront, this works natively. With a local proxy, use `ThreadingMixIn` or `aiohttp` with explicit WS relay.

## 7. Marimo package install fails: "no such option: --python"

**Symptom**: Marimo's built-in package manager fails with pip errors.

**Cause**: AL2023 ships Python 3.9 with an older pip that doesn't support `--python` flag. Marimo's package manager assumes a newer pip.

**Fix**: Pre-install all needed packages in the Dockerfile. Don't rely on runtime install:
```dockerfile
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN pip install --no-cache-dir marimo pandas numpy matplotlib
```

## 8. Auth token required on every request (no public endpoint)

**Symptom**: MicroVM endpoint returns 403 without `X-aws-proxy-auth` header.

**Cause**: By design. All MicroVM ingress is authenticated. No opt-out.

**Fix**: Use CloudFront + Lambda@Edge to inject the token transparently. See architecture below.

## 9. Lambda Function URL returns 403 (Forbidden)

**Symptom**: Function URL with `AuthType: NONE` still returns 403 `AccessDeniedException`.

**Cause**: Organization-level Resource Control Policy (RCP) or SCP blocking unauthenticated Lambda Function URLs.

**Fix**: Use API Gateway HTTP API or CloudFront instead. These aren't typically blocked.

## 10. API Gateway HTTP API doesn't proxy WebSocket

**Symptom**: Page loads via API GW but kernel/interactive features don't work.

**Cause**: HTTP APIs don't support WebSocket passthrough. The separate WebSocket API type can't do transparent relay either (Lambda is stateless between messages).

**Fix**: Use CloudFront, which passes WebSocket through natively to the origin.

## 11. CloudFront "Token authentication failed"

**Symptom**: CloudFront reaches MicroVM but auth is rejected.

**Cause**: Default origin request policy (`AllViewer`) forwards the CloudFront domain as the `Host` header. The MicroVM rejects requests where Host doesn't match its own endpoint domain.

**Fix**: Use `AllViewerExceptHostHeader` origin request policy:
```
OriginRequestPolicyId: b689b0a8-53d0-40ab-baf2-68738e2966ac
```
CloudFront will send the origin's own domain as Host.

## 12. Lambda@Edge boto3 doesn't have lambda-microvms service

**Symptom**: `UnknownServiceError: Unknown service: 'lambda-microvms'`

**Cause**: Lambda runtime's bundled boto3/botocore doesn't have the new service model yet.

**Fix**: Use raw HTTP with sigv4 signing via botocore:
```python
url = f"https://lambda.{REGION}.amazonaws.com/2025-09-09/microvms/{MICROVM_ID}/auth-token"
request = botocore.awsrequest.AWSRequest(method="POST", url=url, data=body, headers={"Content-Type": "application/json"})
botocore.auth.SigV4Auth(credentials, "lambda", REGION).add_auth(request)
```

Service name for signing is `lambda` (not `lambda-microvms`). API path prefix is `/2025-09-09/`.

## 13. No CDK/CloudFormation support

**Symptom**: No `AWS::Lambda::MicrovmImage` resource type exists.

**Cause**: Service launched June 22, 2026. CloudFormation support typically follows weeks later.

**Fix**: Use CLI/SDK directly. Use CDK for supporting resources (S3, IAM, CloudFront) and CLI for MicroVM-specific calls.

---

## Working architecture

```
Browser → CloudFront (d3hduptaclaf0s.cloudfront.net)
            ↓ origin-request
         Lambda@Edge (us-east-1, injects X-aws-proxy-auth + X-aws-proxy-port)
            ↓
         MicroVM endpoint (eu-west-1, Firecracker, 8GB/4vCPU)
            ↓
         marimo (port 2718)
```

**Key settings:**
- CloudFront cache policy: `CachingDisabled` (4135ea2d-6df8-44a3-9df3-4b5a84be39ad)
- Origin request policy: `AllViewerExceptHostHeader` (b689b0a8-53d0-40ab-baf2-68738e2966ac)
- Lambda@Edge event: `origin-request` with `IncludeBody: true`
- MicroVM idle policy: auto-suspend 30 min, auto-resume on traffic, 8hr suspended max

**Monthly cost (light personal use):**
- MicroVM compute (4h/day active): ~$40
- MicroVM suspended storage: ~$0.16
- CloudFront: $0 (free tier)
- Lambda@Edge: < $0.01
- Total: ~$40/month active use, ~$0 when idle

---

## Resources created

| Resource | Region | Identifier |
|----------|--------|-----------|
| S3 bucket | eu-west-1 | microvm-artifacts-791454908090-eu-west-1 |
| IAM role (build) | global | MicroVMBuildRole |
| IAM role (execution) | global | MicroVMExecutionRole |
| IAM role (edge) | global | MicroVMEdgeLambdaRole |
| IAM role (proxy lambda) | global | MicroVMProxyLambdaRole |
| MicroVM image | eu-west-1 | marimo-notebook |
| Lambda@Edge | us-east-1 | microvm-edge-auth |
| Lambda (proxy, unused) | eu-west-1 | microvm-proxy |
| API Gateway (unused) | eu-west-1 | psnzh87w0h |
| CloudFront | global | EQ2B6UB0ABXWX (d3hduptaclaf0s.cloudfront.net) |
