# LLM Maintainer Guide

## Files you must never auto-modify casually

Canonical files are source of truth:
- `vault/00_meta/*`
- `vault/01_execution/tasks/*.md`
- `vault/01_execution/plan-entries/*.md`
- canonical docs in `vault/02_architecture/`, `vault/03_product/`, and `vault/04_engineering/`
- migration specs in `migrations/specs/*.md`
- schema files in `schemas/*.schema.yaml`

Edit these only when the change is deliberate and justified.

## Files you may freely regenerate

- `vault/99_derived/*.md`

These files are generated outputs. If they drift, regenerate them. Do not treat them as source of truth.

## YAML subset

Only use the repository's supported YAML subset in frontmatter and schema files: simple mappings, lists, list-of-object values, booleans, integers, and quoted or bare strings. Do not introduce multiline scalars, anchors, aliases, or tabs, because the local parser rejects them.

## Validator-enforced invariants

- Every canonical document has frontmatter matching its schema.
- Canonical cross-references use stable IDs and must resolve.
- Task dependencies must refer to real tasks and must not contain cycles.
- Complete tasks must point only to existing output files.
- Derived files must contain generated headers and be newer than their sources.
- Handoff ordering must be monotonic by timestamp and handoff ID.

Do not knowingly merge changes that break any of these invariants.

## Deployment modes

This tool supports two layouts: a legacy repo-root layout for this implementation repo, and a consumer-project layout where brain data lives under `.brain/`. Prefer the `.brain/` layout when dogfooding against another project. Use `brain init` to bootstrap new targets instead of hand-creating folders.

Runtime behavior is intentionally strict: once a target is selected, commands read schemas/config only from that target, `linked_output_files` resolve relative to the selected project root, and mutating commands should surface the resolved root/brain dir before writing.

## Adding a new command

1. Add the command parser entry in `project_brain/cli.py`.
2. Implement the behavior in `project_brain/services.py` or a small helper module.
3. Reuse existing loaders and validators instead of re-parsing files ad hoc.
4. Add tests that exercise the command behavior.
5. Document the command in `docs/README.md`.
6. Run `./brain generate-derived`, `./brain validate`, and the test suite.

## Modifying a schema safely

1. Create a migration spec first.
2. Update the schema file under `schemas/`.
3. Implement any migration support needed in the CLI.
4. Backfill existing canonical documents.
5. Regenerate derived files.
6. Run validation and tests.

If a schema change would leave old files inconsistent, stop and add a migration instead of forcing the new field into only some files.

## Resolving handoff conflicts

If a handoff note conflicts with a task, ADR, architecture doc, or department index, the canonical file wins. Use the handoff only as a lead, then verify the cited canonical references and update canonical state if the handoff surfaced a real omission.

## Before marking anything complete

Check all of the following:
1. The task status is updated in the task file.
2. Every linked output file exists on disk.
3. The task's canonical references still resolve.
4. Derived files have been regenerated.
5. `./brain validate` is clean.
6. Any new schema field or rule change has an approved migration if required.
