import pulumi_aws as aws
import pulumi_awsx as awsx


class PostgresInstance:
    """
    Instantiates a Postgres instance on AWS using Pulumi.

    Parameters
    ----------

    instance_name : str
        The string to name the postgres instance and to prefix all of the related resources with.

    vpc : awsx.ec2.Vpc
        The virtual network that the RDS instance is connected to.

    cidr_blocks : list[str]
        The CIDR blocks for limiting access to the instance. This could also be a list of single
        /32 IP addresses if required.

        This is also used to ensure that database access is not made public as that would represent
        a significant security risk.

    username : str
        The username for the administrative user

    password : str
        The default password for the administrative user

    database_name : str
        The name of the actual database - not the instance, but the postgres database
        itself. It is possible to create extra databases in the instance, but RDS generally works
        with a single database in each instance.

    database_port : int
        Allows setting a non-standard port as the default port for the instance.
        Defaults to the normal PostgreSQL port (5432)

    instance_class : aws.rds.InstanceType
        The SKU/Class that represents the size of the instance. This could be a string as well, but
        is limited to the Enum provided by the pulumi AWS package. Defaults to a t4g.small
    """

    def __init__(
        self,
        instance_name: str,
        vpc: awsx.ec2.Vpc,
        cidr_blocks: list[str],
        username: str,
        password: str,
        database_name: str,
        database_port: int = 5432,
        instance_class: aws.rds.InstanceType = aws.rds.InstanceType.T4_G_SMALL,
    ):
        subnet_group = aws.rds.SubnetGroup(
            f"{instance_name}-subnets",
            name=f"{instance_name}-subnets",
            subnet_ids=vpc.public_subnet_ids,
            tags={},
        )

        security_group = aws.ec2.SecurityGroup(
            f"{instance_name}-sg",
            name=f"{instance_name}-sg",
            vpc_id=vpc.vpc_id,
            egress=[
                aws.ec2.SecurityGroupEgressArgs(
                    from_port=0,
                    to_port=0,
                    protocol="-1",
                    cidr_blocks=cidr_blocks,
                )
            ],
            ingress=[
                aws.ec2.SecurityGroupIngressArgs(
                    from_port=database_port,
                    to_port=database_port,
                    protocol="tcp",
                    cidr_blocks=cidr_blocks,
                )
            ],
        )

        db = aws.rds.Instance(
            instance_name,
            allocated_storage=20,
            engine="postgres",
            engine_version="15",
            username=username,
            password=password,
            instance_class=instance_class,
            db_subnet_group_name=subnet_group.name,
            db_name=database_name,
            port=database_port,
            skip_final_snapshot=True,
            vpc_security_group_ids=[
                security_group.id,
            ],
        )

        self.address = db.address
        self.security_group = security_group
        self.secrets = db.master_user_secrets
