"""Lambda@Edge origin-request: injects MicroVM auth token.

This file is a reference. The deploy script generates the actual function
with MICROVM_ID, REGION, and PORT baked in at deploy time.
"""
import json
import urllib.request
import ssl
import time
import botocore.session
import botocore.auth
import botocore.awsrequest

# These are replaced by deploy.sh at deploy time
MICROVM_ID = "PLACEHOLDER"
REGION = "eu-west-1"
PORT = "8080"

_cache = {"token": None, "expires": 0}


def get_token():
    if time.time() < _cache["expires"] - 120:
        return _cache["token"]

    session = botocore.session.get_session()
    credentials = session.get_credentials().get_frozen_credentials()

    url = f"https://lambda.{REGION}.amazonaws.com/2025-09-09/microvms/{MICROVM_ID}/auth-token"
    body = json.dumps({"expirationInMinutes": 60, "allowedPorts": [{"allPorts": {}}]}).encode()

    request = botocore.awsrequest.AWSRequest(
        method="POST", url=url, data=body,
        headers={"Content-Type": "application/json"}
    )
    botocore.auth.SigV4Auth(credentials, "lambda", REGION).add_auth(request)

    req = urllib.request.Request(url, data=body, method="POST", headers=dict(request.headers))
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=4) as resp:
        data = json.loads(resp.read())
        _cache["token"] = data["authToken"]["X-aws-proxy-auth"]
        _cache["expires"] = time.time() + 3600

    return _cache["token"]


def handler(event, context):
    request = event["Records"][0]["cf"]["request"]
    token = get_token()
    request["headers"]["x-aws-proxy-auth"] = [{"key": "X-aws-proxy-auth", "value": token}]
    request["headers"]["x-aws-proxy-port"] = [{"key": "X-aws-proxy-port", "value": PORT}]
    return request
