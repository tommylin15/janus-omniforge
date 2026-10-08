"""Dev CI/CD planning and digest reference fence; no third-party dependencies."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

PROJECT = "gen-lang-client-0593591102"
REGION = "us-central1"
COMPONENTS = ("ingestion-core", "intelligence-mart", "private-pipeline", "api")
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def select_components(paths: list[str]) -> list[str]:
    selected = set()
    for path in paths:
        if path.startswith(("doc/", "archive/")) or path.endswith(".md"):
            continue
        if path.startswith(("packages/", "infra/postgres/", "scripts/gcp/")) or path in {
            "cloudbuild.yaml", "cloudbuild-v2.yaml", ".dockerignore", "requirements-dev.txt",
        }:
            selected.update(COMPONENTS)
        elif path.startswith("jobs/ingestion-core/"):
            selected.add("ingestion-core")
            if path.endswith(("retention.py", "stage.py", "iceberg_maintenance.py")):
                selected.add("intelligence-mart")
        elif path.startswith("jobs/intelligence-mart/"):
            selected.add("intelligence-mart")
        elif path.startswith("services/api/"):
            selected.update(("private-pipeline", "api"))
        elif path.startswith(("apps/user_app/", "apps/web/static/")):
            selected.add("api")
    return [component for component in COMPONENTS if component in selected]


def run(*args: str) -> str:
    # Never print argv or subprocess output on failure: future commands may
    # contain sensitive metadata. gcloud commands here only query safe fields.
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"command failed: {args[0]}")
    return result.stdout.strip()


def gcloud(*args: str):
    return json.loads(run("gcloud", *args, f"--project={PROJECT}", "--format=json"))


def image_references(value) -> set[str]:
    """Walk v1/v2 Run resource shapes without relying on image tags."""
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"image", "imageDigest"} and isinstance(child, str):
                if "@" in child:
                    digest = child.rsplit("@", 1)[1]
                    if not DIGEST.fullmatch(digest):
                        raise ValueError("invalid runtime digest")
                    found.add(child)
                elif key == "image":
                    raise ValueError("mutable runtime image; resolve before cleanup")
            else:
                found.update(image_references(child))
    elif isinstance(value, list):
        for child in value:
            found.update(image_references(child))
    return found


def inventory() -> dict:
    buckets = gcloud("storage", "buckets", "list")
    legacy = PROJECT + "_" + "cloudbuild"
    regional = PROJECT + "-cloudbuild-regional"
    names = {bucket.get("name", bucket.get("id", "")).removeprefix("gs://").rstrip("/"): bucket
             for bucket in buckets}
    approved = names.get(regional, {})
    return {
        "legacy_bucket_exists": legacy in names,
        "regional_bucket_location": approved.get("location"),
        "connections": gcloud("builds", "connections", "list", f"--region={REGION}"),
        "triggers": gcloud("builds", "triggers", "list", f"--region={REGION}"),
    }


def cleanup_plan(candidate_images: list[str]) -> dict:
    """Dry-run only. Protect all regional services, revisions, jobs, executions.

    No limit on reference enumeration; incomplete/permission-denied inventory
    fails closed. Regional repository images may be used by other workloads.
    Cross-region references must be ruled out separately before any deletion.
    """
    protected = image_references([{"image": image} for image in candidate_images])
    for resource in ("services", "revisions", "jobs"):
        resources = gcloud("run", resource, "list", f"--region={REGION}")
        protected.update(image_references(resources))
        if resource == "jobs":
            for job in resources:
                name = job.get("metadata", {}).get("name") or job.get("name", "").rsplit("/", 1)[-1]
                if not name:
                    raise ValueError("job inventory missing name")
                executions = gcloud("run", "jobs", "executions", "list", f"--job={name}", f"--region={REGION}")
                protected.update(image_references(executions))
    images = gcloud("artifacts", "docker", "images", "list",
                    f"{REGION}-docker.pkg.dev/{PROJECT}/janusai-poc", "--include-tags")
    unused = []
    total = 0
    for image in images:
        digest = image.get("version", "").rsplit("/", 1)[-1]
        package = image.get("package", "").rsplit("/", 1)[-1]
        if not DIGEST.fullmatch(digest) or not package:
            raise ValueError("unrecognized Artifact Registry inventory")
        uri = f"{REGION}-docker.pkg.dev/{PROJECT}/janusai-poc/{package}@{digest}"
        size = int(image.get("metadata", image)["imageSizeBytes"])
        total += size
        if uri not in protected:
            unused.append({"image": uri, "bytes": size})
    return {"mode": "dry-run", "inventory_bytes": total,
            "protected": sorted(protected), "unreferenced": unused,
            "delete_allowed": False, "reason": "cross-region and candidate receipts required"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("plan", "inventory", "cleanup-plan"))
    parser.add_argument("--sha")
    parser.add_argument("--base")
    parser.add_argument("--component", action="append", choices=COMPONENTS)
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.action == "plan":
        if not args.sha or not SHA.fullmatch(args.sha):
            parser.error("full immutable commit SHA required")
        if run("git", "rev-parse", "HEAD") != args.sha:
            raise ValueError("checkout SHA mismatch")
        if args.base and not SHA.fullmatch(args.base):
            parser.error("full immutable base SHA required")
        # Explicit components are the bounded manual repair interface; an
        # absent baseline must build all, never silently omit older pushes.
        paths = run("git", "diff", "--name-only", args.base, args.sha).splitlines() if args.base else []
        result = {"sha": args.sha, "base": args.base,
                  "components": args.component or (select_components(paths) if args.base else list(COMPONENTS)),
                  "changed_paths": paths}
    elif args.action == "inventory":
        result = inventory()
    else:
        result = cleanup_plan(args.candidate)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"action": args.action, "output": args.output}))


if __name__ == "__main__":
    main()
