"""Verify the candidate's frozen input manifest, not supplier-certified completeness."""

import hashlib, json
from pathlib import Path
from .contracts import STAGES, read_batch
from .changes import ValidationError


def validate_manifest(data_dir: Path, through: str) -> dict:
    manifest = json.loads((data_dir / "manifest.json").read_text())
    if manifest["scope"] != "supplied_bird_strikes_assessment":
        raise ValidationError("Unexpected snapshot scope")
    for stage in STAGES[: STAGES.index(through) + 1]:
        item = manifest["batches"][stage]
        path = data_dir / f"Bird Strikes - {stage}.csv"
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise ValidationError(f"{stage}: input checksum differs from manifest")
        rows, blank, headers, encoding, sha = read_batch(path, stage)
        if len(rows) != item["valid_rows"] or blank != item["blank_rows"]:
            raise ValidationError(f"{stage}: row counts differ from manifest")
    if not manifest["batches"]["Final"]["authoritative_snapshot"]:
        raise ValidationError("Final not declared an authoritative snapshot")
    return manifest
