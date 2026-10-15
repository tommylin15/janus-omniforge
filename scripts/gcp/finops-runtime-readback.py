"""Read-only Cloud Run JSON identity/fence metadata; never print environment values."""
from __future__ import annotations
import json
import sys


def nested_containers(node):
    if isinstance(node, dict):
        c = node.get("containers")
        if isinstance(c, list):
            yield from (item for item in c if isinstance(item, dict))
        for value in node.values():
            yield from nested_containers(value)
    elif isinstance(node, list):
        for value in node:
            yield from nested_containers(value)


def summarize(job):
    container = next((c for c in nested_containers(job) if c.get("image")), {})
    env = container.get("env") or []
    fence = next((e for e in env if e.get("name") == "CORE_RETENTION_FENCE_URI"), None)
    return {
        "job": (job.get("metadata", {}).get("name") or job.get("name", "")).split("/")[-1],
        "image": container.get("image"),
        "retention_fence_env_present": fence is not None,
        "retention_fence_static_value": bool(fence and fence.get("value")),
        "mode_env_names": sorted(e["name"] for e in env if e.get("name") in {
            "ICEBERG_MAINTENANCE_MODE", "BATCH_CONTROLLER_MODE", "CORE_RETENTION_FENCE_URI"
        }),
        "containers_detected": bool(container),
    }


if __name__ == "__main__":
    print(json.dumps(summarize(json.load(sys.stdin)), sort_keys=True))
