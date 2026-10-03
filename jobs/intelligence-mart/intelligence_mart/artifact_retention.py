"""Keep three specialist generations per symbol; retire their unused execution files."""
from datetime import datetime, timedelta
from hashlib import sha256
import json


def clean_specialist_artifacts(store, *, apply, now, active_executions=frozenset()):
    objects = store.objects("")
    by_name = {item["name"]: item for item in objects}
    documents, indexes = {}, []
    for item in objects:
        name = item["name"]
        if name.startswith("maintenance/specialists/retained-"):
            indexes.append(item)
            for document in json.loads(store.read(name))["executions"]:
                documents[document["execution_id"]] = document
    for name in by_name:
        if name.startswith("executions/") and name.endswith("/specialist-manifest.json"):
            document = json.loads(store.read(name))
            if document.get("artifact_kind") != "mart_specialist_execution_v1":
                raise ValueError("unknown specialist execution contract")
            document["retention_created_at"] = by_name[name]["updated"]
            documents[document["execution_id"]] = document
    generations = {}
    for execution_id, document in documents.items():
        for symbol in {ref["symbol"] for ref in document["specialists"]}:
            generations.setdefault(symbol, []).append((document["analysis_as_of"], document.get("retention_created_at", ""), execution_id))
    selected = {symbol: {execution_id for _, _, execution_id in sorted(values, reverse=True)[:3]}
                for symbol, values in generations.items()}
    for symbol, values in generations.items():
        selected[symbol].update(execution_id for _, _, execution_id in values if execution_id in active_executions)
    retained, live, candidates, retired = [], set(), set(), set()
    for execution_id, document in documents.items():
        prefix = f"executions/{execution_id}/"
        references = [ref for ref in document["specialists"] if execution_id in selected[ref["symbol"]]]
        live.update(ref["artifact_uri"].removeprefix(f"gs://{store.bucket}/") for ref in references)
        if references:
            retained.append({key: value for key, value in {**document, "specialists": references}.items()
                             if key in {"execution_id", "analysis_as_of", "retention_created_at", "core_snapshot_id", "specialists", "evaluation"}})
        if len(references) == len(document["specialists"]) and references:
            live.update(name for name in by_name if name.startswith(prefix))
        else:
            retired.add(execution_id)
            candidates.update(name for name in by_name if name.startswith(prefix) and name.rsplit("/", 1)[-1] in {
                "specialist-manifest.json", "specialist-targets.json", "screening.json",
                "market-membership.json", "oos-evaluation.json"})
    # OOS training models are in memory, not persisted weights. Only the newest retained OOS result is used.
    evaluated = sorted((doc["analysis_as_of"], doc.get("retention_created_at", ""), doc["execution_id"], doc["evaluation"]["artifact_uri"])
                       for doc in retained if "evaluation" in doc)
    for _, _, execution_id, uri in evaluated[:-1]:
        if execution_id in active_executions:
            continue
        name = uri.removeprefix(f"gs://{store.bucket}/")
        live.discard(name)
        candidates.add(name)
        retired.add(execution_id)
    if evaluated:
        latest_evaluation = evaluated[-1][3].removeprefix(f"gs://{store.bucket}/")
        live.add(latest_evaluation)
    for document in retained:
        if "evaluation" in document and evaluated and document["evaluation"]["artifact_uri"] != evaluated[-1][3] \
                and document["execution_id"] not in active_executions:
            document.pop("evaluation")
    for execution_id in retired:
        for name in by_name:
            if name.startswith(f"executions/{execution_id}/") and name.rsplit("/", 1)[-1] in {
                "specialist-manifest.json", "specialist-targets.json", "screening.json", "market-membership.json"}:
                live.discard(name)
                candidates.add(name)
    for item in objects:
        name = item["name"]
        if name.startswith("specialists/") and name not in live:
            # Completed superseded outputs can be removed immediately; unfinished outputs get seven days.
            referenced = any(ref["artifact_uri"] == f"gs://{store.bucket}/{name}"
                             for doc in documents.values() for ref in doc["specialists"])
            if referenced or datetime.fromisoformat(item["updated"].replace("Z", "+00:00")) < now - timedelta(days=7):
                candidates.add(name)
        elif name.startswith("executions/") and name.endswith("/oos-evaluation.json") and name not in live \
                and name.split("/")[1] not in active_executions \
                and datetime.fromisoformat(item["updated"].replace("Z", "+00:00")) < now - timedelta(days=7):
            candidates.add(name)
    candidates.difference_update(live)
    candidates.intersection_update(by_name)
    index = {"policy": "specialist-retention-v1", "generations_per_symbol": 3,
             "executions": sorted(retained, key=lambda doc: doc["execution_id"])}
    payload = json.dumps(index, sort_keys=True, separators=(",", ":")).encode()
    index_name = "maintenance/specialists/retained-" + sha256(payload).hexdigest() + ".json"
    if apply:
        for document in retained:
            for ref in [*document["specialists"], *([document["evaluation"]] if "evaluation" in document else [])]:
                name = ref["artifact_uri"].removeprefix(f"gs://{store.bucket}/")
                if not name.startswith(("specialists/", f"executions/{document['execution_id']}/")):
                    raise ValueError("artifact reference escaped its public Mart prefix")
                if "sha256:" + sha256(store.read(name)).hexdigest() != ref["artifact_hash"]:
                    raise RuntimeError("retained artifact hash mismatch")
        if not store.create(index_name, payload, "application/json") and store.read(index_name) != payload:
            raise RuntimeError("retention index conflict")
        for execution_id in retired:
            name = f"executions/{execution_id}/specialist-retired.json"
            marker = json.dumps({"execution_id": execution_id, "policy": index["policy"]}).encode()
            if not store.create(name, marker, "application/json") and store.read(name) != marker:
                raise RuntimeError("retirement marker conflict")
        for name in sorted(candidates):
            store.delete(name, generation=by_name[name]["generation"])
        for item in indexes:
            if item["name"] != index_name:
                store.delete(item["name"], generation=item["generation"])
        for name in live:
            if name.startswith("specialists/"):
                store.read(name)
    return {"policy": index["policy"], "generations_per_symbol": 3,
            "planned_objects": len(candidates), "deleted_objects": len(candidates) if apply else 0,
            "planned_bytes": sum(int(by_name[name]["size"]) for name in candidates),
            "retained_generations": {symbol: len(values) for symbol, values in selected.items()},
            "core_snapshot_ids": sorted({doc["core_snapshot_id"] for doc in retained}),
            "index_uri": f"gs://{store.bucket}/{index_name}" if apply else None}
