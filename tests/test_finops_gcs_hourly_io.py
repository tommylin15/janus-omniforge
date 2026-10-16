import importlib.util
from pathlib import Path
m=importlib.util.module_from_spec(importlib.util.spec_from_file_location("finopsio",Path("scripts/gcp/finops_gcs_hourly_io.py")))
m.__spec__.loader.exec_module(m)

def test_hourly_aggregation_is_bucket_and_method_scoped():
    def row(bucket,method,num):
        return {"resource":{"labels":{"bucket_name":bucket}},
                "metric":{"labels":{"method":method}},
                "points":[{"interval":{"endTime":"2026-10-15T04:05:00Z"},"value":{"int64Value":str(num)}}]}
    rows=m.aggregate([row(m.BUCKET,"ReadObject",7),row("unrelated","ReadObject",500),
                      row(m.BUCKET,"GetObjectMetadata",3),row(m.BUCKET,"OtherMethod",200)])
    assert len(rows)==1
    assert rows[0]["hour"]=="2026-10-15 12:00 +08"
    assert rows[0]["ReadObject"]==7 and rows[0]["GetObjectMetadata"]==3
    assert rows[0]["ListObjects"]==0

def test_delta_ending_on_hour_boundary_belongs_to_preceding_hour():
    row={"resource":{"labels":{"bucket_name":m.BUCKET}},
         "metric":{"labels":{"method":"ReadObject"}},
         "points":[{"interval":{"endTime":"2026-10-15T04:00:00Z"},"value":{"int64Value":"7"}}]}
    assert m.aggregate([row])[0]["hour"]=="2026-10-15 11:00 +08"
