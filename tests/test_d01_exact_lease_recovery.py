from pathlib import Path
from types import SimpleNamespace
import re
import sys
from textwrap import dedent

import pytest


@pytest.mark.parametrize('done,error,count,identity', [
    (True, None, 1, 'exact'), (False, None, 1, 'exact'),
    (True, {'code': 1}, 1, 'exact'), (True, None, 0, 'exact'),
    (True, None, 1, 'other'),
])
def test_recovery_requires_original_successful_operation(monkeypatch, done, error, count, identity):
    source = (Path(__file__).parents[1] / '.github/workflows/d01-owner-eod-1016-lease-recovery.yml').read_text()
    code = dedent(re.search(r"python - <<'PY'\n(.*?)\n          PY", source, re.S).group(1))
    execution = {'name': 'exact', 'succeededCount': count}
    operation = {'done': done, 'error': error, 'response': {'name': identity}}
    fences = []
    fake = SimpleNamespace(ROOT='root', cloud=lambda path: operation if '/operations/' in path else execution,
                           terminal=lambda _: True, fence=lambda: fences.append(True),
                           scheduler=lambda: {'state': 'ENABLED'})
    monkeypatch.setitem(sys.modules, 'ghcr_jobs_rollout', fake)
    if done and not error and count == 1 and identity == 'exact':
        exec(compile(code, '<recovery>', 'exec'), {})
        assert fences == [True]
    else:
        with pytest.raises(RuntimeError, match='not_proven_successful'):
            exec(compile(code, '<recovery>', 'exec'), {})
        assert not fences
