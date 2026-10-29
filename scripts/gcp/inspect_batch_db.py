"""Read-only database diagnostic for batch acceptance using existing ingestion runtime."""
from base64 import b64encode
import json
import os
from pathlib import Path
import subprocess
import sys
import time

SCRIPT = '''import json
from ingestion_core.__main__ import _control_plane

with _control_plane() as control, control.connection.cursor() as cur:
    # 1. Recent executions
    cur.execute("""SELECT execution_id, config_id, status, error_code,
                   started_at, finished_at, request_options
                   FROM control.executions
                   ORDER BY requested_at DESC LIMIT 5""")
    execs = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    # 2. Failed items in recent executions
    cur.execute("""SELECT execution_id, item_key, source_id, dataset_id,
                   state, error_code, safe_message
                   FROM control.execution_items
                   WHERE state != 'success'
                   ORDER BY execution_id DESC LIMIT 20""")
    failed_items = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    # 3. Controlled occurrences
    cur.execute("""SELECT occurrence_id, scheduled_at, state->>'status' as status,
                   state->>'reason' as reason, state->>'execution' as execution
                   FROM control.batch_occurrences
                   WHERE occurrence_id LIKE 'controlled%'
                   ORDER BY scheduled_at DESC LIMIT 20""")
    controlled_rows = [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    # 4. Stock supplement requests summary
    cur.execute("SELECT status, count(*) FROM control.stock_supplement_requests GROUP BY status")
    supplements = dict(cur.fetchall())

print("=== DB_DIAGNOSTIC_BEGIN ===")
print(json.dumps({
    "recent_executions": execs,
    "failed_items": failed_items,
    "controlled_occurrences": controlled_rows,
    "supplements": supplements
}, default=str))
print("=== DB_DIAGNOSTIC_END ===")
'''

def main():
    sys.path.insert(0, str(Path(__file__).parent.resolve()))
    from ghcr_jobs_rollout import cloud, job, terminal, ROOT, PROJECT, REGION

    source = job('janus-ingestion-core')
    container = source['template']['template']['containers'][0]
    args = (['python'] if not container.get('command') else []) + ['-c', SCRIPT]
    override = {'args': args}
    if container.get('name'):
        override['name'] = container['name']
    payload = {
        'etag': source['etag'],
        'overrides': {'taskCount': 1, 'timeout': '180s', 'containerOverrides': [override]}
    }

    print("Dispatching diagnostic on janus-ingestion-core...")
    operation = cloud(f'{ROOT}/jobs/janus-ingestion-core:run', payload, 'POST')
    name = operation.get('name', '')
    if not name.startswith(ROOT + '/operations/'):
        print(f"Failed to dispatch: {operation}")
        sys.exit(1)

    print(f"Dispatched operation: {name}")
    deadline = time.monotonic() + 240
    execution_name = ""
    while time.monotonic() < deadline:
        current = cloud(name)
        if current.get('done'):
            if current.get('error'):
                print(f"Operation error: {current.get('error')}")
                sys.exit(1)
            resp = current.get('response', {})
            execution_name = resp.get('name', '')
            break
        time.sleep(5)

    if not execution_name:
        print("Timed out waiting for operation.")
        sys.exit(1)

    print(f"Execution completed: {execution_name}")
    # Wait for execution to be terminal
    for _ in range(30):
        ex = cloud(execution_name)
        if terminal(ex):
            break
        time.sleep(3)

    short_name = execution_name.split("/")[-1]
    print(f"Reading logs for {short_name}...")
    log_cmd = [
        "gcloud", "logging", "read",
        f'labels."run.googleapis.com/execution_name"="{short_name}"',
        f"--project={PROJECT}",
        "--freshness=15m",
        "--limit=100",
        "--format=json"
    ]
    res = subprocess.run(log_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Logging read failed: {res.stderr}")
        sys.exit(1)

    try:
        entries = json.loads(res.stdout)
    except Exception as e:
        print(f"Failed to parse log entries: {e}\n{res.stdout}")
        sys.exit(1)

    full_text = ""
    for entry in reversed(entries):
        text = entry.get("textPayload") or ""
        full_text += text + "\n"

    if "=== DB_DIAGNOSTIC_BEGIN ===" in full_text:
        part = full_text.split("=== DB_DIAGNOSTIC_BEGIN ===")[1].split("=== DB_DIAGNOSTIC_END ===")[0].strip()
        data = json.loads(part)
        print("\n### DATABASE DIAGNOSTIC RESULTS")
        print(json.dumps(data, indent=2, default=str))

        # Format markdown summary
        md_lines = ["### Database Diagnostic Findings\n"]
        md_lines.append("#### Controlled Occurrences")
        for occ in data.get("controlled_occurrences", []):
            md_lines.append(f"- `{occ['occurrence_id']}`: status={occ['status']}, reason={occ['reason']}, execution={occ['execution']}")

        md_lines.append("\n#### Recent Executions")
        for ex in data.get("recent_executions", []):
            md_lines.append(f"- `{ex['execution_id']}`: config={ex['config_id']}, status={ex['status']}, error={ex['error_code']}")

        md_lines.append("\n#### Failed Execution Items")
        for item in data.get("failed_items", []):
            md_lines.append(f"- `{item['item_key']}` ({item['source_id']}/{item['dataset_id']}): state={item['state']}, error={item['error_code']}, message={item['safe_message']}")

        md_lines.append("\n#### Supplement Requests")
        for st, count in data.get("supplements", {}).items():
            md_lines.append(f"- {st}: {count}")

        report = "\n".join(md_lines)

        # Post to commit comment if CI
        gh_token = os.environ.get("GH_TOKEN")
        github_sha = os.environ.get("GITHUB_SHA")
        if gh_token and github_sha:
            repo = os.environ.get("GITHUB_REPOSITORY", "tommylin15/janus-omniforge")
            subprocess.run(["gh", "api", f"repos/{repo}/commits/{github_sha}/comments", "-f", f"body={report}"])
    else:
        print("Diagnostic marker not found in logs. Raw text:")
        print(full_text)

if __name__ == "__main__":
    main()
