"""SEQ-08: scoped Drive bundle -> existing Dev GCS candidates; never promote a model."""
import argparse
from hashlib import sha256
from io import BytesIO
import json, os, subprocess, tempfile, zipfile
from pathlib import Path
from urllib.request import Request, urlopen
from seq08_candidate_import import verify, EXPECTED

PROJECT="gen-lang-client-0593591102"
BUCKET=PROJECT+"-dev-mart"
DRIVE_FILE_ID="1hcysaHpaExtgB-OqFfWu3i3qNBSe7Gz1"
BUNDLE_SHA="91df593d9d13cad1858017f989e568c82ece99ca80fa900c6443073a342545a8"
MAX_BYTES=2*1024*1024

def obtain(token, *, opener=urlopen):
    if not token or len(token)<12: raise ValueError("missing scoped Drive token")
    url="https://www.googleapis.com/drive/v3/files/"+DRIVE_FILE_ID+"?alt=media"
    req=Request(url,headers={"Authorization":"Bearer "+token})
    with opener(req,timeout=60) as response: raw=response.read(MAX_BYTES+1)
    if not raw or len(raw)>MAX_BYTES: raise ValueError("invalid Drive bundle size")
    return raw

def verified_extract(raw, directory, *, expected_sha=BUNDLE_SHA, verifier=verify):
    if sha256(raw).hexdigest()!=expected_sha: raise ValueError("Drive ZIP exact SHA mismatch")
    names={f"{k}.ubj" for k in EXPECTED}|{"manifest.json","README.txt"}
    base=Path(directory)
    with zipfile.ZipFile(BytesIO(raw)) as z:
        infos=z.infolist()
        if len(infos)!=len(names) or {i.filename for i in infos}!=names:
            raise ValueError("unapproved ZIP members or missing model head")
        for i in infos:
            if i.is_dir() or i.file_size>1_000_000 or "/" in i.filename or "\\" in i.filename:
                raise ValueError("unbounded or unsafe model file")
            (base/i.filename).write_bytes(z.read(i))
    bundle=json.loads((base/"manifest.json").read_text(encoding="utf-8"))
    checked=verifier(bundle,base)
    for k,v in checked.items():
        if bundle[k].get("sha256")!=v["model_sha256"] or bundle[k].get("byte_count")!=v["bytes"]:
            raise ValueError(k+": bundle metadata mismatch")
    return checked

def cloud(*args):
    r=subprocess.run(["gcloud","storage",*args,"--project",PROJECT],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=100,check=False)
    return r.returncode,r.stdout,r.stderr.decode("utf-8","replace").lower()

def upload_create_only(checked, *, apply=False, runner=cloud):
    result={}
    for key,item in checked.items():
        uri=f"gs://{BUCKET}/{item['object']}"
        code,data,err=runner("cat",uri)
        if code==0:
            if sha256(data).hexdigest()!=item["model_sha256"]:
                raise ValueError(key+": existing GCS model hash conflict")
            result[key]="EXISTS_SHA_VERIFIED"
            continue
        if not any(x in err for x in ("404","not found","no urls matched","matched no objects","no objects matched","does not exist")):
            raise RuntimeError(key+": GCS access/unknown status")
        if not apply:
            result[key]="MISSING_NOT_WRITTEN"
            continue
        code,_,_=runner("cp",item["source_file"],uri,"--if-generation-match=0")
        if code: raise RuntimeError(key+": create-only upload failed")
        code,data,_=runner("cat",uri)
        if code or sha256(data).hexdigest()!=item["model_sha256"]:
            raise RuntimeError(key+": uploaded model readback mismatch")
        result[key]="CREATE_ONLY_SHA_READBACK_PASS"
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    with tempfile.TemporaryDirectory() as directory:
        checked=verified_extract(obtain(os.environ.get("SEQ08_DRIVE_READ_TOKEN","")),directory)
        results=upload_create_only(checked,apply=args.apply)
    print(json.dumps({"status":"GCS_CANDIDATES_READBACK_PASS" if args.apply else "PREFLIGHT_ONLY",
        "source_bundle_sha256":BUNDLE_SHA,"results":results,
        "model_sha256":{k:v["model_sha256"] for k,v in checked.items()},
        "registry_writes":0,"pg_writes":0,"api_traffic_writes":0,"owner_writes":0},sort_keys=True))
if __name__=="__main__":main()
