from __future__ import annotations

import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from shutil import copytree, move

from project_brain.repository import BrainRepository
from project_brain.services import compute_next_tasks, generate_derived, init_brain, migrate, retrieve_resume_context, run_validation, utc_now, wrap_up
from project_brain.validators.schema import check_schema

ROOT = Path(__file__).resolve().parents[1]
DERIVED_FILES = tuple((ROOT / "vault/99_derived").glob("*.md"))


@contextmanager
def preserved_paths(*paths: Path):
    backups: dict[Path, str | None] = {}
    for path in paths:
        backups[path] = path.read_text(encoding="utf-8") if path.exists() else None
    try:
        yield
    finally:
        for path in paths:
            original = backups[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(original, encoding="utf-8")


@contextmanager
def consumer_repo_fixture():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        brain_root = root / ".brain"
        copytree(ROOT / "vault", brain_root / "vault")
        copytree(ROOT / "schemas", brain_root / "schemas")
        copytree(ROOT / "migrations", brain_root / "migrations")
        copytree(ROOT / "artifacts", root / "artifacts")
        (root / "artifacts" / "missing-migration-report.md").write_text("placeholder\n", encoding="utf-8")
        repo = BrainRepository(root)
        generate_derived(repo, timestamp=utc_now())
        yield root


class BrainTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = BrainRepository(ROOT)

    def test_next_task_returns_parallel_safe_unblocked_tasks(self) -> None:
        tasks = compute_next_tasks(self.repo)
        task_ids = [item["task_id"] for item in tasks]
        self.assertEqual(task_ids, ["TASK-003", "TASK-004"])
        self.assertTrue(all(item["parallel_safe"] for item in tasks))

    def test_resume_retrieval_loads_expected_files(self) -> None:
        loaded = retrieve_resume_context(self.repo, "TASK-003")
        paths = [path for path, _ in loaded]
        self.assertEqual(
            paths,
            [
                "vault/00_meta/schema-registry.md",
                "vault/00_meta/departments.md",
                "vault/00_meta/retrieval-rules.md",
                "vault/99_derived/id-path-index.md",
                "vault/01_execution/tasks/TASK-003.md",
                "vault/01_execution/tasks/TASK-002.md",
                "vault/01_execution/plan-entries/PLAN-001.md",
                "vault/04_engineering/index.md",
                "vault/90_handoffs/HANDOFF-0001.md",
                "vault/04_engineering/DOC-coding-standards.md",
                "vault/02_architecture/ARCH-auth-strategy.md",
                "vault/02_architecture/decisions/ADR-002-id-first-references.md",
            ],
        )

    def test_schema_validation_reports_missing_required_field(self) -> None:
        bad_task = ROOT / "vault/01_execution/tasks/TASK-099.md"
        with preserved_paths(bad_task):
            bad_task.write_text(
                "---\n"
                'schema_version: "1.0"\n'
                'doc_type: "task"\n'
                'task_id: "TASK-099"\n'
                'title: "Broken task"\n'
                'status: "ready"\n'
                'priority: "low"\n'
                'department_slug: "engineering"\n'
                'dependencies: []\n'
                'linked_output_files: []\n'
                'linked_canonical_docs: []\n'
                'acceptance_criteria: []\n'
                'created_at: "2026-03-23T11:00:00Z"\n'
                'updated_at: "2026-03-23T11:00:00Z"\n'
                '---\n\n'
                '## Summary\nBroken\n\n'
                '## Implementation Notes\nBroken\n\n'
                '## Dependency Notes\nNone\n\n'
                '## Validation Plan\nNone\n\n'
                '## Change Log\n- created\n',
                encoding="utf-8",
            )
            errors = [error.render() for error in check_schema(self.repo)]
            self.assertTrue(any("TASK-099.md: missing required field owner" in error for error in errors))

    def test_migration_dry_run_reports_diff_without_writing(self) -> None:
        before = (ROOT / "vault/01_execution/tasks/TASK-003.md").read_text(encoding="utf-8")
        diffs = migrate(self.repo, "MIG-2026-001", dry_run=True)
        after = (ROOT / "vault/01_execution/tasks/TASK-003.md").read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertTrue(any("risk_level" in diff for diff in diffs))

    def test_generate_derived_matches_snapshot_shape(self) -> None:
        generate_derived(self.repo, timestamp="2026-03-23T20:00:00Z")
        text = (ROOT / "vault/99_derived/execution-plan-summary.md").read_text(encoding="utf-8")
        self.assertIn("generated_at: 2026-03-23T20:00:00Z", text)
        self.assertIn("| PLAN-001 | TASK-003 | 1 | active |", text)
        self.assertIn("| PLAN-002 | TASK-004 | 2 | queued |", text)

    def test_resume_uses_renamed_doc_after_regeneration(self) -> None:
        old_path = ROOT / "vault/02_architecture/ARCH-auth-strategy.md"
        new_path = ROOT / "vault/02_architecture/ARCH-auth-strategy-renamed.md"
        with preserved_paths(old_path, new_path, *DERIVED_FILES):
            move(old_path, new_path)
            generate_derived(self.repo, timestamp="2026-03-23T20:10:00Z")
            self.repo._cache.clear()
            loaded = retrieve_resume_context(self.repo, "TASK-003")
            paths = [path for path, _ in loaded]
            self.assertIn("vault/02_architecture/ARCH-auth-strategy-renamed.md", paths)
            self.assertNotIn("vault/02_architecture/ARCH-auth-strategy.md", paths)

    def test_resume_fails_when_id_index_is_stale_after_rename(self) -> None:
        old_path = ROOT / "vault/02_architecture/ARCH-auth-strategy.md"
        new_path = ROOT / "vault/02_architecture/ARCH-auth-strategy-renamed.md"
        with preserved_paths(old_path, new_path, *DERIVED_FILES):
            move(old_path, new_path)
            self.repo._cache.clear()
            with self.assertRaisesRegex(ValueError, "stale or invalid"):
                retrieve_resume_context(self.repo, "TASK-003")

    def test_schema_activation_mismatch_fails_cleanly(self) -> None:
        schema_registry = ROOT / "vault/00_meta/schema-registry.md"
        task = ROOT / "vault/01_execution/tasks/TASK-003.md"
        with preserved_paths(schema_registry, task):
            schema_registry.write_text(
                schema_registry.read_text(encoding="utf-8").replace('  task: "1.0"', '  task: "1.1"'),
                encoding="utf-8",
            )
            self.repo._cache.clear()
            errors = [error.render() for error in run_validation(self.repo).errors]
            self.assertTrue(any("TASK-003.md: schema_version 1.0 does not match active task schema 1.1" in error for error in errors))

    def test_wrap_up_restores_derived_files_on_failure(self) -> None:
        task = ROOT / "vault/01_execution/tasks/TASK-003.md"
        derived = ROOT / "vault/99_derived/task-status-report.md"
        before = derived.read_text(encoding="utf-8")
        with preserved_paths(task, *DERIVED_FILES):
            task.write_text(task.read_text(encoding="utf-8").replace('artifacts/schema-validator-plan.md', 'artifacts/missing-schema-validator-plan.md'), encoding="utf-8")
            self.repo._cache.clear()
            with self.assertRaisesRegex(ValueError, "Validation failed after wrap-up"):
                wrap_up(
                    self.repo,
                    "TASK-003",
                    "complete",
                    "Tried to complete the task.",
                    "Updated status.",
                    "Restore the missing artifact.",
                    "Output file is missing.",
                    ["DOC-coding-standards"],
                    [],
                )
            after = derived.read_text(encoding="utf-8")
            self.assertEqual(before, after)

    def test_repository_supports_dot_brain_layout(self) -> None:
        with consumer_repo_fixture() as consumer_root:
            repo = BrainRepository(consumer_root)
            loaded = retrieve_resume_context(repo, "TASK-003")
            paths = [path for path, _ in loaded]
            self.assertIn(".brain/vault/01_execution/tasks/TASK-003.md", paths)
            self.assertIn(".brain/vault/99_derived/id-path-index.md", paths)

    def test_generate_derived_and_outputs_stay_in_selected_root(self) -> None:
        with consumer_repo_fixture() as consumer_root:
            repo = BrainRepository(consumer_root)
            generated = generate_derived(repo, timestamp="2026-03-23T21:00:00Z")
            self.assertTrue(all(path.startswith(".brain/vault/99_derived/") for path in generated))
            status = run_validation(repo)
            self.assertFalse(any(str(ROOT) in error.render() for error in status.errors))
            task_status = repo.load_task("TASK-003")
            self.assertEqual(task_status.rel_path, ".brain/vault/01_execution/tasks/TASK-003.md")

    def test_migration_changes_only_target_project_files(self) -> None:
        source_text = (ROOT / "vault/01_execution/tasks/TASK-003.md").read_text(encoding="utf-8")
        with consumer_repo_fixture() as consumer_root:
            repo = BrainRepository(consumer_root)
            migrate(repo, "MIG-2026-001", dry_run=False)
            external_text = (consumer_root / ".brain/vault/01_execution/tasks/TASK-003.md").read_text(encoding="utf-8")
            self.assertIn("risk_level", external_text)
        self.assertEqual(source_text, (ROOT / "vault/01_execution/tasks/TASK-003.md").read_text(encoding="utf-8"))

    def test_init_brain_seeds_empty_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = BrainRepository(root)
            created = init_brain(repo)
            self.assertIn(".brain/vault/00_meta/departments.md", created)
            self.assertTrue((root / ".brain/vault/99_derived/id-path-index.md").exists())
            self.assertTrue((root / ".brain/schemas/task.schema.yaml").exists())
            self.assertEqual(run_validation(repo).errors, [])

    def test_init_refuses_existing_initialized_target(self) -> None:
        with consumer_repo_fixture() as consumer_root:
            repo = BrainRepository(consumer_root)
            with self.assertRaisesRegex(FileExistsError, "Refusing to initialize"):
                init_brain(repo)

    def test_repository_rejects_external_brain_dir_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            outside = Path(tmp) / "outside-brain"
            with self.assertRaisesRegex(ValueError, "Brain dir must stay inside"):
                BrainRepository(root, str(outside))
            repo = BrainRepository(root, str(outside), allow_external_brain_dir=True)
            self.assertEqual(repo.brain_root, outside.resolve())


class CLISmokeTests(unittest.TestCase):
    def test_resume_command_runs(self) -> None:
        result = subprocess.run([str(ROOT / "brain"), "resume", "TASK-003"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("Session briefing for TASK-003", result.stdout)
        self.assertIn("root=", result.stdout)

    def test_cli_can_target_external_root_with_brain_dir(self) -> None:
        with consumer_repo_fixture() as consumer_root:
            result = subprocess.run(
                [str(ROOT / "brain"), "--root", str(consumer_root), "resume", "TASK-003"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(".brain/vault/01_execution/tasks/TASK-003.md", result.stdout)
            self.assertIn(str(consumer_root), result.stdout)

    def test_cli_init_bootstraps_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run(
                [str(ROOT / "brain"), "--root", str(root), "init"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Initialized brain target", result.stdout)
            self.assertTrue((root / ".brain/vault/00_meta/departments.md").exists())

    def test_cli_reports_mutation_target_before_wrap_up_failure(self) -> None:
        with consumer_repo_fixture() as consumer_root:
            task = consumer_root / ".brain/vault/01_execution/tasks/TASK-003.md"
            task.write_text(task.read_text(encoding="utf-8").replace('artifacts/schema-validator-plan.md', 'artifacts/missing-schema-validator-plan.md'), encoding="utf-8")
            result = subprocess.run(
                [
                    str(ROOT / "brain"),
                    "--root",
                    str(consumer_root),
                    "wrap-up",
                    "TASK-003",
                    "--status",
                    "complete",
                    "--summary",
                    "summary",
                    "--work-completed",
                    "done",
                    "--next-actions",
                    "next",
                    "--risks",
                    "risk",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Mutating brain target:", result.stdout)
            self.assertIn(str(consumer_root), result.stdout)

    def test_cli_rejects_external_brain_dir_without_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            root.mkdir()
            outside = Path(tmp) / "outside-brain"
            result = subprocess.run(
                [str(ROOT / "brain"), "--root", str(root), "--brain-dir", str(outside), "init"],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Brain dir must stay inside", result.stdout)


if __name__ == "__main__":
    unittest.main()
