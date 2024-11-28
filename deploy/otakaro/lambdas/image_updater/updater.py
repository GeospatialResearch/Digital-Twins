import json
import boto3
import os


def response(code: int, message: str):
    return {"statusCode": code, "body": json.dumps(message)}


def get_service(client: boto3.client, cluster_name: str, service_search_str: str):
    """
    Returns the ARN for the first service that matches the substring `service_search_str` in the given
    cluster.

    Returns the definition for the service if it exists.
    """
    services = client.list_services(cluster=cluster_name)
    service_arns = services.get("serviceArns")

    if not service_arns:
        return

    for service_arn in service_arns:
        if service_search_str in service_arn:
            service = client.describe_services(
                cluster=cluster_name, services=[service_arn]
            )
            try:
                service_defn = service.get("services")[0]
                return service_defn
            except (KeyError, ValueError):
                return None


def create_new_task_defn(client: boto3.client, old_task_defn_arn: dict, new_image: str):
    old_task_defn = client.describe_task_definition(taskDefinition=old_task_defn_arn)
    new_task_defn = old_task_defn.get("taskDefinition")

    if not new_task_defn:
        return

    # List of args to remove comes from this stack overflow comment:
    # https://stackoverflow.com/questions/69830578/aws-ecs-using-boto3-to-update-a-task-definition
    remove_args = [
        "compatibilities",
        "registeredAt",
        "registeredBy",
        "status",
        "revision",
        "taskDefinitionArn",
        "requiresAttributes",
    ]
    for arg in remove_args:
        new_task_defn.pop(arg)
    try:
        new_task_defn["containerDefinitions"][0]["image"] = new_image
    except (KeyError, ValueError):
        return None

    return new_task_defn


def update_service(
    client: boto3.client, cluster_name: str, service_arn: str, new_task_defn: dict
):
    task_defn_reg_resp = client.register_task_definition(**new_task_defn)
    task_rev_arn = task_defn_reg_resp.get("taskDefinition", {}).get("taskDefinitionArn")
    client.update_service(
        cluster=cluster_name, service=service_arn, taskDefinition=task_rev_arn
    )


def handler(event, context):
    service_name = os.environ.get("ECS_SERVICE_NAME")
    cluster_name = os.environ.get("ECS_CLUSTER_NAME")
    repo_base_url = os.environ.get("ECR_BASE_URL")
    if not service_name:
        return {
            "statusCode": 400,
            "body": json.dumps("ECS_SERVICE_NAME variable missing"),
        }

    if not cluster_name:
        return {
            "statusCode": 400,
            "body": json.dumps("ECS_CLUSTER_NAME variable missing"),
        }

    event_detail = event.get("detail")
    if not event_detail:
        print("Failed to get event detail.")
        return response(400, "No event detail found")

    image_repo = event_detail.get("repository-name")
    image_tag = event_detail.get("image-tag")
    if image_tag is None or image_repo is None:
        print("Failed to get image reference")
        return {
            "statusCode": 400,
            "body": json.dumps("Something went wrong and no image tag was found."),
        }

    image = f"{repo_base_url}/{image_repo}:{image_tag}"

    client = boto3.client("ecs")

    svc = get_service(client, cluster_name, service_name)
    task_defn_arn = svc.get("taskDefinition")
    new_task_defn = create_new_task_defn(client, task_defn_arn, image)
    update_service(client, cluster_name, svc["serviceArn"], new_task_defn)

    return {
        "statusCode": 200,
        "body": json.dumps("Successfully replaced the image in the ECS config."),
    }
