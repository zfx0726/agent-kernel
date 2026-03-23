from __future__ import annotations

import argparse
import json

from project_brain.repository import BrainRepository
from project_brain.services import compute_next_tasks, generate_derived, get_task_status, init_brain, migrate, retrieve_resume_context, run_validation, wrap_up


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="brain")
    parser.add_argument("--root", help="Project root to operate on. Defaults to the current working directory.")
    parser.add_argument("--brain-dir", default=None, help="Brain data directory relative to --root. Defaults to .brain, with legacy repo-root fallback.")
    parser.add_argument("--allow-external-brain-dir", action="store_true", help="Allow --brain-dir to resolve outside --root.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init")
    subparsers.add_parser("validate")

    resume = subparsers.add_parser("resume")
    resume.add_argument("task_id")

    wrap = subparsers.add_parser("wrap-up")
    wrap.add_argument("task_id")
    wrap.add_argument("--status", required=True)
    wrap.add_argument("--summary", required=True)
    wrap.add_argument("--work-completed", required=True)
    wrap.add_argument("--next-actions", required=True)
    wrap.add_argument("--risks", required=True)
    wrap.add_argument("--ref", action="append", default=[])
    wrap.add_argument("--question", action="append", default=[])

    subparsers.add_parser("next-task")

    task_status = subparsers.add_parser("task-status")
    task_status.add_argument("task_id")

    migration = subparsers.add_parser("migrate")
    migration.add_argument("migration_id")
    migration.add_argument("--dry-run", action="store_true")

    subparsers.add_parser("generate-derived")
    return parser


def _make_repo(args: argparse.Namespace) -> BrainRepository:
    return BrainRepository(root=args.root, brain_dir=args.brain_dir, allow_external_brain_dir=args.allow_external_brain_dir)


def _print_target(prefix: str, repo: BrainRepository) -> None:
    print(f"{prefix}: {repo.describe_target()}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo = _make_repo(args)
    except Exception as exc:  # noqa: BLE001
        print(str(exc))
        return 1
    if args.command == "init":
        try:
            created = init_brain(repo)
        except Exception as exc:  # noqa: BLE001
            print(str(exc))
            return 1
        _print_target("Initialized brain target", repo)
        for path in created:
            print(f"- created {path}")
        return 0
    if args.command == "validate":
        try:
            result = run_validation(repo)
        except Exception as exc:  # noqa: BLE001
            print(str(exc))
            return 1
        if result.ok:
            print(f"Validation succeeded for {repo.describe_target()}.")
            return 0
        print(f"Validation failed for {repo.describe_target()}:")
        for error in result.errors:
            print(f"- {error.render()}")
        return 1
    if args.command == "resume":
        try:
            context = retrieve_resume_context(repo, args.task_id)
        except Exception as exc:  # noqa: BLE001
            print(f"Resume failed for {repo.describe_target()}: {exc}")
            return 1
        print(f"Session briefing for {args.task_id} ({repo.describe_target()})\n")
        for path, reason in context:
            print(f"- {path} :: {reason}")
        return 0
    if args.command == "wrap-up":
        _print_target("Mutating brain target", repo)
        try:
            handoff_path = wrap_up(
                repo,
                args.task_id,
                args.status,
                args.summary,
                args.work_completed,
                args.next_actions,
                args.risks,
                args.ref,
                args.question,
            )
        except Exception as exc:  # noqa: BLE001
            print(str(exc))
            return 1
        print(f"Created {handoff_path}")
        return 0
    if args.command == "next-task":
        try:
            items = compute_next_tasks(repo)
        except Exception as exc:  # noqa: BLE001
            print(str(exc))
            return 1
        print(f"Target: {repo.describe_target()}")
        for item in items:
            shared = ", ".join(item["shared_outputs_with"]) if item["shared_outputs_with"] else "none"
            print(f"{item['task_id']} status={item['status']} parallel_safe={item['parallel_safe']} shared_outputs_with={shared}")
        return 0
    if args.command == "task-status":
        try:
            status = get_task_status(repo, args.task_id)
        except Exception as exc:  # noqa: BLE001
            print(str(exc))
            return 1
        print(json.dumps(status, indent=2))
        return 0
    if args.command == "migrate":
        if not args.dry_run:
            _print_target("Mutating brain target", repo)
        try:
            outputs = migrate(repo, args.migration_id, args.dry_run)
        except Exception as exc:  # noqa: BLE001
            print(str(exc))
            return 1
        print("\n\n".join(outputs) if outputs else "No changes required.")
        return 0
    if args.command == "generate-derived":
        try:
            paths = generate_derived(repo)
        except Exception as exc:  # noqa: BLE001
            print(str(exc))
            return 1
        print(f"Generated derived files for {repo.describe_target()}")
        for path in paths:
            print(path)
        return 0
    return 1
