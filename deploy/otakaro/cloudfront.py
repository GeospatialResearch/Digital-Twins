import json
import shutil
from pathlib import Path

import pulumi
import pulumi_aws as aws


def create_records(domains, zone_name, dns_zone, cname_target):
    for domain in domains:
        record_name = domain.replace(f".{zone_name}", "")
        aws.route53.Record(
            f"{record_name}",
            name=record_name,
            zone_id=dns_zone.id,
            type=aws.route53.RecordType.CNAME,
            ttl=5,
            records=[cname_target],
        )


class CloudFront:
    """
    Creates an AWS CloudFront distribution and associated Lambda, DNS Records, etc.

    Parameters
    ----------

    aliases : str[list]
        The list of domains that this CloudFront distribution supports.

    origin_domain_name : str[list]
        The URL that this CloudFront Distribution points to.

    certificate : aws.acm.Certificate
        An Amazon Issued HTTPS Certificate.

    dns_zone : aws.route53.Zone
        Zone to create DNS records in

    zone_name : str
        Required because retrieving the name from the dns zone is complicated.
        This should just be the primary domain name (i.e otakaro.digitaltwins.nz as an alias
        means this should be `digitaltwins.nz`)
    """

    def __init__(
        self,
        aliases: list[str],
        origin_domain_name: str,
        certificate: aws.acm.Certificate,
        dns_zone: aws.route53.Zone,
        zone_name: str,
        basic_auth: tuple = None,
    ):
        # Cloudfront is us-east-1 only for the API
        self.provider = aws.Provider("aws-east-1", region="us-east-1")
        if basic_auth:
            basic_auth_func = self._basic_auth(basic_auth)

        cloudfront = aws.cloudfront.Distribution(
            "cloudfront_dist",
            aliases=[
                "api.otakaro.digitaltwins.nz",
                "otakaro.digitaltwins.nz",
                "gs.otakaro.digitaltwins.nz",
            ],
            origins=[
                aws.cloudfront.DistributionOriginArgs(
                    domain_name=origin_domain_name,
                    origin_id="otakaro-alb-internal",
                    custom_origin_config=aws.cloudfront.DistributionOriginCustomOriginConfigArgs(
                        http_port=80,
                        https_port=443,
                        origin_protocol_policy="https-only",
                        origin_ssl_protocols=["TLSv1.1", "TLSv1.2"],
                        origin_keepalive_timeout=5,
                        origin_read_timeout=100,
                    ),
                    connection_timeout=10,
                    connection_attempts=3,
                )
            ],
            enabled=True,
            default_cache_behavior=aws.cloudfront.DistributionDefaultCacheBehaviorArgs(
                allowed_methods=[
                    "GET",
                    "HEAD",
                    "PUT",
                    "POST",
                    "OPTIONS",
                    "DELETE",
                    "PATCH",
                ],
                cached_methods=["GET", "HEAD"],
                target_origin_id="otakaro-alb-internal",
                viewer_protocol_policy="redirect-to-https",
                forwarded_values=aws.cloudfront.DistributionDefaultCacheBehaviorForwardedValuesArgs(
                    cookies={"forward": "all"},
                    query_string=True,
                    headers=[
                        "Host",
                        "Origin",
                        "Authorization",
                    ],
                ),
                lambda_function_associations=(
                    [
                        aws.cloudfront.DistributionDefaultCacheBehaviorLambdaFunctionAssociationArgs(
                            lambda_arn=pulumi.Output.concat(
                                basic_auth_func.arn, ":", basic_auth_func.version
                            ),
                            event_type="viewer-request",
                        )
                    ]
                    if basic_auth
                    else []
                ),
                response_headers_policy_id="60669652-455b-4ae9-85a4-c4c02393f86c",  # SimpleCORS
            ),
            restrictions=aws.cloudfront.DistributionRestrictionsArgs(
                geo_restriction=aws.cloudfront.DistributionRestrictionsGeoRestrictionArgs(
                    restriction_type="none",
                    locations=[],
                ),
            ),
            viewer_certificate=aws.cloudfront.DistributionViewerCertificateArgs(
                acm_certificate_arn=certificate.arn,
                ssl_support_method="sni-only",
            ),
        )

        cloudfront.domain_name.apply(
            lambda domain_name: create_records(
                aliases, zone_name, dns_zone, domain_name
            )
        )

        self.cloudfront_url = cloudfront.domain_name

    def _basic_auth(self, basic_auth):
        lambda_role = aws.iam.Role(
            "cloudfront-basic-auth",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Effect": "Allow",
                            "Sid": "",
                        },
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "edgelambda.amazonaws.com"},
                            "Effect": "Allow",
                            "Sid": "",
                        },
                    ],
                },
            ),
        )

        aws.iam.RolePolicy(
            "cloudfront-basic-auth-profile",
            role=lambda_role.id,
            policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            "Resource": "arn:aws:logs:*:*:*",
                        },
                    ],
                }
            ),
        )

        # This section handles templating the basic auth files so that the
        # username and password can be secrets..

        template = Path.cwd() / Path("lambdas/http_basic_auth")
        target = Path.cwd() / Path("lambdas/http_basic_auth_deploy")

        shutil.copytree(template, target, dirs_exist_ok=True)

        def template_file(file, username, password):
            with open(file, "r") as js_file:
                filedata = js_file.read()
                filedata = filedata.replace("$AUTH_USER", username).replace(
                    "$AUTH_PASS", password
                )

            with open(file, "w") as js_file:
                js_file.write(filedata)

        pulumi.Output.all(basic_auth[0], basic_auth[1]).apply(
            lambda args: template_file(
                target / Path("http_basic_auth.js"), args[0], args[1]
            )
        )

        archive = pulumi.AssetArchive(
            {".": pulumi.FileArchive("./lambdas/http_basic_auth_deploy/")}
        )

        aws.lambda_.Function(
            "cloudfront-basic-auth",
            name="cloudfront-basic-auth",
            runtime="nodejs18.x",
            handler="http_basic_auth.handler",
            code=archive,
            role=lambda_role.arn,
            opts=pulumi.ResourceOptions(provider=self.provider),
            publish=True,
        )

        function = aws.lambda_.get_function_output(
            function_name="cloudfront-basic-auth",
            opts=pulumi.InvokeOptions(provider=self.provider),
        )

        return function
