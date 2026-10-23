"""Static, offline contract for Stage 05.1 -> 06/07/08/09 research handoff.

These tests do not claim live Parquet coverage or OOS quality.
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOW = ROOT / "research" / "colab" / "four_model_pipeline_03_11"


def notebook(name):
    p = FLOW / name
    obj = json.loads(p.read_text(encoding="utf-8"))
    assert obj["nbformat"] == 4
    for i, cell in enumerate(obj["cells"]):
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]), filename=f"{name}:{i}")
    return obj


def cell(obj, index=2):
    return "".join(obj["cells"][index]["source"])


def test_stage_051_pins_extended_x_and_original_y():
    nb = notebook("05.1_研究候選因子擴充.ipynb")
    assert nb["metadata"]["janus"]["version"] == "05.1.1"
    body = cell(nb)
    for token in (
        "X_extended_sha256",
        "original_y_sha256",
        "feature_order",
        "expected_order",
        "Y_stage05_relpath",
        "Y_reused_from_stage05",
        "STAGE05_1_X_EXTENDED_WITH_IMMUTABLE_STAGE05_Y",
        "CURRENT_CHANGED_DURING_05_1",
    ):
        assert token in body
    for f in (
        "ret10", "ret120", "bollinger_z20", "ret20_market_rank",
        "downside_vol20", "worst_daily_ret20", "amihud_illiquidity",
        "drawdown_from_high120", "revenue_sum6m", "revenue_mean12m",
        "revenue_growth_6m",
    ):
        assert f in body


def test_extended_training_roles_consume_051_and_do_not_relabel():
    for stage, name, role, count in [
        ("06", "06_Quant訓練.ipynb", "quant", 15),
        ("07", "07_Risk研究驗證.ipynb", "risk", 12),
        ("08", "08_Fundamental訓練.ipynb", "fundamental", 13),
    ]:
        nb = notebook(name)
        body = cell(nb)
        assert nb["metadata"]["janus"]["feature_source"] == "STAGE05_1_EXTENDED_X"
        assert f"role='{role}'" in body
        assert "source/role/'X_extended.parquet'" in body
        assert "out/'xy'/role/'Y_NOT_X.parquet'" in body
        assert "original_y_sha256" in body and "X_extended_sha256" in body
        assert "X_Y_KEY_ORDER_MISMATCH" in body
        assert "STAGE05_1_VERSION_MISMATCH_RERUN_05_1" in body
        assert "janus_train.fit_one(" in body
        assert "janus_train.run(" not in body
        assert "publication_allowed':False" in body
        assert f"'feature_slots':len(features)" in body
        assert f"expected_slots={{'quant':15,'risk':12,'fundamental':13}}" in body
        assert "CURRENT_SOURCE_DRIFT" in body
        assert f"out/'{stage}_train.json'" in body


def test_valuation_stays_five_features_and_mapping_blocked():
    nb = notebook("09_Valuation訓練.ipynb")
    body = cell(nb)
    assert nb["metadata"]["janus"]["feature_source"] == "STAGE05_VALUATION_UNCHANGED"
    assert "STAGE05_1_NOT_PASSED" in body
    assert "slots[role]['x_slots']==5" in body
    assert "VALUATION_MAPPING_MISSING" in body
    assert "VALUATION_REMAINS_5_FEATURES" in body
