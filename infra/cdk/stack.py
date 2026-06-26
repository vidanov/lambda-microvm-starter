"""CDK stack placeholder for Lambda MicroVM infrastructure.

As of June 2026, Lambda MicroVMs are API-only (no CloudFormation resource types).
This stack manages everything EXCEPT the MicroVM-specific resources:
- S3 bucket for artifacts
- IAM roles (build + execution)
- CloudFront distribution
- Lambda@Edge function

When AWS ships CFN support (AWS::Lambda::MicrovmImage, AWS::Lambda::Microvm),
replace the Custom Resource below with native L1 constructs.
"""

# TODO: Uncomment and implement when CDK supports MicroVMs
#
# from aws_cdk import (
#     Stack, Duration, RemovalPolicy,
#     aws_s3 as s3,
#     aws_iam as iam,
#     aws_lambda as lambda_,
#     aws_cloudfront as cf,
#     aws_cloudfront_origins as origins,
#     custom_resources as cr,
# )
# from constructs import Construct
#
#
# class MicroVmStack(Stack):
#     def __init__(self, scope: Construct, id: str, *, app_name: str, region: str, **kwargs):
#         super().__init__(scope, id, **kwargs)
#
#         # S3 bucket for MicroVM artifacts
#         bucket = s3.Bucket(self, "Artifacts",
#             removal_policy=RemovalPolicy.DESTROY,
#             auto_delete_objects=True,
#         )
#
#         # Build role
#         build_role = iam.Role(self, "BuildRole",
#             assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
#         )
#         bucket.grant_read(build_role)
#
#         # Execution role
#         exec_role = iam.Role(self, "ExecRole",
#             assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
#         )
#
#         # Lambda@Edge for auth injection
#         edge_fn = lambda_.Function(self, "EdgeAuth",
#             runtime=lambda_.Runtime.PYTHON_3_12,
#             handler="lambda_function.handler",
#             code=lambda_.Code.from_asset("../infra/edge-auth"),
#             timeout=Duration.seconds(5),
#             memory_size=128,
#         )
#
#         # Custom Resource: create MicroVM image (replace with native when available)
#         # microvm_image = cr.AwsCustomResource(self, "MicrovmImage", ...)
#
#         # CloudFront distribution
#         # distribution = cf.Distribution(self, "CDN", ...)
#
#         # When native CFN support ships, replace Custom Resource with:
#         # cfn_image = lambda_.CfnMicrovmImage(self, "Image",
#         #     name=app_name,
#         #     base_image_arn=f"arn:aws:lambda:{region}:aws:microvm-image:al2023-1",
#         #     build_role_arn=build_role.role_arn,
#         #     code_artifact={"uri": bucket.s3_url_for_object("app.zip")},
#         # )
