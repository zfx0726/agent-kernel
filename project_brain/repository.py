from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from project_brain import miniyaml as yaml
from project_brain.constants import (
    DEFAULT_BRAIN_DIR,
    DEFAULT_CONFIG_FILENAMES,
    GENERATED_HEADER_PREFIX,
    LEGACY_BRAIN_ROOT_MARKERS,
)
from project_brain.loader import Document, iter_vault_markdown, load_markdown, load_schemas


@dataclass
class ValidationError:
    path: str
    message: str

    def render(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class ValidationResult:
    errors: list[ValidationError]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


class BrainRepository:
    def __init__(
        self,
        root: Path | str | None = None,
        brain_dir: str | None = None,
        *,
        allow_external_brain_dir: bool = False,
    ) -> None:
        self.root = Path(root or os.environ.get("BRAIN_ROOT") or Path.cwd()).resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"Selected project root does not exist: {self.root}")
        if not self.root.is_dir():
            raise NotADirectoryError(f"Selected project root is not a directory: {self.root}")
        self.brain_dir_name = brain_dir or os.environ.get("BRAIN_DIR") or DEFAULT_BRAIN_DIR
        self.allow_external_brain_dir = allow_external_brain_dir
        self.brain_root = self._resolve_brain_root()
        self.vault_root = self.brain_root / "vault"
        self.schema_root = self.brain_root / "schemas"
        self.meta_root = self.vault_root / "00_meta"
        self.tasks_root = self.vault_root / "01_execution" / "tasks"
        self.plan_root = self.vault_root / "01_execution" / "plan-entries"
        self.handoff_root = self.vault_root / "90_handoffs"
        self.derived_root = self.vault_root / "99_derived"
        self.migrations_root = self.brain_root / "migrations" / "specs"
        self._cache: dict[Path, Document] = {}

    def _brain_dir_candidate(self) -> Path:
        candidate = Path(self.brain_dir_name)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.root / candidate).resolve()
        if not self.allow_external_brain_dir:
            try:
                resolved.relative_to(self.root)
            except ValueError as exc:
                raise ValueError(
                    f"Brain dir must stay inside the selected project root unless --allow-external-brain-dir is set: "
                    f"root={self.root} brain_dir={resolved}"
                ) from exc
        return resolved

    def _resolve_brain_root(self) -> Path:
        explicit = self._brain_dir_candidate()
        if explicit.exists():
            return explicit
        if self.brain_dir_name == DEFAULT_BRAIN_DIR and all((self.root / marker).exists() for marker in LEGACY_BRAIN_ROOT_MARKERS):
            return self.root
        return explicit

    def describe_target(self) -> str:
        return f"root={self.root} brain_dir={self.brain_root}"

    def is_initialized(self) -> bool:
        return self.meta_root.exists() and self.schema_root.exists() and self.migrations_root.parent.exists()

    def require_initialized(self, *, for_mutation: bool = False) -> None:
        required_paths = [
            self.vault_root,
            self.schema_root,
            self.migrations_root.parent,
            self.meta_root / DEFAULT_CONFIG_FILENAMES["department_registry"],
            self.meta_root / DEFAULT_CONFIG_FILENAMES["schema_registry"],
            self.meta_root / DEFAULT_CONFIG_FILENAMES["retrieval_rules"],
        ]
        missing = [path for path in required_paths if not path.exists()]
        if missing:
            action = "mutating" if for_mutation else "running commands against"
            details = ", ".join(path.relative_to(self.root).as_posix() if path.is_relative_to(self.root) else str(path) for path in missing)
            raise FileNotFoundError(
                f"Target brain is not initialized for {action}: {self.describe_target()}; missing {details}. "
                "Run `brain init` first."
            )

    def load(self, path: Path) -> Document:
        if path not in self._cache:
            self._cache[path] = load_markdown(path, self.root, self.vault_root)
        return self._cache[path]

    def iter_vault_markdown(self) -> list[Path]:
        return iter_vault_markdown(self.vault_root)

    def load_schemas(self) -> dict[str, dict[str, Any]]:
        return load_schemas(self.schema_root)

    def load_task(self, task_id: str) -> Document:
        path = self.tasks_root / f"{task_id}.md"
        if not path.exists():
            raise FileNotFoundError(f"Task not found in {self.describe_target()}: {task_id}")
        return self.load(path)

    def load_plan_entries(self) -> list[Document]:
        return [self.load(path) for path in sorted(self.plan_root.glob("PLAN-*.md"))]

    def load_tasks(self) -> list[Document]:
        return [self.load(path) for path in sorted(self.tasks_root.glob("TASK-*.md"))]

    def load_handoffs(self) -> list[Document]:
        return [self.load(path) for path in sorted(self.handoff_root.glob("HANDOFF-*.md"))]

    def load_migration(self, migration_id: str) -> Document:
        matches = sorted(self.migrations_root.glob(f"{migration_id}*.md"))
        if not matches:
            raise FileNotFoundError(f"Migration not found in {self.describe_target()}: {migration_id}")
        return self.load(matches[0])

    def load_doc_by_relpath(self, rel_path: str) -> Document:
        return self.load(self.root / rel_path)

    def load_department_registry(self) -> Document:
        return self.load(self.meta_root / DEFAULT_CONFIG_FILENAMES["department_registry"])

    def load_schema_registry(self) -> Document:
        return self.load(self.meta_root / DEFAULT_CONFIG_FILENAMES["schema_registry"])

    def load_retrieval_rules(self) -> Document:
        return self.load(self.meta_root / DEFAULT_CONFIG_FILENAMES["retrieval_rules"])

    def department_map(self) -> dict[str, dict[str, Any]]:
        data = self.load_department_registry().frontmatter["departments"]
        return {entry["department_slug"]: entry for entry in data}

    def write_generated(self, path: Path, command: str, sources: list[str], body: str, timestamp: str) -> None:
        header = [
            GENERATED_HEADER_PREFIX,
            f"generated_at: {timestamp}",
            f"command: {command}",
            "sources:",
        ]
        header.extend(f"- {source}" for source in sources)
        header_text = "\n".join(header) + "\n-->\n\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(header_text + body.strip() + "\n", encoding="utf-8")

    def parse_generated_header(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if not text.startswith(GENERATED_HEADER_PREFIX):
            return {}
        header_text = text.split("-->\n", 1)[0]
        info: dict[str, Any] = {"sources": []}
        for raw_line in header_text.splitlines()[1:]:
            line = raw_line.strip()
            if line.startswith("generated_at:"):
                info["generated_at"] = line.split(":", 1)[1].strip()
            elif line.startswith("command:"):
                info["command"] = line.split(":", 1)[1].strip()
            elif line.startswith("-"):
                info["sources"].append(line[1:].strip())
        return info

    def save_markdown(self, path: Path, frontmatter: dict[str, Any], body: str) -> None:
        text = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False).strip() + "\n---\n\n" + body.strip() + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
