import json

import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx


class FargateApplication:
    """
    Creates a default Fargate Application on Amazon ECS. Also automatically instantiates an ECR
    Image Repository, a Load Balancer Target Group (if a port is supplied) and a Lambda Function to
    automatically refresh the running tasks images.

    NOTE: Some manual intervention is required to enable the trigger for the lambda. At this stage
    there's no good documentation on how to do this with Pulumi and it's just easier to connect it
    in the AWS Console.

    Parameters
    ----------

    service_name : str
        The name of the ECS Fargate Service you wish to run

    cluster : aws.ecs.Cluster
        The Cluster that this service will run within.

    vpc : aws.ec2.Vpc
        The VPC that your Cluster is connected to.

    service_port : int
        The port that your application listens on for HTTP traffic. Defaults to None.
        If not specified, no Target Group will be created for a load balancer.

    image_tag : str
        The tag of the container image within the supplied or created repository.

    repository : aws.ecr.Repository
        If this is set, no new ECR Repository will be created, and this one will be used instead.

    auto_image_push : bool
        If set to True, an AWS Lambda function is created that will automatically update the image
        tag to a new tag on image push.

    entrypoint : list[str]
        The entrypoint command for the container if it needs to be overridden.

    environment : list[dict]
        Environment variables for the container. Secrets should not be set here.

    replica_count : int
        How many "tasks" (i.e replicas of your container) you want to run

    cpu : int
        How much CPU should this task get? 1000 ~= 1 vCPU.

    memory : int
        How much Memory should this task get? 1024 ~= 1GB Mem

    volumes : list[aws.ecs.TaskDefinitionVolumeArgs]
        The list of volumes that this task has access to

    mount_points : list[awsx.ecs.TaskDefinitionMountPointArgs]
        The list of mount points for the volumes specified above.

    secrets : list[awsx.ecs.TaskDefinitionSecretArgs]
        The list of secrets to mount as Environment Variables.
    """

    def __init__(
        self,
        service_name: str,
        cluster: aws.ecs.Cluster,
        vpc: awsx.ec2.Vpc,
        service_port: int = None,
        image_tag: str = "latest",
        repository: aws.ecr.Repository = None,
        auto_image_push: bool = True,
        entrypoint: list[str] = None,
        environment: list[dict] = [],
        replica_count: int = 2,
        cpu: int = 128,
        memory: int = 512,
        volumes: list[aws.ecs.TaskDefinitionVolumeArgs] = [],
        mount_points: list[awsx.ecs.TaskDefinitionMountPointArgs] = [],
        secrets: [awsx.ecs.TaskDefinitionSecretArgs] = [],
    ):
        repo = repository
        if not repo:
            repo_name = f"{service_name}-ecr"
            repo = aws.ecr.Repository(
                repo_name,
                name=repo_name,
                image_tag_mutability="MUTABLE",
                image_scanning_configuration={
                    "scan_on_push": True,
                },
            )

        security_group = aws.ec2.SecurityGroup(
            f"{service_name}-sg",
            vpc_id=vpc.vpc_id,
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=["0.0.0.0/0"],
                    ipv6_cidr_blocks=["::/0"],
                )
            ],
            ingress=(
                [
                    aws.ec2.SecurityGroupIngressArgs(
                        from_port=service_port,
                        to_port=service_port,
                        protocol="tcp",
                        cidr_blocks=["0.0.0.0/0"],
                    ),
                ]
                if service_port
                else []
            ),
        )

        port_mappings = []
        target_group = None
        if service_port:
            target_group_name = f"{service_name}-tg"
            target_group = aws.lb.TargetGroup(
                target_group_name,
                name=target_group_name,
                vpc_id=vpc.vpc_id,
                port=service_port,
                protocol="HTTP",
                target_type="ip",
            )

            port_mappings = [
                {
                    "container_port": service_port,
                    "host_port": service_port,
                    "target_group": {
                        "arn": target_group.arn,
                        "port": target_group.port,
                    },
                    "protocol": "tcp",
                }
            ]

        execution_role = aws.iam.Role(
            f"{service_name}-execution",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                            "Effect": "Allow",
                            "Sid": "",
                        }
                    ],
                }
            ),
        )

        aws.iam.RolePolicy(
            f"{service_name}-execution-policy",
            role=execution_role.id,
            policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "ssm:Describe*",
                                "ssm:Get*",
                                "ssm:List*",
                                "kms:Decrypt",
                                "ecr:GetAuthorizationToken",
                                "ecr:BatchCheckLayerAvailability",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:BatchGetImage",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            "Resource": "*",
                        },
                    ],
                }
            ),
        )

        service = awsx.ecs.FargateService(
            service_name,
            name=service_name,
            cluster=cluster.arn,
            network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
                subnets=vpc.public_subnet_ids,
                assign_public_ip=True,
                security_groups=[security_group],
            ),
            desired_count=replica_count,
            task_definition_args=awsx.ecs.FargateServiceTaskDefinitionArgs(
                execution_role={
                    "role_arn": execution_role.arn,
                },
                container=awsx.ecs.TaskDefinitionContainerDefinitionArgs(
                    name=service_name,
                    image=pulumi.Output.concat(repo.repository_url, ":", image_tag),
                    cpu=cpu,
                    memory=memory,
                    essential=True,
                    mount_points=mount_points,
                    entry_point=entrypoint,
                    port_mappings=port_mappings,
                    environment=environment,
                    secrets=secrets,
                    user="root",
                ),
                volumes=volumes,
            ),
        )

        if auto_image_push:
            self._configure_auto_image_push(
                cluster.name, service_name, repository or repo
            )

        self.target_group = target_group
        self.repo = repo
        self.service = service

    def _configure_auto_image_push(
        self, cluster_name: str, service_name: str, repository: aws.ecr.Repository
    ):
        """
        Configures an AWS Lambda function to automatically detect new image pushes and
        update the application.
        """

        lambda_role = aws.iam.Role(
            f"{service_name}-update",
            assume_role_policy=json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Action": "sts:AssumeRole",
                            "Principal": {"Service": "lambda.amazonaws.com"},
                            "Effect": "Allow",
                            "Sid": "",
                        }
                    ],
                }
            ),
        )

        aws.iam.RolePolicy(
            f"{service_name}-update-policy",
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
                        {
                            "Effect": "Allow",
                            "Action": [
                                "ecs:ListServices",
                                "ecs:DescribeTasks",
                                "ecs:DescribeServices",
                                "ecs:DescribeTaskDefinition",
                                "ecs:RegisterTaskDefinition",
                                "ecs:UpdateService",
                                "ecs:ListTasks",
                                "ecs:DeregisterTaskDefinition",
                            ],
                            "Resource": "*",
                        },
                        {
                            "Effect": "Allow",
                            "Action": ["iam:PassRole"],
                            "Resource": "*",
                        },
                    ],
                }
            ),
        )

        lambda_func = aws.lambda_.Function(
            f"{service_name}-update",
            role=lambda_role.arn,
            runtime="python3.12",
            handler="updater.handler",
            code=pulumi.AssetArchive(
                {".": pulumi.FileArchive("./lambdas/image_updater/")}
            ),
            environment={
                "variables": {
                    "ECS_SERVICE_NAME": service_name,
                    "ECS_CLUSTER_NAME": cluster_name,
                    "ECR_BASE_URL": "443370676516.dkr.ecr.ap-southeast-2.amazonaws.com",
                },
            },
        )

        image_push_rule = aws.cloudwatch.EventRule(
            f"{service_name}-image-push",
            event_bus_name="default",
            event_pattern=repository.name.apply(
                lambda name: json.dumps(
                    {
                        "source": ["aws.ecr"],
                        "detail-type": ["ECR Image Action"],
                        "detail": {
                            "repository-name": [name],
                            "result": ["SUCCESS"],
                            "action-type": ["PUSH"],
                        },
                    }
                )
            ),
        )

        aws.cloudwatch.EventTarget(
            f"{service_name}-image-push-lambda-trigger",
            target_id="image-push-lambda-trigger",
            rule=image_push_rule.name,
            arn=lambda_func.arn,
            event_bus_name="default",
        )
