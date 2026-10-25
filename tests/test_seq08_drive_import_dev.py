"""SEQ08 private model bundle validation and GCS create-only safety."""
from hashlib import sha256
from io import BytesIO
import sys,zipfile
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/"scripts/gcp"))
from seq08_drive_import_dev import verified_extract,upload_create_only

def test_malformed_archive_fail_closed(tmp_path):
    b=BytesIO()
    with zipfile.ZipFile(b,"w") as z:z.writestr("quant.ubj",b"x")
    raw=b.getvalue()
    with pytest.raises(ValueError,match="unapproved"):
        verified_extract(raw,tmp_path,expected_sha=sha256(raw).hexdigest())
    with pytest.raises(ValueError,match="exact SHA"):
        verified_extract(raw,tmp_path,expected_sha="0"*64)

def test_existing_same_sha_can_reuse_but_never_rewrite():
    raw=b"real_model"
    records={"quant":{"object":"models/candidates/quant/x/model.ubj",
        "model_sha256":sha256(raw).hexdigest(),"source_file":"/unused"}}
    def onlyread(*args):
        assert args[0]=="cat"
        return 0,raw,""
    assert upload_create_only(records,apply=True,runner=onlyread)["quant"]=="EXISTS_SHA_VERIFIED"
    with pytest.raises(ValueError,match="hash conflict"):
        upload_create_only(records,apply=True,runner=lambda *a:(0,b"wrong",""))

def test_non_404_error_is_not_absence():
    records={"risk":{"object":"models/candidates/risk/x/model.ubj",
        "model_sha256":sha256(b"x").hexdigest(),"source_file":"/unused"}}
    with pytest.raises(RuntimeError,match="access/unknown"):
        upload_create_only(records,apply=True,runner=lambda *a:(1,b"","403 permission denied"))
    assert upload_create_only(records,apply=False,runner=lambda *a:(1,b"","404 not found"))["risk"]=="MISSING_NOT_WRITTEN"
