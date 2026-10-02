"""Prepare a reviewable dev controller Job manifest; no resource writes."""
import copy
import json
from pathlib import Path
import shutil
import subprocess

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
TARGET = "janus-batch-controller"


def controller_manifest(source):
    task = copy.deepcopy(source["spec"]["template"]["spec"]["template"]["spec"])
    container = task["containers"][0]
    if len(task["containers"]) != 1 or "@sha256:" not in container["image"]:
        raise ValueError("require one container with an immutable image")
    allowed = {"GCP_PROJECT_ID", "CORE_BUCKET", "STAGE_BUCKET", "ICEBERG_WAREHOUSE", "JANUS_INGESTION_POSTGRES_BUNDLE",
               "CONTROL_DB_HOST", "CONTROL_DB_NAME", "CONTROL_DB_USER", "CONTROL_DB_SSLMODE",
               "CATALOG_DB_HOST", "CATALOG_DB_NAME", "CATALOG_DB_USER", "CATALOG_DB_SSLMODE"}
    container["env"] = [item for item in container.get("env", []) if item["name"] in allowed]
    container["env"].append({"name": "BATCH_CONTROLLER_MODE", "value": "observe"})
    container["command"] = ["python"]
    container["args"] = ["-m", "ingestion_core.batch_controller"]
    container["resources"] = {"limits": {"cpu": "1", "memory": "512Mi"}}
    task.update(timeoutSeconds="120", maxRetries=0, serviceAccountName=f"ingestion-core@{PROJECT}.iam.gserviceaccount.com")
    annotations = source["spec"]["template"].get("metadata", {}).get("annotations", {})
    network = {key: value for key, value in annotations.items() if key in {
        "run.googleapis.com/network-interfaces", "run.googleapis.com/vpc-access-connector", "run.googleapis.com/vpc-access-egress",
        "run.googleapis.com/execution-environment"}}
    return {"apiVersion": "run.googleapis.com/v1", "kind": "Job", "metadata": {"name": TARGET},
            "spec": {"template": {"metadata": {"annotations": network}, "spec": {"taskCount": 1, "parallelism": 1,
                     "template": {"spec": task}}}}}


if __name__ == "__main__":
    cloud = shutil.which("gcloud") or r"C:/Program Files (x86)/Google/Cloud SDK/google-cloud-sdk/bin/gcloud.cmd"
    result = subprocess.run([cloud, "run", "jobs", "describe", "janus-ingestion-core", "--project=" + PROJECT,
                             "--region=" + REGION, "--format=json"], capture_output=True, check=True, timeout=30)
    manifest = controller_manifest(json.loads(result.stdout))
    path = Path(".tmp/batch-controller-dev.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(path.resolve()), "job": TARGET, "mode": "observe", "cpu": 1,
                      "memory_mib": 512, "timeout_seconds": 120, "max_retries": 0,
                      "scheduler_cron": "30 * * * *", "time_zone": "Asia/Taipei", "resource_writes": 0}))
