from __future__ import annotations

import difflib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_brain import miniyaml as yaml
from project_brain.loader import Document, extract_section
from project_brain.repository import BrainRepository, ValidationError, ValidationResult
from project_brain.validators import check_consistency, check_dag, check_derived_freshness, check_links, check_schema, check_schema_activation
from project_brain.validators.links import build_id_index


SCHEMA_FIXTURES = {
    "architecture-doc.schema.yaml": "schemas/architecture-doc.schema.yaml",
    "decision-record.schema.yaml": "schemas/decision-record.schema.yaml",
    "department-index.schema.yaml": "schemas/department-index.schema.yaml",
    "department-registry.schema.yaml": "schemas/department-registry.schema.yaml",
    "execution-plan-entry.schema.yaml": "schemas/execution-plan-entry.schema.yaml",
    "folder-index.schema.yaml": "schemas/folder-index.schema.yaml",
    "handoff-note.schema.yaml": "schemas/handoff-note.schema.yaml",
    "meta-document.schema.yaml": "schemas/meta-document.schema.yaml",
    "migration-spec.schema.yaml": "schemas/migration-spec.schema.yaml",
    "task.schema.yaml": "schemas/task.schema.yaml",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _starter_frontmatter(doc_type: str, **values: Any) -> dict[str, Any]:
    return {"schema_version": "1.0", "doc_type": doc_type, **values}


def init_brain(repo: BrainRepository) -> list[str]:
    if repo.is_initialized():
        raise FileExistsError(f"Refusing to initialize an existing brain target: {repo.describe_target()}")
    if repo.brain_root.exists() and any(repo.brain_root.iterdir()):
        raise FileExistsError(
            f"Refusing to initialize because the target brain directory already contains files: {repo.describe_target()}"
        )

    repo.vault_root.mkdir(parents=True, exist_ok=True)
    repo.schema_root.mkdir(parents=True, exist_ok=True)
    repo.migrations_root.mkdir(parents=True, exist_ok=True)
    created: list[str] = []

    for rel_dir in [
        "00_meta",
        "01_execution",
        "01_execution/tasks",
        "01_execution/plan-entries",
        "02_architecture",
        "02_architecture/decisions",
        "03_product",
        "04_engineering",
        "90_handoffs",
        "99_derived",
    ]:
        path = repo.vault_root / rel_dir
        path.mkdir(parents=True, exist_ok=True)
        created.append(path.relative_to(repo.root).as_posix() + "/")

    for name, fixture_rel in SCHEMA_FIXTURES.items():
        source = _package_root() / fixture_rel
        destination = repo.schema_root / name
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        created.append(destination.relative_to(repo.root).as_posix())

    repo.save_markdown(
        repo.meta_root / "departments.md",
        _starter_frontmatter(
            "department_registry",
            registry_id="DEPT-REGISTRY",
            last_reviewed=str(datetime.now(timezone.utc).date()),
            departments=[
                {
                    "department_slug": "product",
                    "title": "Product",
                    "folder_path": "03_product",
                    "index_doc_id": "DOC-product-index",
                    "index_path": "03_product/index.md",
                    "owner": "unassigned",
                    "status": "active",
                },
                {
                    "department_slug": "engineering",
                    "title": "Engineering",
                    "folder_path": "04_engineering",
                    "index_doc_id": "DOC-engineering-index",
                    "index_path": "04_engineering/index.md",
                    "owner": "unassigned",
                    "status": "active",
                },
            ],
        ),
        """## Registry Purpose
Defines the authoritative mapping between department slugs and folder locations.

## Department Entries
Seeded starter departments for new projects.

## Change Rules
Update this file and regenerate derived indexes in the same change.

## Validation Notes
Reject duplicate slugs, missing indexes, and unknown task departments.""",
    )
    created.append((repo.meta_root / "departments.md").relative_to(repo.root).as_posix())

    repo.save_markdown(
        repo.meta_root / "schema-registry.md",
        _starter_frontmatter(
            "meta_document",
            doc_id="DOC-schema-registry",
            title="Schema Registry",
            status="active",
            owner="unassigned",
            active_versions={
                "task": "1.0",
                "decision_record": "1.0",
                "handoff_note": "1.0",
                "department_index": "1.0",
                "architecture_doc": "1.0",
                "execution_plan_entry": "1.0",
                "migration_spec": "1.0",
                "department_registry": "1.0",
                "meta_document": "1.0",
                "folder_index": "1.0",
            },
        ),
        """## Purpose
Defines the active schema versions for each supported document type.

## Rules
Project-local schemas are authoritative at runtime. Built-in schemas are copied only during `brain init`.

## References
Keep this file aligned with the schema files stored under the selected brain root.""",
    )
    created.append((repo.meta_root / "schema-registry.md").relative_to(repo.root).as_posix())

    repo.save_markdown(
        repo.meta_root / "retrieval-rules.md",
        _starter_frontmatter(
            "meta_document",
            doc_id="DOC-retrieval-rules",
            title="Retrieval Rules",
            status="active",
            owner="unassigned",
        ),
        """## Purpose
Defines deterministic file loading for resume and wrap-up commands.

## Rules
Resume loads shared meta prerequisites, the target task, direct dependencies, matching plan entries, the department index, the latest valid handoff, linked canonical docs, and referenced ADRs.

## References
See [[DEPT-REGISTRY]] and [[DOC-schema-registry]].""",
    )
    created.append((repo.meta_root / "retrieval-rules.md").relative_to(repo.root).as_posix())

    starter_docs = {
        repo.meta_root / "index.md": (
            _starter_frontmatter("folder_index", doc_id="DOC-meta-index", title="Vault Meta Index", owner="unassigned", status="active"),
            """## Purpose
Defines the meta-level registry and policy documents for the vault.

## Scope
Covers schema versions, retrieval rules, and department mapping.

## Retrieval Notes
Loaded through specific meta documents, not directly by commands.

## Change Policy
Do not duplicate task or decision truth here.""",
        ),
        repo.vault_root / "01_execution" / "index.md": (
            _starter_frontmatter("folder_index", doc_id="DOC-execution-index", title="Execution Index", owner="unassigned", status="active"),
            """## Purpose
Tracks canonical tasks, plan entries, and execution coordination documents.

## Scope
Tasks and plan entries live below this folder.

## Retrieval Notes
Commands load individual tasks and matching plan entries directly.

## Change Policy
Keep execution status in task files, not summaries.""",
        ),
        repo.vault_root / "02_architecture" / "index.md": (
            _starter_frontmatter("folder_index", doc_id="DOC-architecture-index", title="Architecture Index", owner="unassigned", status="active"),
            """## Purpose
Tracks architecture documents for the project.

## Scope
Use this folder for architecture docs and decisions.

## Retrieval Notes
Reference specific architecture docs from tasks when needed.

## Change Policy
Prefer stable IDs over path references.""",
        ),
        repo.vault_root / "02_architecture" / "decisions" / "index.md": (
            _starter_frontmatter("folder_index", doc_id="DOC-decision-index", title="Decision Index", owner="unassigned", status="active"),
            """## Purpose
Lists architecture decision records.

## Scope
Add ADRs here as the project evolves.

## Retrieval Notes
ADRs are usually pulled indirectly from linked canonical docs.

## Change Policy
Keep one ADR per decision.""",
        ),
        repo.vault_root / "03_product" / "index.md": (
            _starter_frontmatter("folder_index", doc_id="DOC-product-index", title="Product Index", owner="unassigned", status="active"),
            """## Purpose
Tracks product-facing canonical documents.

## Scope
Use this folder for product scope, requirements, and policy docs.

## Retrieval Notes
Tasks should link specific product docs by ID.

## Change Policy
Keep roadmap notes out of canonical summaries unless approved.""",
        ),
        repo.vault_root / "04_engineering" / "index.md": (
            _starter_frontmatter(
                "department_index",
                doc_id="DOC-engineering-index",
                department_slug="engineering",
                title="Engineering Index",
                owner="unassigned",
                status="active",
                doc_refs=[],
                decision_refs=[],
                last_reviewed=str(datetime.now(timezone.utc).date()),
            ),
            """## Purpose
Tracks engineering-facing canonical documents.

## Scope
Use this folder for standards, runbooks, and implementation guidance.

## Documents in This Folder
Add engineering docs here as the project grows.

## Retrieval Notes
Tasks should link specific engineering docs by ID.

## Change Policy
Keep implementation status in task files, not here.""",
        ),
        repo.handoff_root / "index.md": (
            _starter_frontmatter("folder_index", doc_id="DOC-handoff-index", title="Handoff Index", owner="unassigned", status="active"),
            """## Purpose
Stores ephemeral handoff notes between sessions.

## Scope
Only session handoffs belong here.

## Retrieval Notes
Commands prefer the latest valid handoff for the current task.

## Change Policy
Handoffs never override canonical files.""",
        ),
    }
    for path, (frontmatter, body) in starter_docs.items():
        repo.save_markdown(path, frontmatter, body)
        created.append(path.relative_to(repo.root).as_posix())

    starter_task = repo.tasks_root / "TASK-001.md"
    repo.save_markdown(
        starter_task,
        _starter_frontmatter(
            "task",
            task_id="TASK-001",
            title="Bootstrap the project brain",
            status="proposed",
            priority="medium",
            owner="unassigned",
            department_slug="engineering",
            dependencies=[],
            linked_output_files=[],
            linked_canonical_docs=[],
            acceptance_criteria=["starter brain is initialized"],
            created_at=utc_now(),
            updated_at=utc_now(),
        ),
        """## Summary
Track follow-up work needed to tailor this starter brain to the real project.

## Implementation Notes
Replace placeholder owners, add project-specific docs, and create real tasks before active use.

## Dependency Notes
No dependencies yet.

## Validation Plan
Run `brain validate` after customizing the starter files.

## Change Log
- bootstrap task created during `brain init`.""",
    )
    created.append(starter_task.relative_to(repo.root).as_posix())

    generated = generate_derived(repo)
    created.extend((repo.root / path).relative_to(repo.root).as_posix() for path in generated)
    repo._cache.clear()
    return created


# Aggregate all validators so CLI commands can enforce one consistent definition of clean state.
def run_validation(repo: BrainRepository) -> ValidationResult:
    repo.require_initialized()
    errors = []
    errors.extend(check_schema(repo))
    errors.extend(check_links(repo))
    errors.extend(check_schema_activation(repo))
    errors.extend(check_dag(repo))
    errors.extend(check_consistency(repo))
    errors.extend(check_derived_freshness(repo))
    unique = {(err.path, err.message): err for err in errors}
    return ValidationResult(errors=sorted(unique.values(), key=lambda item: (item.path, item.message)), warnings=[])


def ensure_resume_prerequisites(repo: BrainRepository) -> None:
    repo.require_initialized()
    id_index_path = repo.derived_root / "id-path-index.md"
    derived_rel = id_index_path.relative_to(repo.root).as_posix()
    if not id_index_path.exists():
        raise ValueError(f"Missing derived prerequisite {derived_rel} for {repo.describe_target()}. Run `brain generate-derived`.")
    freshness_errors = [error for error in check_derived_freshness(repo) if error.path == derived_rel]
    if freshness_errors:
        details = "; ".join(error.message for error in freshness_errors)
        raise ValueError(f"Derived prerequisite {derived_rel} is stale or invalid for {repo.describe_target()}: {details}")


# Implement Phase 1 deterministic retrieval rules and return both documents and human-readable reasons.
def retrieve_resume_context(repo: BrainRepository, task_id: str) -> list[tuple[str, str]]:
    ensure_resume_prerequisites(repo)
    id_index = build_id_index(repo)
    task = repo.load_task(task_id)
    derived_rel = (repo.derived_root / "id-path-index.md").relative_to(repo.root).as_posix()
    retrieved: list[tuple[str, str]] = []
    retrieved.extend(
        [
            (repo.load_schema_registry().rel_path, "shared retrieval prerequisite: active schema versions"),
            (repo.load_department_registry().rel_path, "shared retrieval prerequisite: department registry"),
            (repo.load_retrieval_rules().rel_path, "shared retrieval prerequisite: deterministic retrieval contract"),
            (derived_rel, "shared retrieval prerequisite: ID-to-path resolution"),
            (task.rel_path, f"target task {task_id}"),
        ]
    )
    for dep in task.frontmatter.get("dependencies", []):
        retrieved.append((repo.load_task(dep).rel_path, f"direct dependency of {task_id}"))
    for plan in repo.load_plan_entries():
        if plan.frontmatter.get("task_id") == task_id:
            retrieved.append((plan.rel_path, f"plan entry for {task_id}"))
    dept_entry = repo.department_map()[task.frontmatter["department_slug"]]
    dept_rel_path = (repo.vault_root / dept_entry["index_path"]).relative_to(repo.root).as_posix()
    retrieved.append((repo.load_doc_by_relpath(dept_rel_path).rel_path, f"department index for {task.frontmatter['department_slug']}"))
    handoffs = [doc for doc in repo.load_handoffs() if doc.frontmatter.get("current_task") == task_id]
    if handoffs:
        handoffs.sort(key=lambda doc: (doc.frontmatter.get("created_at", ""), doc.frontmatter.get("handoff_id", "")), reverse=True)
        retrieved.append((handoffs[0].rel_path, f"latest handoff for {task_id}"))
    loaded_canonical_docs: list[Document] = []
    for doc_id in task.frontmatter.get("linked_canonical_docs", []):
        rel_path = id_index[doc_id]
        document = repo.load_doc_by_relpath(rel_path)
        loaded_canonical_docs.append(document)
        retrieved.append((document.rel_path, f"linked canonical document {doc_id}"))
    for document in loaded_canonical_docs:
        for adr_id in document.frontmatter.get("related_decisions", []):
            rel_path = id_index[adr_id]
            retrieved.append((repo.load_doc_by_relpath(rel_path).rel_path, f"decision referenced by {document.identity}"))
    seen = set()
    ordered: list[tuple[str, str]] = []
    for rel_path, reason in retrieved:
        if rel_path not in seen:
            seen.add(rel_path)
            ordered.append((rel_path, reason))
    return ordered


# Generate all derived reports from canonical sources so humans never hand-maintain them.
def generate_derived(repo: BrainRepository, timestamp: str | None = None) -> list[str]:
    repo.require_initialized()
    timestamp = timestamp or utc_now()
    id_index = build_id_index(repo)
    sources = sorted(set(id_index.values()) | {
        repo.load_department_registry().rel_path,
        repo.load_schema_registry().rel_path,
        repo.load_retrieval_rules().rel_path,
    })
    id_lines = ["# ID Path Index", "", "| ID | Path |", "|---|---|"]
    for doc_id, rel_path in sorted(id_index.items()):
        id_lines.append(f"| {doc_id} | {rel_path} |")
    repo.write_generated(repo.derived_root / "id-path-index.md", "brain generate-derived", sources, "\n".join(id_lines), timestamp)

    plan_lines = ["# Execution Plan Summary", "", "| Plan ID | Task ID | Sequence | Status |", "|---|---|---:|---|"]
    for plan in sorted(repo.load_plan_entries(), key=lambda doc: doc.frontmatter.get("sequence", 0)):
        fm = plan.frontmatter
        plan_lines.append(f"| {fm['plan_id']} | {fm['task_id']} | {fm['sequence']} | {fm['status']} |")
    repo.write_generated(repo.derived_root / "execution-plan-summary.md", "brain generate-derived", [doc.rel_path for doc in repo.load_plan_entries()], "\n".join(plan_lines), timestamp)

    task_lines = ["# Task Status Report", "", "| Task ID | Status | Department | Owner |", "|---|---|---|---|"]
    for task in repo.load_tasks():
        fm = task.frontmatter
        task_lines.append(f"| {fm['task_id']} | {fm['status']} | {fm['department_slug']} | {fm['owner']} |")
    repo.write_generated(repo.derived_root / "task-status-report.md", "brain generate-derived", [doc.rel_path for doc in repo.load_tasks()], "\n".join(task_lines), timestamp)

    errors = [error.render() for error in check_links(repo)]
    report = "# Broken References Report\n\n" + ("\n".join(f"- {line}" for line in errors) if errors else "No broken references found.")
    repo.write_generated(repo.derived_root / "broken-references-report.md", "brain generate-derived", sources, report, timestamp)
    return [path.relative_to(repo.root).as_posix() for path in sorted(repo.derived_root.glob("*.md"))]


# Report unblocked tasks and mark which ones can run together without output collisions.
def compute_next_tasks(repo: BrainRepository) -> list[dict[str, Any]]:
    repo.require_initialized()
    tasks = {task.frontmatter["task_id"]: task for task in repo.load_tasks()}
    ready: list[Document] = []
    for task in tasks.values():
        if task.frontmatter["status"] in {"complete", "cancelled", "review"}:
            continue
        deps = task.frontmatter.get("dependencies", [])
        if all(tasks[dep].frontmatter["status"] == "complete" for dep in deps):
            ready.append(task)
    outputs_by_task = {task.frontmatter["task_id"]: set(task.frontmatter.get("linked_output_files", [])) for task in ready}
    result = []
    for task in sorted(ready, key=lambda doc: doc.frontmatter["task_id"]):
        overlaps = [other_id for other_id, outputs in outputs_by_task.items() if other_id != task.frontmatter["task_id"] and outputs & outputs_by_task[task.frontmatter["task_id"]]]
        result.append(
            {
                "task_id": task.frontmatter["task_id"],
                "status": task.frontmatter["status"],
                "parallel_safe": not overlaps,
                "shared_outputs_with": sorted(overlaps),
            }
        )
    return result


# Provide an explicit per-task view that checks dependency status and output existence at the same time.
def get_task_status(repo: BrainRepository, task_id: str) -> dict[str, Any]:
    repo.require_initialized()
    task = repo.load_task(task_id)
    tasks = {doc.frontmatter["task_id"]: doc for doc in repo.load_tasks()}
    outputs = []
    for output in task.frontmatter.get("linked_output_files", []):
        path = repo.root / output
        outputs.append({"path": output, "exists": path.is_file()})
    deps = []
    for dep in task.frontmatter.get("dependencies", []):
        dep_doc = tasks[dep]
        deps.append({"task_id": dep, "status": dep_doc.frontmatter["status"]})
    return {"task": task.frontmatter, "dependencies": deps, "outputs": outputs, "target": repo.describe_target()}


# Parse the machine-readable migration block conservatively because Phase 1 left migration mechanics underspecified.
def parse_migration_operations(document: Document) -> list[dict[str, Any]]:
    body = extract_section(document.body, "Migration Steps")
    marker = "```yaml"
    if marker not in body:
        return []
    yaml_block = body.split(marker, 1)[1].split("```", 1)[0]
    data = yaml.safe_load(yaml_block) or {}
    return data.get("operations", [])


# Apply only supported migration operations and show diffs for dry-run mode.
def migrate(repo: BrainRepository, migration_id: str, dry_run: bool) -> list[str]:
    repo.require_initialized(for_mutation=not dry_run)
    result = run_validation(repo)
    if not dry_run and not result.ok:
        raise ValueError(f"Refusing to apply migration to an invalid target: {repo.describe_target()}. Run `brain validate` first.")
    migration = repo.load_migration(migration_id)
    operations = parse_migration_operations(migration)
    if not operations:
        raise ValueError(f"Migration does not contain a supported machine-readable operations block in {repo.describe_target()}.")
    outputs: list[str] = []
    for operation in operations:
        if operation.get("type") != "add_frontmatter_field":
            raise ValueError(f"Unsupported migration operation for {repo.describe_target()}: {operation.get('type')}")
        target = operation["target"]
        field = operation["field"]
        value = operation["value"]
        for task in repo.load_tasks() if target == "task" else []:
            if field in task.frontmatter:
                continue
            new_frontmatter = deepcopy(task.frontmatter)
            new_frontmatter[field] = value
            original = task.path.read_text(encoding="utf-8")
            updated = "---\n" + yaml.safe_dump(new_frontmatter, sort_keys=False).strip() + "\n---\n\n" + task.body.strip() + "\n"
            diff = "\n".join(
                difflib.unified_diff(
                    original.splitlines(),
                    updated.splitlines(),
                    fromfile=task.rel_path,
                    tofile=task.rel_path,
                    lineterm="",
                )
            )
            outputs.append(diff)
            if not dry_run:
                task.path.write_text(updated, encoding="utf-8")
    if not dry_run:
        repo._cache.clear()
        generate_derived(repo)
        repo._cache.clear()
        after = run_validation(repo)
        if not after.ok:
            raise ValueError(f"Migration applied but post-validation failed for {repo.describe_target()}. Inspect the reported errors and revert.")
    return outputs


# Create a handoff and update the task atomically enough for a single-user local workflow.
def wrap_up(
    repo: BrainRepository,
    task_id: str,
    status: str,
    summary: str,
    work_completed: str,
    next_actions: str,
    risks: str,
    refs: list[str],
    questions: list[str],
    author: str = "agent-gpt",
) -> str:
    repo.require_initialized(for_mutation=True)
    task = repo.load_task(task_id)
    original_task = task.path.read_text(encoding="utf-8")
    original_handoffs = {doc.path: doc.path.read_text(encoding="utf-8") for doc in repo.load_handoffs()}
    original_derived = {path: path.read_text(encoding="utf-8") for path in repo.derived_root.glob("*.md")}
    try:
        fm = deepcopy(task.frontmatter)
        fm["status"] = status
        fm["updated_at"] = utc_now()
        body = task.body.strip()
        body += f"\n- {datetime.now(timezone.utc).date()}: wrap-up updated status to `{status}`."
        repo.save_markdown(task.path, fm, body)
        repo._cache.pop(task.path, None)
        handoff_id = f"HANDOFF-{len(repo.load_handoffs()) + 1:04d}"
        handoff_frontmatter = {
            "schema_version": "1.0",
            "doc_type": "handoff_note",
            "handoff_id": handoff_id,
            "session_id": f"SESSION-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "created_at": utc_now(),
            "author": author,
            "current_task": task_id,
            "status_snapshot": summary,
            "canonical_refs": [task_id, *refs],
            "open_questions": questions,
        }
        handoff_body = (
            "## Session Summary\n"
            f"{summary}\n\n"
            "## Work Completed\n"
            f"{work_completed}\n\n"
            "## Next Recommended Actions\n"
            f"{next_actions}\n\n"
            "## Risks / Blockers\n"
            f"{risks}\n\n"
            "## Canonical References\n"
            + "\n".join(f"- {ref}" for ref in handoff_frontmatter["canonical_refs"])
        )
        new_handoff = repo.handoff_root / f"{handoff_id}.md"
        repo.save_markdown(new_handoff, handoff_frontmatter, handoff_body)
        repo._cache.clear()
        generate_derived(repo)
        repo._cache.clear()
        result = run_validation(repo)
        if not result.ok:
            raise ValueError(
                f"Validation failed after wrap-up for {repo.describe_target()}:\n" + "\n".join(error.render() for error in result.errors)
            )
        return new_handoff.relative_to(repo.root).as_posix()
    except Exception:
        task.path.write_text(original_task, encoding="utf-8")
        for path in repo.handoff_root.glob("HANDOFF-*.md"):
            if path not in original_handoffs:
                path.unlink()
        for path, content in original_handoffs.items():
            path.write_text(content, encoding="utf-8")
        for path in repo.derived_root.glob("*.md"):
            if path not in original_derived:
                path.unlink()
        for path, content in original_derived.items():
            path.write_text(content, encoding="utf-8")
        repo._cache.clear()
        raise
