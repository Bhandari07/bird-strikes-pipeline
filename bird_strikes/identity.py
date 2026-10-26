"""Stable, unambiguous serialization for incident and dimension hashes."""

import json, hashlib


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def key(*values):
    return hashlib.sha256(canonical(values).encode()).hexdigest()
