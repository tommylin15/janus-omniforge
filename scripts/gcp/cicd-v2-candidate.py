"""Bounded candidate/release controller using the existing regional mutex."""
from __future__ import annotations

import importlib.util
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

spec = importlib.util.spec_from_file_location("v2", Path(__file__).with_name("cicd-v2.py"))
v2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v2)
PROJECT, REGION = v2.PROJECT, v2.REGION
BUCKET = f"gs://{PROJECT}-cloudbuild-regional/v2"


def command(*args):
    return v2.run("gcloud", *args, f"--project={PROJECT}", f"--region={REGION}", "--quiet")


def describe(kind, name):
    return v2.gcloud("run", kind, "describe", name, f"--region={REGION}")


def ready(resource):
    return any(c.get("type") == "Ready" and c.get("status") == "True"
               for c in resource.get("status", {}).get("conditions", []))


def job_config(resource):
    config = json.loads(json.dumps(resource["spec"]))
    template = config["template"]["spec"]["template"]["spec"]
    for container in template["containers"]:
        container.pop("image", None)
        # Mart version metadata intentionally changes with the image.
        container["env"] = [e for e in container.get("env", [])
                            if e["name"] not in {"JANUS_GIT_SHA", "JANUS_IMAGE_DIGEST"}]
    return config


def ensure_idle(job):
    executions = v2.gcloud("run", "jobs", "executions", "list", f"--job={job}", f"--region={REGION}")
    if any(not e.get("status", {}).get("completionTime") for e in executions):
        raise RuntimeError("active execution; bounded retry after completion required")


def execute(job, env, timeout=900):
    ensure_idle(job)
    name = command("run", "jobs", "execute", job, "--tasks=1", "--task-timeout=10m",
                   f"--update-env-vars={env}", "--async", "--format=value(metadata.name)").rsplit("/", 1)[-1]
    if not name:
        raise RuntimeError("execution identity missing; do not redispatch")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resource = v2.gcloud(
            "run", "jobs", "executions", "describe", name, f"--region={REGION}")
        status = resource.get("status", {})
        if status.get("completionTime"):
            if int(status.get("failedCount", 0)) or int(status.get("succeededCount", 0)) != 1:
                raise RuntimeError(f"execution failed: {name}")
            return name
        print(json.dumps({"execution": name, "state": "waiting"}), flush=True)
        time.sleep(10)
    raise TimeoutError(f"execution timeout: {name}; inspect same execution before retry")


def http_gate(base, sha):
    paths = {"/health": 200, "/api/v1/public/health": 200,
             "/api/v1/me/profile": 401, "/api/v1/admin/stocks": 401}
    for path, expected in paths.items():
        try:
            with urlopen(base + path, timeout=30) as response:
                status = response.status
        except HTTPError as error:
            status = error.code
        if status != expected:
            raise RuntimeError(f"candidate HTTP gate failed: {path} ({status})")
    with urlopen(base + "/app/build-id.txt", timeout=30) as response:
        if response.read().decode().strip() != sha:
            raise RuntimeError("candidate Flutter SHA mismatch")
    for path in ("/app/", "/app/admin"):
        with urlopen(base + path, timeout=30) as response:
            if f"flutter_bootstrap.{sha}.js" not in response.read().decode():
                raise RuntimeError("candidate User/Admin bootstrap mismatch")


def validate_acceptance(acceptance, receipt):
    required = {"migration", "permissions", "dependencies", "ingestion", "mart", "private_queue",
                "owner_isolation", "oauth", "canonical_pnl", "mcp"}
    if acceptance.get("sha") != receipt["sha"] or acceptance.get("images") != receipt["images"]:
        raise ValueError("acceptance SHA/digest mismatch")
    if any(acceptance.get("gates", {}).get(gate) != "PASS" for gate in required):
        raise RuntimeError("live acceptance incomplete; release forbidden")
    if not acceptance.get("evidence"):
        raise RuntimeError("live acceptance evidence missing")


def head_fence(sha):
    current = json.loads(urlopen("https://api.github.com/repos/tommylin15/janus-omniforge/commits/main", timeout=30).read())["sha"]
    if current != sha:
        raise RuntimeError("stale SHA; cannot replace newer main runtime")


def restore_version_flags(resource):
    names = {"JANUS_GIT_SHA", "JANUS_IMAGE_DIGEST"}
    env = resource["spec"]["template"]["spec"]["template"]["spec"]["containers"][0].get("env", [])
    values = {e["name"]: e["value"] for e in env if e["name"] in names and "value" in e}
    flags = []
    if values:
        flags.append("--update-env-vars=" + ",".join(f"{key}={value}" for key, value in sorted(values.items())))
    if names - values.keys():
        flags.append("--remove-env-vars=" + ",".join(sorted(names - values.keys())))
    return flags


