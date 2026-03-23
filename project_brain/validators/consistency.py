from __future__ import annotations

from project_brain.repository import BrainRepository, ValidationError


# Check business invariants that relate task status to actual repository artifacts.
def check_consistency(repo: BrainRepository) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for task in repo.load_tasks():
        status = task.frontmatter.get("status")
        outputs = [repo.root / output for output in task.frontmatter.get("linked_output_files", [])]
        if status == "complete":
            for output in outputs:
                if not output.exists():
                    errors.append(ValidationError(task.rel_path, f"complete task is missing output file {output.relative_to(repo.root).as_posix()}"))
                elif output.is_dir():
                    errors.append(ValidationError(task.rel_path, f"complete task output {output.relative_to(repo.root).as_posix()} is a directory"))
    handoffs = sorted(repo.load_handoffs(), key=lambda doc: (doc.frontmatter.get("created_at", ""), doc.frontmatter.get("handoff_id", "")))
    ids = [doc.frontmatter.get("handoff_id", "") for doc in handoffs]
    if ids != sorted(ids):
        errors.append(ValidationError(repo.handoff_root.relative_to(repo.root).as_posix(), "handoff IDs are not monotonic relative to timestamp ordering"))
    return errors
