from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_brain import miniyaml as yaml

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass
class Document:
    path: Path
    repo_root: Path
    vault_root: Path
    frontmatter: dict[str, Any]
    body: str

    @property
    def rel_path(self) -> str:
        return self.path.relative_to(self.repo_root).as_posix()

    @property
    def vault_rel_path(self) -> str:
        return self.path.relative_to(self.vault_root).as_posix()

    @property
    def headings(self) -> list[str]:
        return HEADING_RE.findall(self.body)

    @property
    def doc_type(self) -> str:
        return str(self.frontmatter.get("doc_type", ""))

    @property
    def identity(self) -> str | None:
        for key in ("plan_id", "task_id", "decision_id", "migration_id", "doc_id", "handoff_id", "registry_id"):
            value = self.frontmatter.get(key)
            if value:
                return str(value)
        return None


# Maintain a strict parser so all validators see identical markdown structure.
def load_markdown(path: Path, repo_root: Path, vault_root: Path) -> Document:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"{path} is missing YAML frontmatter")
    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = text[match.end() :].lstrip("\n")
    return Document(path=path, repo_root=repo_root, vault_root=vault_root, frontmatter=frontmatter, body=body)


# Enumerate vault markdown files deterministically so validation output is stable.
def iter_vault_markdown(vault_root: Path) -> list[Path]:
    return sorted(path for path in vault_root.rglob("*.md") if path.is_file() and "99_derived" not in path.parts)


# Load schema definitions from disk rather than hardcoding them in validators.
def load_schemas(schema_root: Path) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}
    for path in sorted(schema_root.glob("*.schema.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        doc_type = data.get("doc_type")
        if doc_type:
            schemas[str(doc_type)] = data
    return schemas


# Parse a markdown heading section so command-specific extractors can read structured content.
def extract_section(body: str, heading: str) -> str:
    lines = body.splitlines()
    capture = False
    collected: list[str] = []
    target = f"## {heading}"
    for line in lines:
        if line.strip() == target:
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture:
            collected.append(line)
    return "\n".join(collected).strip()


# Keep cross-reference parsing centralized so link validation and reporting stay aligned.
def extract_wikilinks(body: str) -> list[str]:
    return WIKILINK_RE.findall(body)
