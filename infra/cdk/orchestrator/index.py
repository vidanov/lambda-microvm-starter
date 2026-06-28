"""Custom resource: runs a MicroVM, updates Lambda@Edge code, publishes version."""
import json
import time
import zipfile
import io
import boto3
import cfnresponse

EDGE_TEMPLATE = '''import json,urllib.request,ssl,time,botocore.session,botocore.auth,botocore.awsrequest
M="{mid}";R="{region}";P="{port}"
_c={{"t":None,"e":0}}
def get_token():
 if time.time()<_c["e"]-120:return _c["t"]
 s=botocore.session.get_session();cr=s.get_credentials().get_frozen_credentials()
 u=f"https://lambda.{{R}}.amazonaws.com/2025-09-09/microvms/{{M}}/auth-token"
 b=json.dumps({{"expirationInMinutes":60,"allowedPorts":[{{"allPorts":{{}}}}]}}).encode()
 r=botocore.awsrequest.AWSRequest(method="POST",url=u,data=b,headers={{"Content-Type":"application/json"}})
 botocore.auth.SigV4Auth(cr,"lambda",R).add_auth(r)
 with urllib.request.urlopen(urllib.request.Request(u,data=b,method="POST",headers=dict(r.headers)),context=ssl.create_default_context(),timeout=4) as rp:
  _c["t"]=json.loads(rp.read())["authToken"]["X-aws-proxy-auth"];_c["e"]=time.time()+3600
 return _c["t"]
def handler(event,context):
 req=event["Records"][0]["cf"]["request"];t=get_token()
 req["headers"]["x-aws-proxy-auth"]=[{{"key":"X-aws-proxy-auth","value":t}}]
 req["headers"]["x-aws-proxy-port"]=[{{"key":"X-aws-proxy-port","value":P}}]
 return req
'''


def handler(event, context):
    try:
        props = event["ResourceProperties"]
        region = props["Region"]
        mv = boto3.client("lambda-microvms", region_name=region)
        lm = boto3.client("lambda", region_name=region)

        if event["RequestType"] == "Delete":
            mid = event.get("PhysicalResourceId", "")
            if mid.startswith("microvm-"):
                try:
                    mv.terminate_microvm(microvmIdentifier=mid)
                except Exception:
                    pass
            # Clean up edge function in us-east-1
            try:
                lm_us = boto3.client("lambda", region_name="us-east-1")
                lm_us.delete_function(FunctionName=props["EdgeFn"])
            except Exception:
                pass
            cfnresponse.send(event, context, cfnresponse.SUCCESS, {})
            return

        # 1. Run MicroVM
        resp = mv.run_microvm(
            imageIdentifier=props["ImageArn"],
            imageVersion="1.0",
            executionRoleArn=props["ExecRoleArn"],
            idlePolicy={
                "maxIdleDurationSeconds": 1800,
                "suspendedDurationSeconds": 28800,
                "autoResumeEnabled": True,
            },
        )
        mid = resp["microvmId"]
        endpoint = resp["endpoint"]

        # 2. Wait for RUNNING
        for _ in range(120):
            state = mv.get_microvm(microvmIdentifier=mid)["state"]
            if state == "RUNNING":
                break
            if state == "TERMINATED":
                raise Exception("MicroVM terminated unexpectedly")
            time.sleep(3)
        else:
            raise Exception("Timeout waiting for MicroVM to start")

        # 3. Update edge function (us-east-1 for Lambda@Edge) with MicroVM ID baked in
        code = EDGE_TEMPLATE.format(mid=mid, region=region, port=props["Port"])
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("index.py", code)
        buf.seek(0)
        zip_bytes = buf.read()

        lm_edge = boto3.client("lambda", region_name="us-east-1")
        edge_fn = props["EdgeFn"]

        # Create or update the edge function in us-east-1
        try:
            lm_edge.get_function(FunctionName=edge_fn)
            lm_edge.update_function_code(FunctionName=edge_fn, ZipFile=zip_bytes)
        except lm_edge.exceptions.ResourceNotFoundException:
            lm_edge.create_function(
                FunctionName=edge_fn,
                Runtime="python3.12",
                Role=props["EdgeRoleArn"],
                Handler="index.handler",
                Code={"ZipFile": zip_bytes},
                Timeout=5,
                MemorySize=256,
            )

        # 4. Wait for update to complete, then publish version
        for _ in range(30):
            time.sleep(3)
            status = lm_edge.get_function_configuration(FunctionName=edge_fn)
            if status.get("LastUpdateStatus", "Successful") == "Successful" and status.get("State") == "Active":
                break
        ver = lm_edge.publish_version(FunctionName=edge_fn)

        cfnresponse.send(event, context, cfnresponse.SUCCESS, {
            "MicrovmId": mid,
            "Endpoint": endpoint,
            "EdgeVersionArn": ver["FunctionArn"],
        }, physicalResourceId=mid, reason="OK")

    except Exception as e:
        msg = str(e)[:200]
        print(f"Error: {msg}")
        cfnresponse.send(event, context, cfnresponse.FAILED, {"Error": msg})
