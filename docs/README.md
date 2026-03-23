# Persistent Project Brain

This system provides a local-first, file-based project memory for AI-assisted software development. It keeps durable state in a Git-tracked markdown vault, separates canonical state from generated reports and ephemeral handoffs, and exposes a small CLI that can resume work, validate invariants, and regenerate derived indexes without relying on any external service.

## Vault structure

- `vault/00_meta/`: canonical registry and policy files.
- `vault/01_execution/`: canonical tasks and canonical plan entries.
- `vault/02_architecture/`, `vault/03_product/`, `vault/04_engineering/`: canonical domain docs.
- `vault/90_handoffs/`: ephemeral session notes.
- `vault/99_derived/`: generated reports and indexes.

Canonical files are source of truth and must be edited deliberately. Derived files are safe to regenerate. Ephemeral files help sessions hand off work but never override canonical truth.

## Installation

```bash
pip install -r requirements.txt
pip install -e .
```

No external runtime packages are required; editable install enables use from another project while preserving local development.

## Supported YAML subset

This project deliberately supports a small YAML subset for frontmatter and schema files: mappings, lists, list-of-object structures, quoted or bare scalars, booleans, integers, and empty `[]` / `{}` values. It does **not** support multiline scalars (`|` or `>`), anchors, aliases, tabs, or formatting-preserving round-trips. The parser will reject unsupported constructs instead of trying to guess.

## Commands

The CLI can run against either a legacy repo-root layout (`vault/`, `schemas/`, `migrations/`) or a consumer project with brain state stored under `.brain/`. Use `--root /path/to/project` to target another project cleanly. `brain init` bootstraps a fresh target, and runtime commands use only the selected target's schemas/config rather than silently falling back to bundled copies.

```bash
brain init --root /path/to/real-project --brain-dir .brain
brain validate
brain resume TASK-003
brain --root /path/to/real-project resume TASK-003
brain --root /path/to/real-project wrap-up TASK-006 --status review --summary "..." --work-completed "..." --next-actions "..." --risks "..." --ref DOC-coding-standards
brain next-task
brain task-status TASK-003
brain migrate MIG-2026-001 --dry-run
brain generate-derived
```

### Command notes

- `init`: creates a new brain under the selected target root, seeds starter schemas/meta files, and generates initial derived files. It refuses to overwrite an already-initialized target.
- `validate`: runs schema, reference, DAG, consistency, and derived freshness checks.
- `resume`: prints the exact files loaded for a task and why each one was included.
- `wrap-up`: updates a task, writes a new handoff, regenerates derived files, and refuses to finalize if validation fails.
- `next-task`: prints currently unblocked tasks and whether they are parallel-safe.
- `task-status`: prints a task, its dependency statuses, and linked output file existence.
- `migrate`: applies a migration spec, or prints diffs only in `--dry-run` mode.
- `generate-derived`: rebuilds everything under `vault/99_derived/`.

## External project layout

A consumer project can keep its brain data under `.brain/` with this structure:

- `.brain/vault/`
- `.brain/schemas/`
- `.brain/migrations/`

That lets the code and the target project stay separate while references still resolve locally inside the consumer repo.

Safety rules:

- `--root` must point to an existing directory.
- `--brain-dir` must stay inside `--root` unless you pass `--allow-external-brain-dir`.
- Mutating commands (`wrap-up`, non-dry-run `migrate`) print the resolved target root and brain dir before making changes.
- Runtime schema/config resolution is project-local only; bundled schemas are copied during `brain init` but are not consulted afterward.

## Adding a new department

1. Add a new entry to `vault/00_meta/departments.md` with `department_slug`, `folder_path`, `index_doc_id`, `index_path`, `owner`, and `status`.
2. Create the new department folder and its `index.md`.
3. Add any department-owned canonical docs.
4. Run `./brain generate-derived` and `./brain validate`.

## Adding a new task field safely

1. Create a migration spec in `migrations/specs/` that explains the field and includes a machine-readable operations block.
2. Update `schemas/task.schema.yaml`.
3. Backfill all existing task files through `./brain migrate ...` or a deliberate manual change.
4. Regenerate derived files.
5. Run `./brain validate` until clean.

Do not start writing new required fields into tasks without a migration.

## Example vault note

The included example vault intentionally contains one validation error: `TASK-006` is marked `complete` while `artifacts/missing-migration-report.md` does not exist. This is deliberate so `./brain validate` has a real consistency failure to report. Commands such as `resume`, `next-task`, `task-status`, `migrate --dry-run`, and `generate-derived` still work against the example vault.

## Common failure modes

- **Broken canonical reference**: run `./brain generate-derived` and `./brain validate`, then update the missing ID or document.
- **Complete task missing output file**: either create the output file or move the task out of `complete`.
- **Derived freshness error**: regenerate `vault/99_derived/`.
- **Unknown department slug**: fix the task or update the department registry.
- **Migration refuses to run**: make the vault validate cleanly first, unless you are using `--dry-run`.

## Recovering from a bad vault state

1. Run `./brain validate` and read the full error list.
2. Fix canonical files first; do not patch derived files by hand.
3. Regenerate derived files with `./brain generate-derived`.
4. Re-run validation.
5. If the vault is still inconsistent, use Git to inspect the last clean commit and restore only the canonical files that drifted.
