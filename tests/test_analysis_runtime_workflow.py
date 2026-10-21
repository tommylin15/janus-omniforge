"""Real product acceptance uses the released Mart without traffic/config writes."""
import ast
from pathlib import Path
import re
import yaml


def test_existing_mart_acceptance_checks_source_and_avoids_deployment():
    workflow = yaml.safe_load(Path('.github/workflows/analysis-product-runtime-dev.yml').read_text())
    assert workflow['concurrency']['group'] == 'janus-dev-runtime-writers'
    script = '\n'.join(step.get('run', '') for step in workflow['jobs']['baseline']['steps'])
    for embedded in re.findall(r"python - <<'PY'\n(.*?)\nPY", script, re.S):
        ast.parse(embedded)
    assert "path=ROOT+'/jobs/janus-intelligence-mart'" in script
    assert "metadata['Labels']['org.opencontainers.image.revision']==os.environ['PRODUCT_SHA']" in script
    assert "execution_fence()" in script and 'fence()' in script
    assert "'value':'deep-coverage'" in script
    assert "'name':'MART_AI_ENABLED','value':'false'" in script
    assert 'no automatic retry' in script and 'len(results)==2' in script
    assert 'update-traffic' not in script and 'gcloud run deploy' not in script
    assert 'ghcr_release_lease.py acquire' in script
    assert 'ghcr_release_lease.py release --safe-to-release' in script
