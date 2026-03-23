from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from project_brain.repository import BrainRepository, ValidationError

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ID_PATTERNS = {
    "task_id": re.compile(r"^TASK-\d{3}$"),
    "plan_id": re.compile(r"^PLAN-\d{3}$"),
    "decision_id": re.compile(r"^ADR-\d{3}$"),
    "migration_id": re.compile(r"^MIG-\d{4}-\d{3}$"),
    "handoff_id": re.compile(r"^HANDOFF-\d{4}$"),
    "registry_id": re.compile(r"^DEPT-REGISTRY$"),
    "doc_id": re.compile(r"^(DOC|ARCH)-[a-z0-9-]+$"),
}


def _check_type(value: Any, declared: str) -> bool:
    if declared == "string":
        return isinstance(value, str)
    if declared == "integer":
        return isinstance(value, int)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "list[string]":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    if declared == "list[object]":
        return isinstance(value, list) and all(isinstance(item, dict) for item in value)
    if declared == "date":
        return isinstance(value, str) and bool(ISO_DATE.match(value))
    if declared == "date-time":
        return isinstance(value, str) and bool(ISO_DATETIME.match(value))
    return True


# Enforce schema files as the normative contract for frontmatter and heading order.
def check_schema(repo: BrainRepository) -> list[ValidationError]:
    schemas = repo.load_schemas()
    errors: list[ValidationError] = []
    seen_ids: dict[str, Path] = {}
    for path in repo.iter_vault_markdown():
        document = repo.load(path)
        doc_type = document.frontmatter.get("doc_type")
        if not doc_type:
            errors.append(ValidationError(document.rel_path, "missing doc_type"))
            continue
        schema = schemas.get(str(doc_type))
        if not schema:
            errors.append(ValidationError(document.rel_path, f"unknown doc_type {doc_type}"))
            continue
        fields: dict[str, Any] = schema.get("fields", {})
        for field_name, rules in fields.items():
            if rules.get("required") and field_name not in document.frontmatter:
                errors.append(ValidationError(document.rel_path, f"missing required field {field_name}"))
                continue
            if field_name not in document.frontmatter:
                continue
            value = document.frontmatter[field_name]
            if not _check_type(value, str(rules.get("type", "string"))):
                errors.append(ValidationError(document.rel_path, f"field {field_name} has invalid type"))
            allowed = rules.get("enum")
            if allowed and value not in allowed:
                errors.append(ValidationError(document.rel_path, f"field {field_name} must be one of {allowed}"))
            pattern = ID_PATTERNS.get(field_name)
            if pattern and isinstance(value, str) and not pattern.match(value):
                errors.append(ValidationError(document.rel_path, f"field {field_name} has invalid format: {value}"))
        expected_headings = schema.get("required_headings", [])
        actual = document.headings
        required_titles = [heading.removeprefix("## ") for heading in expected_headings]
        if actual[: len(required_titles)] != required_titles:
            errors.append(ValidationError(document.rel_path, f"headings must start with {required_titles}"))
        doc_id = document.identity
        if doc_id:
            previous = seen_ids.get(doc_id)
            if previous:
                errors.append(ValidationError(document.rel_path, f"duplicate document identity {doc_id} also used by {previous.as_posix()}"))
            seen_ids[doc_id] = path
    return errors


# Enforce active schema versions from the schema registry so migrations cannot be partially activated.
def check_schema_activation(repo: BrainRepository) -> list[ValidationError]:
    errors: list[ValidationError] = []
    registry = repo.load_schema_registry().frontmatter.get("active_versions", {})
    if not isinstance(registry, dict):
        return [ValidationError(repo.load_schema_registry().rel_path, "active_versions must be a mapping when present")]
    for path in repo.iter_vault_markdown():
        document = repo.load(path)
        doc_type = document.frontmatter.get("doc_type")
        active = registry.get(doc_type)
        if active and document.frontmatter.get("schema_version") != active:
            errors.append(ValidationError(document.rel_path, f"schema_version {document.frontmatter.get('schema_version')} does not match active {doc_type} schema {active}"))
    return errors
