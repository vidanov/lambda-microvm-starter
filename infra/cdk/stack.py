"""CDK stack: one-command Lambda MicroVM deploy with public CloudFront access.

Usage:
    cd infra/cdk && pip install aws-cdk-lib constructs

    # Build orchestrator dependencies (once)
    ./orchestrator/build.sh

    # Upload app code first
    aws s3 cp app.zip s3://microvm-artifacts-ACCT-eu-west-1/images/playground.zip

    # Deploy everything: image build → run MicroVM → CloudFront
    cdk deploy -c app_name=playground -c app_port=2718 --profile YOUR_PROFILE
"""

from aws_cdk import (
    Stack, CfnOutput, CfnResource, Duration, CustomResource, Fn,
    aws_s3 as s3, aws_iam as iam, aws_lambda as lambda_,
    aws_cloudfront as cf,
)
from constructs import Construct
import os


class MicroVmStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        app_name = self.node.try_get_context("app_name") or "playground"
        memory_mib = int(self.node.try_get_context("memory") or "4096")
        app_port = self.node.try_get_context("app_port") or "8080"

        # --- S3 bucket (import existing) ---
        bucket_name = f"microvm-artifacts-{self.account}-{self.region}"
        bucket = s3.Bucket.from_bucket_name(self, "Artifacts", bucket_name)

        # --- IAM roles ---
        build_role = iam.Role(self, "BuildRole",
            role_name=f"MicroVMBuildRole-{app_name}",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        bucket.grant_read(build_role)
        build_role.add_to_policy(iam.PolicyStatement(
            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            resources=["*"],
        ))

        exec_role = iam.Role(self, "ExecRole",
            role_name=f"MicroVMExecRole-{app_name}",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )
        exec_role.add_to_policy(iam.PolicyStatement(
            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            resources=["*"],
        ))

        edge_role = iam.Role(self, "EdgeRole",
            role_name=f"MicroVMEdge-{app_name}",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("lambda.amazonaws.com"),
                iam.ServicePrincipal("edgelambda.amazonaws.com"),
            ),
        )
        edge_role.add_to_policy(iam.PolicyStatement(
            actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
            resources=["*"],
        ))
        edge_role.add_to_policy(iam.PolicyStatement(
            actions=["lambda:CreateMicrovmAuthToken"],
            resources=["*"],
        ))

        # --- MicroVM Image ---
        image = CfnResource(self, "Image",
            type="AWS::Lambda::MicrovmImage",
            properties={
                "Name": app_name,
                "Description": f"MicroVM image for {app_name}",
                "BaseImageArn": f"arn:aws:lambda:{self.region}:aws:microvm-image:al2023-1",
                "BaseImageVersion": "0",
                "BuildRoleArn": build_role.role_arn,
                "CodeArtifact": {"Uri": f"s3://{bucket_name}/images/{app_name}.zip"},
                "AdditionalOsCapabilities": ["ALL"],
                "CpuConfigurations": [{"Architecture": "ARM_64"}],
                "Resources": [{"MinimumMemoryInMiB": memory_mib}],
                "EgressNetworkConnectors": [],
                "EnvironmentVariables": [],
                "Hooks": {},
                "Logging": {"CloudWatch": {}},
            },
        )
        image.add_dependency(build_role.node.default_child)

        # --- Placeholder Edge function removed ---
        # The orchestrator creates the edge function in us-east-1 (Lambda@Edge requirement)
        edge_fn_name = f"microvm-edge-{app_name}"

        # --- Orchestrator: run MicroVM + update edge + publish version ---
        # Code is loaded from file to avoid inline size limits
        orchestrator_code_path = os.path.join(os.path.dirname(__file__), "orchestrator")
        orchestrator = lambda_.Function(self, "Orchestrator",
            function_name=f"microvm-orchestrator-{app_name}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            timeout=Duration.minutes(10),
            code=lambda_.Code.from_asset(orchestrator_code_path),
        )
        orchestrator.add_to_role_policy(iam.PolicyStatement(
            actions=["lambda:*"],
            resources=["*"],
        ))
        orchestrator.add_to_role_policy(iam.PolicyStatement(
            actions=["iam:PassRole"],
            resources=[exec_role.role_arn, edge_role.role_arn],
        ))

        microvm = CustomResource(self, "RunMicrovm",
            service_token=orchestrator.function_arn,
            properties={
                "ImageArn": image.get_att("ImageArn").to_string(),
                "ExecRoleArn": exec_role.role_arn,
                "EdgeFn": edge_fn_name,
                "EdgeRoleArn": edge_role.role_arn,
                "Region": self.region,
                "Port": app_port,
            },
        )
        microvm.node.add_dependency(image)
        microvm.node.add_dependency(orchestrator)

        microvm_id = microvm.get_att_string("MicrovmId")
        microvm_endpoint = microvm.get_att_string("Endpoint")
        edge_version_arn = microvm.get_att_string("EdgeVersionArn")

        # --- CloudFront ---
        distribution = cf.CfnDistribution(self, "CDN",
            distribution_config=cf.CfnDistribution.DistributionConfigProperty(
                comment=f"MicroVM: {app_name}",
                enabled=True,
                origins=[cf.CfnDistribution.OriginProperty(
                    id="microvm",
                    domain_name=microvm_endpoint,
                    custom_origin_config=cf.CfnDistribution.CustomOriginConfigProperty(
                        https_port=443,
                        origin_protocol_policy="https-only",
                        origin_ssl_protocols=["TLSv1.2"],
                    ),
                )],
                default_cache_behavior=cf.CfnDistribution.DefaultCacheBehaviorProperty(
                    target_origin_id="microvm",
                    viewer_protocol_policy="redirect-to-https",
                    allowed_methods=["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                    cached_methods=["GET", "HEAD"],
                    cache_policy_id="4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
                    origin_request_policy_id="b689b0a8-53d0-40ab-baf2-68738e2966ac",
                    lambda_function_associations=[cf.CfnDistribution.LambdaFunctionAssociationProperty(
                        event_type="origin-request",
                        lambda_function_arn=edge_version_arn,
                        include_body=True,
                    )],
                    compress=True,
                ),
            ),
        )
        distribution.add_dependency(microvm.node.default_child)

        # --- Outputs ---
        CfnOutput(self, "Url", value=Fn.join("", ["https://", distribution.attr_domain_name, "/"]))
        CfnOutput(self, "MicrovmId", value=microvm_id)
        CfnOutput(self, "Endpoint", value=microvm_endpoint)
        CfnOutput(self, "ImageArn", value=image.get_att("ImageArn").to_string())
