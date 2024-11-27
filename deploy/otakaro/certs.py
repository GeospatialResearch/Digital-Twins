import pulumi
import pulumi_aws as aws


def create_cert_validation(domain_validation_options, cert_arn, zone_id, provider):
    records = []
    for dvo in domain_validation_options:
        record = aws.route53.Record(
            dvo.resource_record_name,
            name=dvo.resource_record_name,
            zone_id=zone_id,
            type=dvo.resource_record_type,
            records=[dvo.resource_record_value],
            ttl=600,
        )
        records.append(record)

    aws.acm.CertificateValidation(
        "otakaro.digitaltwins.nz-validation",
        certificate_arn=cert_arn,
        validation_record_fqdns=[record.fqdn for record in records],
        opts=pulumi.ResourceOptions(provider=provider),
    )


class AWSCertificate:
    """
    Wraps the default AWS Certificate to handle Validation, and creation of Certificates in
    multiple cloud regions - this is required for CloudFront integration as CloudFront only works
    out of us-east-1.

    Parameters
    ----------

    domains : list[str]
        A list of domains you want to create a certificate for.

    regions: list[str]
        A list of AWS regions you wish to create certificates in.

    zone: aws.route53.Zone
        The zone that your `domains` live in. Currently this only supports everything in a single
        zone.
    """

    def __init__(self, domains: list[str], regions: list[str], zone: aws.route53.Zone):
        if not domains:
            raise ValueError("domains should not be empty.")

        primary_domain = domains[0]
        alternative_domains = domains[1:]
        certs = dict()

        validate = True
        for region in regions:
            certs[region] = self._create_cert(
                region, primary_domain, alternative_domains, validate
            )
            validate = False
        self.certs = certs

    def __getitem__(self, name):
        return self.certs[name]

    def _create_cert(
        self, region, primary_domain, alternative_domains, zone, validate=False
    ):
        provider = aws.Provider(f"aws-{region}", region=region)

        cert = aws.acm.Certificate(
            f"{region}-{primary_domain}",
            domain_name=primary_domain,
            validation_method="DNS",
            subject_alternative_names=alternative_domains,
            opts=pulumi.ResourceOptions(provider=provider),
        )

        if validate:
            cert.domain_validation_options.apply(
                lambda domain_validation_options: create_cert_validation(
                    domain_validation_options, cert.arn, zone.id, provider
                )
            )

        return cert
