import kopf
import kubernetes.client
from kubernetes.client.rest import ApiException

def create_redis_deployment(name, namespace, size, role, image):
    # Labels to identify the pods
    labels = {"app": f"{name}-{role}"}
    return kubernetes.client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=kubernetes.client.V1ObjectMeta(name=f"{name}-{role}", namespace=namespace),
        spec=kubernetes.client.V1DeploymentSpec(
            replicas=size,
            selector=kubernetes.client.V1LabelSelector(
                match_labels=labels
            ),
            template=kubernetes.client.V1PodTemplateSpec(
                metadata=kubernetes.client.V1ObjectMeta(
                    labels=labels
                ),
                spec=kubernetes.client.V1PodSpec(
                    containers=[
                        kubernetes.client.V1Container(
                            name="redis",
                            image=image,
                            ports=[kubernetes.client.V1ContainerPort(container_port=6379)]
                        )
                    ]
                )
            )
        )
    )

def create_backup_cron_job(name, namespace, schedule, image):
    # Define a CronJob resource for backups
    return kubernetes.client.V1CronJob(
        api_version="batch/v1",
        kind="CronJob",
        metadata=kubernetes.client.V1ObjectMeta(name=f"{name}-backup", namespace=namespace),
        spec=kubernetes.client.V1CronJobSpec(
            schedule=schedule,
            job_template=kubernetes.client.V1JobTemplateSpec(
                spec=kubernetes.client.V1JobSpec(
                    template=kubernetes.client.V1PodTemplateSpec(
                        spec=kubernetes.client.V1PodSpec(
                            containers=[
                                kubernetes.client.V1Container(
                                    name="backup",
                                    image=image,
                                    args=["redis-cli", "save"]
                                )
                            ],
                            restart_policy="OnFailure"
                        )
                    )
                )
            )
        )
    )

@kopf.on.create('database.example.com', 'v1', 'redises')
def create_fn(body, name, namespace, logger, **kwargs):
    # Extract the spec from the body of the custom resource
    spec = body.get('spec', {})
    master_size = spec.get('masterSize', 1)
    slave_size = spec.get('slaveSize', 2)
    image = spec.get('image', 'redis:latest')
    backup_enabled = spec.get('backupEnabled', False)
    backup_schedule = spec.get('backupSchedule', '0 */12 * * *')

    k8s_apps_v1 = kubernetes.client.AppsV1Api()

    # Create master deployment
    master_deployment = create_redis_deployment(name, namespace, master_size, 'master', image)
    try:
        k8s_apps_v1.create_namespaced_deployment(namespace=namespace, body=master_deployment)
        logger.info(f"Master deployment for Redis '{name}' created.")
    except ApiException as e:
        logger.error(f"Failed to create master deployment: {str(e)}")
        raise kopf.TemporaryError(f"Failed to create master deployment: {str(e)}", delay=30)

    # Create slave deployment
    slave_deployment = create_redis_deployment(name, namespace, slave_size, 'slave', image)
    try:
        k8s_apps_v1.create_namespaced_deployment(namespace=namespace, body=slave_deployment)
        logger.info(f"Slave deployment for Redis '{name}' created.")
    except ApiException as e:
        logger.error(f"Failed to create slave deployment: {str(e)}")
        raise kopf.TemporaryError(f"Failed to create slave deployment: {str(e)}", delay=30)

    # Create a backup job if enabled
    if backup_enabled:
        backup_job = create_backup_cron_job(name, namespace, backup_schedule, image)
        k8s_batch_v1 = kubernetes.client.BatchV1Api()
        try:
            k8s_batch_v1.create_namespaced_cron_job(namespace=namespace, body=backup_job)
            logger.info(f"Backup cron job for Redis '{name}' created.")
        except ApiException as e:
            logger.error(f"Failed to create backup cron job: {str(e)}")
            raise kopf.TemporaryError(f"Failed to create backup cron job: {str(e)}", delay=30)
