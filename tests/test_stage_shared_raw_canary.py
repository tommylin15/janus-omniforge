"""The live Stage dedupe canary is scoped, generation-fenced and self-cleaning."""
import importlib.util
import json
from pathlib import Path
import pytest


class MemoryStage:
    bucket = "gen-lang-client-0593591102-dev-stage"

    def __init__(self, corrupt_read=False):
        self.items = {}
        self.deleted = []
        self.corrupt_read = corrupt_read

    def create(self, name, payload, content_type):
        if name in self.items:
            return False
        self.items[name] = (payload, str(len(self.items) + 1))
        return True

    def read(self, name):
        if self.corrupt_read and name.endswith("/payload.json"):
            return b"corrupted"
        return self.items[name][0]

    def objects(self, prefix):
        return tuple({"name": name, "size": str(len(payload)),
                      "generation": generation, "updated": "2026-10-20T00:00:00Z"}
                     for name, (payload, generation) in self.items.items()
                     if name.startswith(prefix))

    def delete(self, name, *, generation):
        assert name in self.items
        assert self.items[name][1] == generation
        self.deleted.append((name, generation))
        del self.items[name]


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts/gcp/stage_shared_raw_canary.py"
    spec = importlib.util.spec_from_file_location("stage_live_dedupe_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("corrupt", [False, True])
def test_shared_raw_canary_generations_and_failure_cleanup(monkeypatch, capsys, corrupt):
    module, store = load_module(), MemoryStage(corrupt_read=corrupt)
    monkeypatch.setattr(module, "GcsObjectStore", lambda bucket: store)
    monkeypatch.setenv("STAGE_BUCKET", store.bucket)
    monkeypatch.setenv("JANUS_STAGE_DEDUPE_CANARY_APPROVED", "true")
    if corrupt:
        with pytest.raises(RuntimeError, match="stage_shared_raw_live_canary_failed"):
            module.main()
    else:
        module.main()
        result = json.loads(capsys.readouterr().out)
        assert result["status"] == "PASS"
        assert result["proof"]["raw_created_once"]
        assert result["proof"]["second_execution_reused"]
        assert result["proof"]["distinct_provenance_manifests"]
        assert result["deleted_canary_objects"] == 4
    assert not store.items and len(store.deleted) == 4


def test_shared_raw_canary_rejects_wrong_bucket_before_any_write(monkeypatch):
    module = load_module()
    monkeypatch.setenv("STAGE_BUCKET", "some-other-bucket")
    monkeypatch.setenv("JANUS_STAGE_DEDUPE_CANARY_APPROVED", "true")
    with pytest.raises(RuntimeError, match="scope_required"):
        module.main()
