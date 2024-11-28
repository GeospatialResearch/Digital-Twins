import pulumi_aws as aws
import pulumi_awsx as awsx


def _create_mount_targets(public_subnet_ids, fs_name, fs_id, security_group):
    """
    Creates a set of MountTarget objects from a given set of subnets.

    This happens here because the method must be called in an apply callback and
    putting this in the class below may lead to things being done out of order.
    """
    targets = []
    for subnet_id in public_subnet_ids:
        target = aws.efs.MountTarget(
            f"{fs_name}-{subnet_id}",
            file_system_id=fs_id,
            subnet_id=subnet_id,
            security_groups=[security_group],
        )
        targets.append(target)
    return targets


class EFSVolume:
    """
    Instantiates an EFS Volume with a given name and the necessary mount targets so that
    the volume can be connected to from ECS instances over NFS.

    Parameters
    ----------

    fs_name : str
        The name you want to give to the filesystem.

    vpc : awsx.ec2.Vpc
        The VPC that this volume will be shareable on.
    """

    def __init__(
        self,
        fs_name: str,
        vpc: awsx.ec2.Vpc,
    ):
        fs = aws.efs.FileSystem(fs_name)

        security_group = aws.ec2.SecurityGroup(
            f"{fs_name}-sg",
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
                    from_port=2049,
                    to_port=2049,
                    protocol="tcp",
                    cidr_blocks=["10.0.0.0/16"],
                ),
            ],
        )

        vpc.public_subnet_ids.apply(
            lambda public_subnet_ids: _create_mount_targets(
                public_subnet_ids, fs_name, fs.id, security_group
            )
        )
        self._fs_name = fs_name  # Saved so we can use it later.
        self.file_system = fs
        self.file_system_id = fs.id
        self.security_group = security_group

    def create_access_point(
        self, app_name: str, path: str, permissions: str = "664"
    ) -> aws.efs.AccessPoint:
        """
        Create an EFS Access Point object so that access to resources can be
        manages programatically per application.

        Parameters
        ----------

        app_name : str
            The short name of the application this access point is used by.

        path : str
            The path within the container that this Access Point uses

        permissions : str
            The POSIX (RWX) permissions for this filesystem represented as a string.
        """

        return aws.efs.AccessPoint(
            f"{self._fs_name}-{app_name}-ap",
            file_system_id=self.file_system.id,
            posix_user=aws.efs.AccessPointPosixUserArgs(gid=0, uid=0),
            root_directory=aws.efs.AccessPointRootDirectoryArgs(
                path=path,
                creation_info=aws.efs.AccessPointRootDirectoryCreationInfoArgs(
                    owner_gid=0, owner_uid=0, permissions=permissions
                ),
            ),
        )
