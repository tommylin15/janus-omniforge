"""Diagnostic collector for Janus Three Pipelines dev acceptance."""
import json
import os
import subprocess
import sys

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
JOBS = [
    "janus-batch-controller",
    "janus-ingestion-core",
    "janus-intelligence-mart",
    "janus-private-pipeline",
]


def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return -1, "", str(e)


def get_executions(job_name):
    cmd = [
        "gcloud", "run", "jobs", "executions", "list",
        f"--job={job_name}",
        f"--project={PROJECT}",
        f"--region={REGION}",
        "--limit=3",
        "--format=json",
    ]
    code, stdout, stderr = run_cmd(cmd)
    if code != 0 or not stdout.strip():
        return []
    try:
        return json.loads(stdout)
    except Exception:
        return []


def describe_execution(exec_name):
    cmd = [
        "gcloud", "run", "jobs", "executions", "describe",
        exec_name,
        f"--project={PROJECT}",
        f"--region={REGION}",
        "--format=json",
    ]
    code, stdout, stderr = run_cmd(cmd)
    if code != 0 or not stdout.strip():
        return {}
    try:
        return json.loads(stdout)
    except Exception:
        return {}


def get_logs_for_job(job_name, freshness="2h", limit=40):
    cmd = [
        "gcloud", "logging", "read",
        f'resource.type="cloud_run_job" AND resource.labels.job_name="{job_name}"',
        f"--project={PROJECT}",
        f"--freshness={freshness}",
        f"--limit={limit}",
        "--format=json",
    ]
    code, stdout, stderr = run_cmd(cmd)
    if code != 0 or not stdout.strip():
        return []
    try:
        return json.loads(stdout)
    except Exception:
        return []


def get_logs_for_execution(exec_name, freshness="2h", limit=50):
    cmd = [
        "gcloud", "logging", "read",
        f'labels."run.googleapis.com/execution_name"="{exec_name}"',
        f"--project={PROJECT}",
        f"--freshness={freshness}",
        f"--limit={limit}",
        "--format=json",
    ]
    code, stdout, stderr = run_cmd(cmd)
    if code != 0 or not stdout.strip():
        return []
    try:
        return json.loads(stdout)
    except Exception:
        return []


def format_log_entry(entry):
    ts = entry.get("timestamp", "")
    sev = entry.get("severity", "INFO")
    msg = entry.get("textPayload")
    if msg is None:
        jp = entry.get("jsonPayload", {})
        msg = jp.get("message") or json.dumps(jp)
    return f"[{ts}] [{sev}] {msg}"


def main():
    title = sys.argv[1] if len(sys.argv) > 1 else "Acceptance Diagnostic"
    lines = [f"### {title}"]

    # 1. Inspect executions of all 4 jobs
    failed_executions = []
    lines.append("\n#### Job Executions Status")
    for job in JOBS:
        execs = get_executions(job)
        if not execs:
            lines.append(f"- **{job}**: No executions found")
            continue
        lines.append(f"- **{job}** ({len(execs)} recent):")
        for ex in execs:
            name = ex.get("metadata", {}).get("name", "unknown")
            status = ex.get("status", {})
            succeeded = status.get("succeededCount", 0)
            failed = status.get("failedCount", 0)
            conditions = status.get("conditions", [])
            cond_str = ", ".join(f"{c.get('type')}={c.get('status')}:{c.get('message', c.get('reason'))}" for c in conditions)
            created = ex.get("metadata", {}).get("creationTimestamp", "")
            lines.append(f"  - `{name}` (created {created}): succeeded={succeeded}, failed={failed} [{cond_str}]")
            if failed > 0 or any(c.get("status") == "False" for c in conditions if c.get("type") == "Completed"):
                failed_executions.append((job, name))

    # 2. Get recent controller logs
    lines.append("\n#### Recent Controller Logs (janus-batch-controller)")
    ctrl_logs = get_logs_for_job("janus-batch-controller", freshness="2h", limit=50)
    if ctrl_logs:
        # Sort ascending by timestamp
        ctrl_logs.sort(key=lambda x: x.get("timestamp", ""))
        lines.append("```")
        for entry in ctrl_logs[-30:]:
            lines.append(format_log_entry(entry))
        lines.append("```")
    else:
        lines.append("_No controller logs returned by Cloud Logging in last 2h._")

    # 3. Get logs for failed executions
    for job, name in failed_executions:
        if job == "janus-batch-controller":
            continue
        lines.append(f"\n#### Failed Execution Logs: `{name}` ({job})")
        exec_logs = get_logs_for_execution(name, freshness="2h", limit=50)
        if exec_logs:
            exec_logs.sort(key=lambda x: x.get("timestamp", ""))
            lines.append("```")
            for entry in exec_logs[-30:]:
                lines.append(format_log_entry(entry))
            lines.append("```")
        else:
            lines.append(f"_No specific logs for {name}_")

    report = "\n".join(lines)
    print(report)

    # Post to commit comments if GH_TOKEN and GITHUB_SHA present
    gh_token = os.environ.get("GH_TOKEN")
    github_sha = os.environ.get("GITHUB_SHA")
    if gh_token and github_sha:
        repo = os.environ.get("GITHUB_REPOSITORY", "tommylin15/janus-omniforge")
        # Ensure report isn't too huge for GitHub comment (max 65536 chars)
        if len(report) > 60000:
            report = report[:60000] + "\n...[truncated]"
        run_cmd(["gh", "api", f"repos/{repo}/commits/{github_sha}/comments", "-f", f"body={report}"])


if __name__ == "__main__":
    main()
