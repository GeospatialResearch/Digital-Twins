from collections import namedtuple

import pulumi_aws as aws
import pulumi_awsx as awsx

LoadBalancerTarget = namedtuple("LoadBalancerTarget", ["name", "url", "target_group"])


class ApplicationLoadBalancer:

    def __init__(
        self,
        lb_name: str,
        vpc: awsx.ec2.Vpc,
        default_target_group,
        targets: list,
        internal: bool = False,
        certificate: aws.acm.Certificate = None,
    ):

        security_group = aws.ec2.SecurityGroup(
            f"{lb_name}-sg",
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
                    from_port=80,
                    to_port=80,
                    protocol="tcp",
                    cidr_blocks=["0.0.0.0/0"],
                ),
                aws.ec2.SecurityGroupIngressArgs(
                    from_port=443,
                    to_port=443,
                    protocol="tcp",
                    cidr_blocks=["0.0.0.0/0"],
                ),
            ],
        )

        lb = awsx.lb.ApplicationLoadBalancer(
            lb_name,
            name=lb_name,
            subnet_ids=vpc.public_subnet_ids,
            idle_timeout=100,
            listeners=[
                {
                    "default_actions": [
                        {
                            "type": "redirect",
                            "redirect": {
                                "status_code": "HTTP_302",
                                "protocol": "HTTPS",
                                "port": "443",
                            },
                        }
                    ],
                    "port": 80,
                },
                {
                    "certificate_arn": certificate.arn,
                    "default_actions": [
                        {
                            "type": "forward",
                            "forward": {
                                "target_groups": [
                                    {
                                        "arn": default_target_group.arn,
                                    }
                                ]
                            },
                        }
                    ],
                    "port": 443,
                },
            ],
            default_security_group=security_group.id,
            security_groups=[security_group],
            internal=internal,
        )

        https_listener = lb.load_balancer.arn.apply(
            lambda arn: aws.lb.get_listener(load_balancer_arn=arn, port=443)
        )

        priority = 99
        for target in targets:
            aws.lb.ListenerRule(
                f"host-routing-{target.name}",
                listener_arn=https_listener.arn,
                priority=priority,
                actions=[
                    {
                        "type": "forward",
                        "forward": {
                            "target_groups": [
                                {
                                    "arn": target.target_group.arn,
                                }
                            ]
                        },
                    }
                ],
                conditions=[
                    {
                        "host_header": {
                            "values": [target.url],
                        },
                    }
                ],
            )
            priority -= 1

        self.load_balancer = lb.load_balancer
