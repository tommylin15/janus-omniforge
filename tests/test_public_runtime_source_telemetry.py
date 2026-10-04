import json
from pathlib import Path

from services.api.public_runtime import _emit_core_query_source


def test_core_query_source_telemetry_is_bounded(capsys):
    _emit_core_query_source("core.ohlcv_v1", "serving_projection")
    event = json.loads(capsys.readouterr().out)
    assert event == {
        "component": "janus-api",
        "dataset": "ohlcv",
        "operation": "core_query_source",
        "source": "serving_projection",
    }


def test_projection_hit_emits_telemetry_before_return():
    source = (Path(__file__).resolve().parents[1] / "services/api/public_runtime.py").read_text(encoding="utf-8")
    marker = '_emit_core_query_source(identifier, "serving_projection")'
    assert marker in source
    projection_branch = source.split("if rows:", 1)[1].split("return rows", 1)[0]
    assert marker in projection_branch
