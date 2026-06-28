#!/usr/bin/env python3
"""CDK app entry point. Deploy with: cdk deploy -c app_name=playground -c app_port=2718"""
import os
import aws_cdk as cdk
from stack import MicroVmStack

app = cdk.App()
app_name = app.node.try_get_context("app_name") or "playground"

MicroVmStack(app, f"MicroVM-{app_name}",
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION", "eu-west-1"),
    ),
)
app.synth()
