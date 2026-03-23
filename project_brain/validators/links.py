from __future__ import annotations

from project_brain.loader import extract_wikilinks
from project_brain.repository import BrainRepository, ValidationError


# Resolve all declared IDs and explicit path references so rename drift becomes visible.
def check_links(repo: BrainRepository) -> list[ValidationError]:
    errors: list[ValidationError] = []
    id_index = build_id_index(repo)
    for task in repo.load_tasks():
        for dep in task.frontmatter.get("dependencies", []):
            if dep not in id_index:
                errors.append(ValidationError(task.rel_path, f"dependency {dep} does not resolve"))
        for doc_id in task.frontmatter.get("linked_canonical_docs", []):
            if doc_id not in id_index:
                errors.append(ValidationError(task.rel_path, f"linked_canonical_docs entry {doc_id} does not resolve"))
        for output in task.frontmatter.get("linked_output_files", []):
            path = repo.root / output
            if path.exists() and path.is_dir():
                errors.append(ValidationError(task.rel_path, f"linked_output_files entry {output} is a directory, not a file"))
    for handoff in repo.load_handoffs():
        for ref in handoff.frontmatter.get("canonical_refs", []):
            if ref not in id_index:
                errors.append(ValidationError(handoff.rel_path, f"canonical_refs entry {ref} does not resolve"))
    for plan in repo.load_plan_entries():
        if plan.frontmatter.get("task_id") not in id_index:
            errors.append(ValidationError(plan.rel_path, f"task_id {plan.frontmatter.get('task_id')} does not resolve"))
    for document in [repo.load_department_registry(), repo.load_schema_registry(), repo.load_retrieval_rules()]:
        for ref in extract_wikilinks(document.body):
            if ref not in id_index:
                errors.append(ValidationError(document.rel_path, f"wikilink {ref} does not resolve"))
    return errors


# A single ID index keeps validators and commands aligned on document resolution.
def build_id_index(repo: BrainRepository) -> dict[str, str]:
    docs = [repo.load(path) for path in repo.iter_vault_markdown()]
    for path in sorted(repo.migrations_root.glob("*.md")):
        docs.append(repo.load(path))
    index: dict[str, str] = {}
    for document in docs:
        identity = document.identity
        if identity:
            index[identity] = document.rel_path
    return index