def main():
    state = Path(os.environ.get("JANUS_STATE", "/workspace/v2-state"))
    receipt = json.loads((state / "build-receipt.json").read_text())
    mode = os.environ.get("JANUS_MODE", "shadow")
    if mode not in {"shadow", "candidate", "release"}:
        raise ValueError("invalid release mode")
    if mode == "shadow" or not receipt["images"]:
        return
    release = mode == "release"
    if release:
        if os.environ.get("JANUS_RELEASE_READY") != "true" or not os.environ.get("JANUS_WBS_ID"):
            raise RuntimeError("release work package not Ready")
        uri = os.environ.get("JANUS_ACCEPTANCE_URI", "")
        if not uri.startswith(BUCKET + "/evidence/") or not uri.endswith(".json"):
            raise ValueError("versioned regional acceptance evidence required")
        acceptance = json.loads(v2.run("gcloud", "storage", "cat", uri))
        validate_acceptance(acceptance, receipt)

    build_id = os.environ["JANUS_BUILD_ID"]
    # One existing regional object is the global deployment mutex. No lease
    # takeover: a killed build requires operator terminal-state verification.
    lock_uri = BUCKET + "/deployment-lock.json"
    lock = state / "lock.json"
    lock.write_text(json.dumps({"build_id": build_id, "sha": receipt["sha"]}))
    v2.run("gcloud", "storage", "cp", str(lock), lock_uri, "--if-generation-match=0", "--quiet")
    generation = v2.run("gcloud", "storage", "objects", "describe", lock_uri, "--format=value(generation)")
    previous = {}
    updated = []
    paused = []
    try:
        head_fence(receipt["sha"])
        # Preserve only the existing active schedules; suspended ones stay so.
        schedules = v2.gcloud("scheduler", "jobs", "list", f"--location={REGION}")
        jobs = ["janus-ingestion-core", "janus-intelligence-mart", "janus-private-pipeline", "janus-batch-controller"]
        for job in jobs:
            if release:
                ensure_idle(job)
            previous[job] = describe("jobs", job)
        api_before = describe("services", "janus-api")
        original_traffic = api_before["status"].get("traffic", [])
        snapshot = state / "runtime-before.json"
        snapshot.write_text(json.dumps({"sha": receipt["sha"], "build_id": build_id,
                                        "jobs": previous, "api": api_before, "enabled_schedules": [x["name"] for x in schedules if x.get("state") == "ENABLED"]}, indent=2))
        v2.run("gcloud", "storage", "cp", str(snapshot),
               BUCKET + f"/evidence/{build_id}/{os.environ.get('JANUS_VALIDATION_ID', 'candidate')}-runtime-before.json",
               "--if-generation-match=0", "--quiet")
        for schedule in schedules if release else []:
            target = schedule.get("httpTarget", {}).get("uri", "")
            if any(name in target for name in ("janus-batch-controller", "janus-ingestion-core", "janus-intelligence-mart", "janus-private-pipeline")) and schedule.get("state") == "ENABLED":
                name = schedule["name"].rsplit("/", 1)[-1]
                v2.run("gcloud", "scheduler", "jobs", "pause", name, f"--project={PROJECT}", f"--location={REGION}", "--quiet")
                paused.append(name)
        candidates = {}
        if "api" in receipt["images"]:
            suffix = f"v2-{receipt['sha'][:20]}"
            command("run", "services", "update", "janus-api", f"--image={receipt['images']['api']}",
                    "--no-traffic", "--tag=v2-candidate", f"--revision-suffix={suffix}")
            api = describe("services", "janus-api")
            candidate = api["status"]["latestReadyRevisionName"]
            if not ready(api) or candidate != "janus-api-" + suffix:
                raise RuntimeError("API candidate not ready")
            positive_before = {t["revisionName"]: t.get("percent", 0) for t in original_traffic if t.get("percent", 0)}
            positive_after = {t["revisionName"]: t.get("percent", 0) for t in api["status"]["traffic"] if t.get("percent", 0)}
            if positive_before != positive_after:
                raise RuntimeError("candidate unexpectedly changed traffic")
            url = next(t["url"] for t in api["status"]["traffic"] if t.get("tag") == "v2-candidate")
            http_gate(url, receipt["sha"])
            candidates["api"] = {"revision": candidate, "url": url, "public_negative_and_flutter": "PASS",
                                  "authenticated_owner_oauth_pnl": "NOT_RUN"}
        for component in v2.COMPONENTS[:-1] if release else []:
            if component not in receipt["images"]:
                continue
            job = "janus-" + component
            ensure_idle(job)
            head_fence(receipt["sha"])
            flags = []
            if component == "intelligence-mart":
                flags = [f"--update-env-vars=JANUS_GIT_SHA={receipt['sha']},JANUS_IMAGE_DIGEST={receipt['images'][component].rsplit('@', 1)[1]}"]
            command("run", "jobs", "update", job, f"--image={receipt['images'][component]}", *flags)
            updated.append(job)
            after = describe("jobs", job)
            if not ready(after) or job_config(previous[job]) != job_config(after):
                raise RuntimeError("job config drift or readiness failed")
            if component == "ingestion-core":
                execution = execute(job, "JANUS_CICD_READINESS=check")
            elif component == "intelligence-mart":
                execution = execute(job, "MART_OPERATION=specialist-smoke")
            else:
                execution = execute(job, "MOBILE_LEDGER_PROBE_ONLY=true,PRIVATE_RECALC_QUEUE_MODE=false")
            candidates[component] = {"job": job, "execution": execution, "readback_and_smoke": "PASS"}
        if release:
            # The controller image shares ingestion, but never executes a batch here.
            if "ingestion-core" in receipt["images"]:
                job = "janus-batch-controller"
                ensure_idle(job)
                command("run", "jobs", "update", job, f"--image={receipt['images']['ingestion-core']}")
                updated.append(job)
                if job_config(previous[job]) != job_config(describe("jobs", job)):
                    raise RuntimeError("batch controller config drift")
            if "api" in candidates:
                head_fence(receipt["sha"])
                command("run", "services", "update-traffic", "janus-api",
                        f"--to-revisions={candidates['api']['revision']}=100")
                http_gate(describe("services", "janus-api")["status"]["url"], receipt["sha"])
            published = {**receipt, "wbs_id": os.environ["JANUS_WBS_ID"],
                         "acceptance_uri": os.environ["JANUS_ACCEPTANCE_URI"],
                         "candidates": candidates, "status": "PASS", "promotion": "PASS", "runtime_acceptance": "PASS"}
            output = state / "published.json"
            output.write_text(json.dumps(published, indent=2) + "\n")
            receipt.update(published)
            updated.clear()
        else:
            receipt.update({"candidates": candidates, "status": "PARTIAL",
                        "promotion": "NOT_RUN", "blocker": "authenticated API acceptance and canonical cutover pending"})
    except Exception as error:
        receipt.update({"status": "FAILED", "error_code": type(error).__name__,
                        "failure_classification": "TIMEOUT_INSPECT_EXECUTION" if isinstance(error, TimeoutError) else "GATE_OR_DEPLOYMENT",
                        "promotion": "NOT_COMPLETE"})
        raise
    finally:
        # Candidate validation rolls jobs back until all four gates pass.
        # Existing executions are immutable; never cancel or redispatch them.
        rollback_failed = False
        for job in reversed(updated):
            old_image = previous[job]["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["image"]
            try:
                ensure_idle(job)
                command("run", "jobs", "update", job, f"--image={old_image}", *restore_version_flags(previous[job]))
            except Exception:
                rollback_failed = True
        for name in paused if not rollback_failed else []:
            try:
                v2.run("gcloud", "scheduler", "jobs", "resume", name, f"--project={PROJECT}", f"--location={REGION}", "--quiet")
            except Exception:
                rollback_failed = True
        if release and receipt.get("status") != "PASS" and "api_before" in locals():
            traffic = ",".join(f"{t['revisionName']}={t['percent']}" for t in original_traffic if t.get("percent", 0))
            try:
                command("run", "services", "update-traffic", "janus-api", f"--to-revisions={traffic}")
            except Exception:
                rollback_failed = True
        if release and receipt.get("status") == "PASS" and not rollback_failed:
            try:
                v2.run("gcloud", "storage", "cp", str(state / "published.json"), BUCKET + "/published.json",
                       "--if-generation-match=" + (state / "baseline-generation").read_text().strip(), "--quiet")
            except Exception:
                rollback_failed = True
                receipt["status"] = "FAILED_BASELINE_COMMIT"
        receipt["job_rollback_and_schedule_restore"] = "FAILED" if rollback_failed else "PASS"
        output = state / "candidate-receipt.json"
        output.write_text(json.dumps(receipt, indent=2) + "\n")
        v2.run("gcloud", "storage", "cp", str(output), BUCKET + f"/evidence/{build_id}/{os.environ.get('JANUS_VALIDATION_ID', 'candidate')}-receipt.json", "--if-generation-match=0", "--quiet")
        if not rollback_failed:
            v2.run("gcloud", "storage", "rm", lock_uri, f"--if-generation-match={generation}", "--quiet")
        if rollback_failed:
            raise RuntimeError("rollback/restore failed; deployment mutex retained for recovery")


if __name__ == "__main__":
    main()
