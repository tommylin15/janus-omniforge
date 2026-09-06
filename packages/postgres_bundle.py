"""Load a bounded PostgreSQL credential bundle without logging its payload."""

from __future__ import annotations

import json
import os
from typing import Mapping


def load_postgres_bundle(env_name: str, fields: Mapping[str, str]) -> None:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return
    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{env_name} must contain a JSON object") from error
    if not isinstance(bundle, dict):
        raise ValueError(f"{env_name} must contain a JSON object")
    missing = [target for target, source in fields.items() if not str(bundle.get(source, "")).strip()]
    if missing:
        raise ValueError(f"{env_name} is missing: {','.join(missing)}")
    for target, source in fields.items():
        os.environ.setdefault(target, str(bundle[source]).strip())
