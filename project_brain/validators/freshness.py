from __future__ import annotations

from datetime import datetime
from pathlib import Path

from project_brain.repository import BrainRepository, ValidationError


# Ensure generated reports are newer than their declared sources before commands trust them.
def check_derived_freshness(repo: BrainRepository) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for path in sorted(repo.derived_root.glob("*.md")):
        info = repo.parse_generated_header(path)
        if not info:
            errors.append(ValidationError(path.relative_to(repo.root).as_posix(), "derived file is missing generated header"))
            continue
        derived_mtime = path.stat().st_mtime
        for source in info.get("sources", []):
            source_path = repo.root / source
            if not source_path.exists():
                errors.append(ValidationError(path.relative_to(repo.root).as_posix(), f"derived file references missing source {source}"))
            elif source_path.stat().st_mtime > derived_mtime + 1e-6:
                errors.append(ValidationError(path.relative_to(repo.root).as_posix(), f"derived file is older than source {source}"))
    return errors
