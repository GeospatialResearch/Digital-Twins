import pulumi_aws as aws
import pulumi_awsx as awsx
from fargate import FargateApplication


class DigitalTwinBackend:
    """
    Stands up 2 Fargate Services with the same image.

    Parameters
    ----------

    service_name : str
        The name of the service. This will be a prefix to the ECS services, etc.

    vpc : awsx.ec2.Vpc
        The VPC that all of the resources are connected to.

    security_group: aws.ec2.SecurityGroup
        The Security Group that all of the resources make use of.

    cluster: aws.ecs.Cluster
        The ECS Cluster that the services created work within.

    image_tag : str
        The tag of the container image within the supplied or created repository.

    environment : list[dict]
        Environment variables for the container. Secrets should not be set here.

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
        vpc: awsx.ec2.Vpc,
        cluster: aws.ecs.Cluster,
        image_tag: str = "latest",
        environment: list[dict] = [],
        volumes: list[aws.ecs.TaskDefinitionVolumeArgs] = [],
        mount_points: list[awsx.ecs.TaskDefinitionMountPointArgs] = [],
        secrets: list[awsx.ecs.TaskDefinitionSecretArgs] = [],
    ):

        redis = self._setup_cache(f"{service_name}-redis", "cache.t2.micro", vpc)

        repo = aws.ecr.Repository(
            f"{service_name}-ecr",
            name=f"{service_name}-ecr",
            image_tag_mutability="MUTABLE",
            image_scanning_configuration={
                "scan_on_push": True,
            },
        )

        env = [
            *environment,
            {"name": "MESSAGE_BROKER_HOST", "value": redis.cache_nodes[0].address},
        ]

        shared_fargate_args = {
            "secrets": secrets,
            "environment": env,
            "volumes": volumes,
            "mount_points": mount_points,
            "repository": repo,
            "image_tag": image_tag,
        }

        backend_service_name = f"{service_name}-flask"
        backend_service = FargateApplication(
            backend_service_name,
            cluster,
            vpc,
            service_port=5000,
            entrypoint=["/app/src/backend_entrypoint.sh"],
            **shared_fargate_args,
        )

        celery_service_name = f"{service_name}-celery"
        celery_service = FargateApplication(
            celery_service_name,
            cluster,
            vpc,
            cpu=1000,
            memory=4096,
            replica_count=2,
            entrypoint=["/app/src/celery_worker_entrypoint.sh"],
            **shared_fargate_args,
        )

        self.target_group = backend_service.target_group
        self.backend_service = backend_service
        self.celery_service = celery_service
        self.repo = repo

    def _setup_cache(self, service_name: str, cache_node_type: str, vpc: awsx.ec2.Vpc):
        cache_subnet_group = aws.elasticache.SubnetGroup(
            f"{service_name}-subnetgroup",
            name=f"{service_name}-subnetgroup",
            subnet_ids=vpc.public_subnet_ids,
        )

        redis_sec_group = aws.ec2.SecurityGroup(
            f"{service_name}-sg",
            name=f"{service_name}-sg",
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
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    from_port=6379,
                    to_port=6379,
                    protocol="tcp",
                    cidr_blocks=["10.0.0.0/16"],
                )
            ],
        )

        redis = aws.elasticache.Cluster(
            service_name,
            cluster_id=service_name,
            engine="redis",
            node_type=cache_node_type,
            subnet_group_name=cache_subnet_group.name,
            num_cache_nodes=1,
            parameter_group_name="default.redis7",
            engine_version="7.0",
            port=6379,
            security_group_ids=[
                redis_sec_group.id,
            ],
        )

        return redis
