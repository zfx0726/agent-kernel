# Persistent Project Brain — Phase 1 Architecture & Schema

## 1. Architecture proposal

This design treats the project brain as a local-first repository with one durable memory surface: a markdown vault stored in Git and governed by explicit schemas. The vault is intentionally conservative. Canonical state lives in human-edited markdown files with YAML frontmatter. Derived state is regenerated into a separate tree and is always disposable. Ephemeral state is isolated so sessions can communicate without accidentally becoming source of truth. The goal is deterministic resumability: a future agent or engineer should be able to predict exactly which files define current project state for any task and exactly which files may be edited safely.

The operating model is ID-first. Every durable canonical object has a stable document ID that is the source of identity regardless of file path: tasks use `TASK-###`, decisions use `ADR-###`, architecture docs use `ARCH-<slug>`, department standards/docs use `DOC-<slug>`, plan entries use `PLAN-###`, and migrations use `MIG-YYYY-###`. Paths are location metadata only. Canonical cross-references therefore use IDs, not paths. A generated ID-to-path index in `vault/99_derived/` resolves those IDs to current locations. This makes renames operationally safe: a canonical file may move, but references stay stable as long as the ID is unchanged and the derived index regenerates cleanly.

The repository separates content from policy. `vault/` stores project memory. `schemas/` contains normative file contracts. `templates/` contains starter documents. `validators/` enforces invariants such as required frontmatter, allowed status transitions, ID uniqueness, reference resolution, and rename safety. `migrations/` stores schema changes and any backfill requirements. `scripts/` exposes deterministic commands such as `/resume`, `/wrap-up`, and derived-index generation. `docs/` contains design references for humans only and is explicitly out of runtime scope.

Single source of truth is strict. Task status exists only in the task file. A decision exists only in its ADR. A department’s identity mapping exists only in the department registry. A plan entry is the canonical execution unit, while execution summaries are derived from plan entries. Handoffs can summarize, recommend, and flag blockers, but they are never authoritative: any material claim must cite canonical IDs, and validators treat free-text handoff summaries as non-semantic.

Retrieval rules are enumerable by command. `/resume TASK-031` loads the task, its direct dependencies, the owning department registry entry and department index, the relevant plan entry or entries, the latest valid handoff for that task, the ID-to-path index, and the canonical documents referenced by ID from the task plus any decision records those docs declare. `/wrap-up TASK-031` loads the same set and performs stricter invariant checks before writing any updates, including existence checks for linked outputs and validation that the latest handoff ordering is consistent by both timestamp and handoff ID. No fuzzy search, embeddings, or “load related context” heuristics are part of the base design.

Department folders are extensible but registry-driven. A department consists of a folder such as `04_engineering/`, a slug such as `engineering`, a human title such as `Engineering`, and an index path such as `04_engineering/index.md`. The mapping is declared canonically in `vault/00_meta/departments.md`; no command or validator may infer one field from another without consulting the registry. This keeps folder naming flexible while preventing accidental drift when a department is renamed, added, or deprecated.

## 2. Repository and vault file tree

Annotated legend:
- `[C]` Canonical
- `[D]` Derived
- `[E]` Ephemeral
- `[R]` Reference-only; never runtime truth
- `NEVER` notes indicate maintainer prohibitions

```text
repo/
├── docs/
│   └── phase1-persistent-project-brain.md        [R] Human reference design. NEVER load at runtime as authoritative state.
├── migrations/
│   ├── README.md                                 [C] Migration process and ordering rules.
│   └── specs/
│       └── MIG-YYYY-001-<slug>.md                [C] One migration spec per schema change. NEVER rewrite an applied migration in place.
├── schemas/
│   ├── README.md                                 [C] Schema authoring and versioning rules.
│   ├── architecture-doc.schema.yaml              [C]
│   ├── decision-record.schema.yaml               [C]
│   ├── department-index.schema.yaml              [C]
│   ├── department-registry.schema.yaml           [C]
│   ├── execution-plan-entry.schema.yaml          [C]
│   ├── handoff-note.schema.yaml                  [C]
│   ├── migration-spec.schema.yaml                [C]
│   └── task.schema.yaml                          [C]
├── scripts/
│   ├── README.md                                 [C] Command contracts only; implementation is not source of truth.
│   ├── resume.py                                 [C] Deterministic retrieval entrypoint.
│   ├── wrap_up.py                                [C] Controlled state update entrypoint.
│   ├── build_derived.py                          [C] Regenerates all derived state.
│   └── validate.py                               [C] Runs full vault validation.
├── templates/
│   ├── architecture-doc.template.md              [C] Starter template. NEVER store live state here.
│   ├── decision-record.template.md               [C]
│   ├── department-index.template.md              [C]
│   ├── department-registry.template.md           [C]
│   ├── execution-plan-entry.template.md          [C]
│   ├── handoff-note.template.md                  [C]
│   ├── migration-spec.template.md                [C]
│   └── task.template.md                          [C]
├── tests/
│   ├── fixtures/
│   │   └── sample-vault/                         [C] Test fixture vault only. NEVER run production commands against it.
│   ├── test_reference_resolution.py              [C]
│   ├── test_retrieval_rules.py                   [C]
│   ├── test_schema_validation.py                 [C]
│   └── test_status_invariants.py                 [C]
├── validators/
│   ├── README.md                                 [C] Validator responsibilities.
│   ├── frontmatter_validator.py                  [C]
│   ├── id_registry_validator.py                  [C]
│   ├── reference_validator.py                    [C]
│   ├── rename_policy_validator.py                [C]
│   ├── schema_registry.py                        [C]
│   └── status_validator.py                       [C]
└── vault/
    ├── 00_meta/
    │   ├── index.md                              [C] Meta folder index. NEVER duplicate task or ADR content here.
    │   ├── changelog.md                          [C] Human-readable vault change log.
    │   ├── departments.md                        [C] Canonical department registry.
    │   ├── retrieval-rules.md                    [C] Normative command loading rules.
    │   ├── schema-registry.md                    [C] Active schema versions and comparison semantics.
    │   └── rename-policy.md                      [C] Canonical rename and inbound-reference policy.
    ├── 01_execution/
    │   ├── index.md                              [C] Execution folder index.
    │   ├── tasks/
    │   │   ├── TASK-001.md                       [C] Canonical task file.
    │   │   └── TASK-002.md                       [C]
    │   └── plan-entries/
    │       ├── PLAN-001.md                       [C] Canonical execution unit.
    │       └── PLAN-002.md                       [C]
    ├── 02_architecture/
    │   ├── index.md                              [C]
    │   ├── ARCH-auth-strategy.md                 [C] Canonical architecture doc.
    │   └── decisions/
    │       ├── index.md                          [C]
    │       └── ADR-007-filesystem-brain.md       [C] Canonical decision record.
    ├── 03_product/
    │   ├── index.md                              [C]
    │   └── DOC-product-scope.md                  [C] Canonical product doc.
    ├── 04_engineering/
    │   ├── index.md                              [C]
    │   └── DOC-coding-standards.md               [C] Canonical engineering doc.
    ├── 90_handoffs/
    │   ├── index.md                              [E] Ephemeral handoff index. NEVER use as canonical truth.
    │   └── HANDOFF-0041.md                       [E] Session-scoped note.
    └── 99_derived/
        ├── index.md                              [D] Generated artifact catalog.
        ├── execution-plan-summary.md             [D] Generated from PLAN files; NEVER hand-edit.
        ├── id-path-index.md                      [D] Generated ID-to-path resolution table.
        ├── broken-references-report.md           [D] Generated unresolved-reference report.
        └── task-status-report.md                 [D] Generated status summary.
```

### Folder contracts

| Folder | Contains | Naming convention | State class | Maintainer must never do |
|---|---|---|---|---|
| `docs/` | Reference documentation for humans | kebab-case or phase-specific docs | Reference-only | Never consult these files at runtime as authoritative system state |
| `vault/00_meta/` | Registry, policy, schema versions, changelog | fixed names for registry docs | Canonical | Never mirror task status, plan order, or ADR conclusions here |
| `vault/01_execution/tasks/` | Task source of truth | `TASK-###.md`; ID must match frontmatter | Canonical | Never infer status from filename or duplicate task status elsewhere |
| `vault/01_execution/plan-entries/` | Canonical plan units | `PLAN-###.md`; ID must match frontmatter | Canonical | Never maintain a second canonical execution ordering file |
| `vault/02_architecture/` and department folders | Canonical docs and indexes | `index.md`, `ARCH-<slug>.md`, `DOC-<slug>.md`, `ADR-###-<slug>.md` | Canonical | Never store generated summaries or session notes here |
| `vault/90_handoffs/` | Session handoffs and scratch transition notes | `HANDOFF-####.md` | Ephemeral | Never resolve factual conflicts in favor of handoffs |
| `vault/99_derived/` | Regenerated indexes and reports | `*-summary.md`, `*-report.md`, `*-index.md` | Derived | Never hand-edit and expect edits to survive regeneration |
| `schemas/` | Normative schema definitions | `<type>.schema.yaml` | Canonical | Never activate a breaking field change without a migration spec |
| `templates/` | Starter markdown files | `<type>.template.md` | Canonical | Never store live project data here |
| `migrations/specs/` | Schema and data migration records | `MIG-YYYY-###-<slug>.md` | Canonical | Never rewrite old migrations in place; supersede with a new one |

### Department extensibility rule

To add, rename, or remove a department, update only:
1. `vault/00_meta/departments.md`
2. The department folder and its `index.md`
3. Any task files or canonical docs that reference the affected `department_slug`
4. Regenerated derived indexes in `vault/99_derived/`

No validator or retrieval command may hardcode department names or infer folder paths directly from slugs. The registry is authoritative.

### Folder index rule

Every first-level vault folder and every nested canonical collection folder has an `index.md` containing:
- purpose of the folder
- inclusion and exclusion rules
- naming conventions
- retrieval notes if the folder participates in a command
- either:
  - a **hand-maintained scope summary** of what belongs in the folder, or
  - a pointer to the generated inventory in `vault/99_derived/id-path-index.md`

Indexes must **not** duplicate task status tables, rewrite ADR decisions, or summarize handoffs as truth. To reduce maintenance burden, child-by-child inventories are optional in canonical indexes and should be generated whenever a folder becomes large.

## 3. Schema definitions and templates for all file types

Normative rules for all markdown file types:
- YAML frontmatter must appear first.
- `schema_version` is required and uses `major.minor` string form such as `1.0`.
- Version comparison is semantic by numeric tuple, not lexicographic string ordering; for example `1.10` is greater than `1.2`.
- Unknown required fields are invalid unless introduced by an approved migration spec and activated in `vault/00_meta/schema-registry.md`.
- Required body headings must appear in the specified order.
- Every canonical document with a durable identity must declare a unique `doc_id`-style field and appear in the derived ID-to-path index.
- Cross-document references in canonical files use IDs only unless a field is explicitly defined as path-bearing.

Reference token classes used below:
- **Canonical document ID**: `TASK-###`, `PLAN-###`, `ADR-###`, `ARCH-<slug>`, `DOC-<slug>`, `MIG-YYYY-###`
- **Repo-relative path**: path rooted at repository root, used only for output artifacts and non-canonical implementation files
- **Vault-relative path**: path rooted at `vault/`, used only in derived indexes and registry location metadata, not as canonical identity

---

### 3.1 Task file

#### YAML frontmatter schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | Example `1.0` |
| `doc_type` | string | yes | Must be `task` |
| `task_id` | string | yes | Format `TASK-###`; zero-padded numeric IDs are stable and sortable |
| `title` | string | yes | Short outcome-oriented title |
| `status` | enum | yes | One of `proposed`, `ready`, `in_progress`, `blocked`, `review`, `complete`, `cancelled` |
| `priority` | enum | yes | One of `low`, `medium`, `high`, `critical` |
| `owner` | string | yes | Must be one of: registered team slug, registered human handle, or literal `unassigned` |
| `department_slug` | string | yes | Must match a department in `vault/00_meta/departments.md` |
| `dependencies` | list[string] | yes | Task IDs only; direct dependencies only |
| `linked_output_files` | list[string] | yes | Repo-relative file paths only; directories are not allowed in v1.0 |
| `linked_canonical_docs` | list[string] | yes | Canonical document IDs only; no paths |
| `acceptance_criteria` | list[string] | yes | Concrete completion checks |
| `created_at` | date-time | yes | ISO 8601 UTC |
| `updated_at` | date-time | yes | ISO 8601 UTC |
| `target_date` | date | no | Optional planning target |
| `supersedes` | string | no | Prior task ID if replacing another task |

#### Required body headings
1. `## Summary`
2. `## Implementation Notes`
3. `## Dependency Notes`
4. `## Validation Plan`
5. `## Change Log`

#### Filled example

```markdown
---
schema_version: "1.0"
doc_type: task
task_id: TASK-031
title: Add deterministic wrap-up validation for output artifacts
status: in_progress
priority: high
owner: team-platform
department_slug: engineering
dependencies:
  - TASK-028
  - TASK-030
linked_output_files:
  - validators/status_validator.py
  - tests/test_status_invariants.py
linked_canonical_docs:
  - DOC-coding-standards
  - ARCH-auth-strategy
acceptance_criteria:
  - wrap-up refuses to mark a task complete when any linked output file is missing
  - validator error messages identify the missing repo-relative file path
  - regression tests cover valid and invalid completion transitions
created_at: "2026-03-23T09:00:00Z"
updated_at: "2026-03-23T14:30:00Z"
target_date: "2026-03-25"
---

## Summary
Implement completion-time checks so task status cannot transition to `complete` unless all listed output files exist.

## Implementation Notes
Status transitions are validated in one shared validator so `/wrap-up` and standalone validation cannot drift.

## Dependency Notes
Depends on TASK-028 for the shared path resolver and TASK-030 for the command error format.

## Validation Plan
Run schema validation, status invariant tests, and a fixture-based wrap-up test for a missing artifact.

## Change Log
- 2026-03-23: Task created.
- 2026-03-23: Status changed from `ready` to `in_progress`.
```

#### Interaction model

The task file is the operational center of the system. It owns task identity, current status, acceptance criteria, direct task dependencies, and links to relevant canonical context via stable document IDs. It also declares the expected implementation outputs as repo-relative file paths, which `/wrap-up` must verify before allowing `complete`. Plan entries may schedule the task and handoffs may summarize it, but neither may redefine its status or acceptance criteria.

---

### 3.2 Decision record

#### YAML frontmatter schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | Example `1.0` |
| `doc_type` | string | yes | Must be `decision_record` |
| `decision_id` | string | yes | Format `ADR-###` |
| `title` | string | yes | Decision title |
| `status` | enum | yes | `proposed`, `accepted`, `superseded`, `rejected` |
| `date` | date | yes | Decision date |
| `owners` | list[string] | yes | Registered team slugs or human handles |
| `supersedes` | list[string] | no | Older ADR IDs |
| `superseded_by` | string | no | Newer ADR ID |
| `related_tasks` | list[string] | yes | Task IDs only |
| `related_docs` | list[string] | yes | Canonical document IDs only |

#### Required body headings
1. `## Context`
2. `## Decision`
3. `## Consequences`
4. `## Alternatives Considered`
5. `## References`

#### Filled example

```markdown
---
schema_version: "1.0"
doc_type: decision_record
decision_id: ADR-007
title: Use filesystem-backed markdown as the project brain
status: accepted
date: "2026-03-23"
owners:
  - team-staff-eng
related_tasks:
  - TASK-001
  - TASK-004
related_docs:
  - ARCH-auth-strategy
---

## Context
The system must persist state locally without requiring external infrastructure or opaque storage.

## Decision
Store durable project memory in markdown files with YAML frontmatter inside a Git-versioned vault.

## Consequences
The system is easy to inspect and diff, but validators must be strict to prevent drift.

## Alternatives Considered
SQLite with a markdown export layer; JSON documents; external hosted knowledge store.

## References
See the architecture overview and schema registry for compatibility rules.
```

#### Interaction model

A decision record is the sole canonical record for a project-level decision. Tasks, architecture docs, and department indexes may reference the ADR by ID, but none may restate the decision as source of truth. Supersession is recorded through ADR metadata only, which lets validators compute authoritative decision state without interpreting handoff text.

---

### 3.3 Handoff note

#### YAML frontmatter schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | Example `1.0` |
| `doc_type` | string | yes | Must be `handoff_note` |
| `handoff_id` | string | yes | Format `HANDOFF-####`; must increase monotonically |
| `session_id` | string | yes | External or local session identifier |
| `created_at` | date-time | yes | ISO 8601 UTC; retrieval orders by timestamp first, ID second |
| `author` | string | yes | Registered team slug, human handle, or agent handle |
| `current_task` | string | yes | Task ID |
| `status_snapshot` | string | yes | Free-text operational summary; explicitly non-semantic |
| `canonical_refs` | list[string] | yes | Canonical IDs only; no paths |
| `open_questions` | list[string] | yes | Questions for the next session |

#### Required body headings
1. `## Session Summary`
2. `## Work Completed`
3. `## Next Recommended Actions`
4. `## Risks / Blockers`
5. `## Canonical References`

#### Filled example

```markdown
---
schema_version: "1.0"
doc_type: handoff_note
handoff_id: HANDOFF-0041
session_id: SESSION-22
created_at: "2026-03-23T18:10:00Z"
author: agent-gpt
current_task: TASK-031
status_snapshot: "TASK-031 remains in_progress pending missing-output validation tests."
canonical_refs:
  - TASK-031
  - ADR-007
  - ARCH-auth-strategy
open_questions:
  - Should wrap-up validate symlinked files as ordinary output files in v1.0?
---

## Session Summary
Implemented initial validator logic but did not finalize test coverage.

## Work Completed
Updated the task notes and identified one missing edge case in completion validation.

## Next Recommended Actions
Finish regression tests, run the validator suite, and only then transition the task to `review`.

## Risks / Blockers
A prior summary phrased ADR-007 loosely; use the ADR itself for any normative wording.

## Canonical References
- TASK-031
- ADR-007
- ARCH-auth-strategy
```

#### Interaction model

The handoff note is an ephemeral bridge between sessions. It is retrieved because it is operationally useful, but validators must ignore `status_snapshot` semantically and treat `canonical_refs` as the only trustworthy anchors. Retrieval must sort handoffs by `created_at` descending and use `handoff_id` as a tie-breaker; validation must fail if ID order and timestamp order disagree materially.

---

### 3.4 Department index

#### YAML frontmatter schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | Example `1.0` |
| `doc_type` | string | yes | Must be `department_index` |
| `doc_id` | string | yes | Format `DOC-<slug>` for the index document itself |
| `department_slug` | string | yes | Must match the department registry |
| `title` | string | yes | Human-readable department name |
| `owner` | string | yes | Registered team slug or human handle |
| `status` | enum | yes | `active`, `deprecated` |
| `doc_refs` | list[string] | yes | Canonical document IDs in department scope |
| `decision_refs` | list[string] | no | ADR IDs relevant to the department |
| `last_reviewed` | date | yes | Governance freshness |

#### Required body headings
1. `## Purpose`
2. `## Scope`
3. `## Documents in This Folder`
4. `## Retrieval Notes`
5. `## Change Policy`

#### Filled example

```markdown
---
schema_version: "1.0"
doc_type: department_index
doc_id: DOC-engineering-index
department_slug: engineering
title: Engineering
owner: team-platform
status: active
doc_refs:
  - DOC-coding-standards
decision_refs:
  - ADR-007
last_reviewed: "2026-03-23"
---

## Purpose
Defines engineering standards, implementation conventions, and shared technical notes.

## Scope
Applies to code quality, release process, and operational engineering practices.

## Documents in This Folder
See `vault/99_derived/id-path-index.md` for the generated full inventory of engineering documents.

## Retrieval Notes
Load this index whenever a task declares `department_slug: engineering`.

## Change Policy
Update `doc_refs` and the department registry when documents are added, removed, renamed, or deprecated.
```

#### Interaction model

A department index defines the conceptual scope of a department while the department registry defines the slug-to-folder mapping. The index is canonical for scope and retrieval guidance, but not for filesystem location. That split lets a department move folders without changing its identity or forcing task references to churn.

---

### 3.5 Architecture doc

#### YAML frontmatter schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | Example `1.0` |
| `doc_type` | string | yes | Must be `architecture_doc` |
| `doc_id` | string | yes | Format `ARCH-<slug>` |
| `title` | string | yes | Document title |
| `status` | enum | yes | `draft`, `active`, `deprecated` |
| `owners` | list[string] | yes | Registered team slugs or human handles |
| `department_slug` | string | yes | Owning department slug |
| `related_decisions` | list[string] | yes | ADR IDs only |
| `related_tasks` | list[string] | yes | Task IDs only |
| `reviewed_at` | date | yes | Last review date |

#### Required body headings
1. `## Overview`
2. `## Constraints`
3. `## Proposed Structure`
4. `## Operational Implications`
5. `## References`

#### Filled example

```markdown
---
schema_version: "1.0"
doc_type: architecture_doc
doc_id: ARCH-auth-strategy
title: Authentication Strategy
status: active
owners:
  - team-platform
department_slug: engineering
related_decisions:
  - ADR-007
related_tasks:
  - TASK-031
reviewed_at: "2026-03-23"
---

## Overview
Describes the authentication boundaries, trust model, and repository integration points.

## Constraints
Must remain local-first, auditable, and compatible with deterministic retrieval.

## Proposed Structure
Keep canonical policy choices in ADRs and implementation-level structure here.

## Operational Implications
Tasks touching authentication must link this doc and any relevant ADRs.

## References
ADR-007 and DOC-coding-standards.
```

#### Interaction model

Architecture docs hold durable technical context that is broader than a single task and narrower than a project-wide ADR. They are referenced by task and decision IDs rather than by path, which allows document renames without task churn. Retrieval includes them only when directly linked from the task being resumed.

---

### 3.6 Execution plan entry

#### YAML frontmatter schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | Example `1.0` |
| `doc_type` | string | yes | Must be `execution_plan_entry` |
| `plan_id` | string | yes | Format `PLAN-###` |
| `task_id` | string | yes | Linked task ID |
| `sequence` | integer | yes | Positive integer ordering in active plan |
| `status` | enum | yes | `queued`, `active`, `done`, `dropped` |
| `depends_on_plan_ids` | list[string] | no | Optional plan-entry dependencies |
| `updated_at` | date-time | yes | ISO 8601 UTC |

#### Required body headings
1. `## Objective`
2. `## Preconditions`
3. `## Exit Criteria`
4. `## Notes`

#### Filled example

```markdown
---
schema_version: "1.0"
doc_type: execution_plan_entry
plan_id: PLAN-014
task_id: TASK-031
sequence: 14
status: active
depends_on_plan_ids:
  - PLAN-013
updated_at: "2026-03-23T17:00:00Z"
---

## Objective
Complete output-file validation for wrap-up.

## Preconditions
TASK-030 command formatting rules are merged locally.

## Exit Criteria
TASK-031 is in `review` with tests passing.

## Notes
This entry owns sequencing only; it does not own task status.
```

#### Interaction model

Plan entries are the only canonical execution-planning records. `vault/99_derived/execution-plan-summary.md` is generated from them and is never hand-maintained. This removes the duplicated-state hazard between a summary file and per-entry plan documents while preserving a readable overview for humans and agents.

---

### 3.7 Migration spec

#### YAML frontmatter schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | Example `1.0` |
| `doc_type` | string | yes | Must be `migration_spec` |
| `migration_id` | string | yes | Format `MIG-YYYY-###` |
| `title` | string | yes | Short change description |
| `status` | enum | yes | `proposed`, `approved`, `applied`, `superseded` |
| `target_file_types` | list[string] | yes | Affected schema names |
| `introduced_in_version` | string | yes | New schema version |
| `requires_backfill` | boolean | yes | Whether existing files must be updated |
| `approved_by` | list[string] | yes | Registered team slugs or human handles |
| `approved_at` | date-time | no | Required when status is `approved` or `applied` |

#### Required body headings
1. `## Change Summary`
2. `## Rationale`
3. `## Compatibility Impact`
4. `## Migration Steps`
5. `## Validation Requirements`
6. `## Rollback / Supersession`

#### Filled example

```markdown
---
schema_version: "1.0"
doc_type: migration_spec
migration_id: MIG-2026-002
title: Add `risk_level` to task schema
status: proposed
target_file_types:
  - task
introduced_in_version: "1.1"
requires_backfill: true
approved_by:
  - team-platform
---

## Change Summary
Introduce a new required `risk_level` enum field for task files.

## Rationale
Task priority alone is insufficient for operational review.

## Compatibility Impact
All existing task files require backfill before schema version `1.1` can be activated.

## Migration Steps
1. Approve the migration.
2. Update `schemas/task.schema.yaml` and `vault/00_meta/schema-registry.md`.
3. Backfill all existing task files.
4. Regenerate `vault/99_derived/id-path-index.md` and validation reports.
5. Enable validators to require the field.

## Validation Requirements
Validation must fail mixed `1.0` and `1.1` task usage once the registry marks `1.1` active.

## Rollback / Supersession
Supersede with a new migration if the field shape changes.
```

#### Interaction model

Migration specs are the only approved path for changing file contracts. Validators consult the active schema registry to determine what is currently allowed, and operators consult migration specs to know how to move the repository forward safely. This blocks ad hoc schema drift by requiring a documented transition before any new required field becomes enforceable.

---

### 3.8 Department registry

#### YAML frontmatter schema

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | yes | Example `1.0` |
| `doc_type` | string | yes | Must be `department_registry` |
| `registry_id` | string | yes | Must be `DEPT-REGISTRY` |
| `last_reviewed` | date | yes | Last review date |
| `departments` | list[object] | yes | Each entry follows the contract below |

Each `departments` item must contain:
- `department_slug` (string, required)
- `title` (string, required)
- `folder_path` (string, required, vault-relative, e.g. `04_engineering`)
- `index_doc_id` (string, required, canonical ID of the department index)
- `index_path` (string, required, vault-relative path to the index)
- `owner` (string, required, registered team slug or human handle)
- `status` (enum `active` or `deprecated`, required)

#### Required body headings
1. `## Registry Purpose`
2. `## Department Entries`
3. `## Change Rules`
4. `## Validation Notes`

#### Filled example

```markdown
---
schema_version: "1.0"
doc_type: department_registry
registry_id: DEPT-REGISTRY
last_reviewed: "2026-03-23"
departments:
  - department_slug: product
    title: Product
    folder_path: 03_product
    index_doc_id: DOC-product-index
    index_path: 03_product/index.md
    owner: team-product
    status: active
  - department_slug: engineering
    title: Engineering
    folder_path: 04_engineering
    index_doc_id: DOC-engineering-index
    index_path: 04_engineering/index.md
    owner: team-platform
    status: active
---

## Registry Purpose
Defines the authoritative mapping between department slug, display title, folder location, and owning index document.

## Department Entries
See the frontmatter list for the authoritative registry contents.

## Change Rules
Any add, rename, deprecation, or removal must update this file and regenerate the derived ID-to-path index in the same change.

## Validation Notes
Validators must reject duplicate slugs, duplicate folder paths, missing index documents, and tasks that reference unknown departments.
```

#### Interaction model

The department registry is the only canonical mapping between department slug, folder path, and index document. Tasks reference only `department_slug`. Commands resolve the folder and index through the registry, which prevents Phase 2 from hardcoding `03_product` or `04_engineering` assumptions.

## Deterministic retrieval rules

### Shared retrieval prerequisites
Every retrieval operation must load these first:
1. `vault/00_meta/schema-registry.md`
2. `vault/00_meta/departments.md`
3. `vault/00_meta/retrieval-rules.md`
4. `vault/99_derived/id-path-index.md`

If the ID-to-path index is missing or stale relative to canonical file modification times, validation must fail before command execution continues.

### `/resume <task_id>` must load exactly
1. Shared retrieval prerequisites.
2. `vault/01_execution/tasks/<task_id>.md`.
3. All direct dependency task files named in that task’s `dependencies`.
4. All `PLAN-###` files whose `task_id` matches `<task_id>`.
5. The department registry entry for the task’s `department_slug` and the corresponding department index document via `index_doc_id`.
6. The most recent valid handoff for `<task_id>`, ordered by `created_at` descending and `handoff_id` descending, provided validation confirms the ordering is monotonic.
7. Every canonical document resolved from IDs listed in `linked_canonical_docs`.
8. Any ADRs listed in the `related_decisions` frontmatter of documents loaded in step 7.

Nothing else is loaded automatically.

### `/wrap-up <task_id>` must load exactly
1. Everything `/resume <task_id>` loads.
2. Every repo-relative file listed in `linked_output_files`, checked for on-disk existence as files, not directories.
3. Any migration spec affecting the task schema version when validators detect version mismatch or pending backfill.

`/wrap-up` may update only:
- the target task file
- a newly created handoff note
- derived files regenerated by the normal build step

`/wrap-up` may not edit ADRs, architecture docs, department indexes, or registry files.

## Rename and reference policy

Canonical rename rules:
1. A canonical document may be renamed or moved only if its durable ID remains unchanged.
2. All inbound references must continue to resolve through the ID-to-path index in the same change.
3. `validate` must fail if any canonical ID referenced by a task, ADR, department index, or handoff cannot be resolved.
4. If a rename changes human-facing meaning materially, create either a migration spec or a changelog entry that records the rename explicitly.
5. Path strings must never be used as canonical identity in task, ADR, architecture, department-index, or handoff schemas.

This policy prevents silent stale-reference drift after file moves.

## 4. Design Decisions

1. **Commit fully to ID-based canonical references.** The prior draft mixed IDs and paths too casually. This revision makes IDs the only allowed canonical reference form in tasks, ADRs, handoffs, department indexes, and architecture docs, while a derived `id-path-index.md` resolves current locations. This is the safest answer to rename drift and directly hardens failure mode 1. 

2. **Treat paths as location metadata, not identity.** Some fields still need paths, but only where the system is describing filesystem artifacts rather than canonical knowledge objects. `linked_output_files` therefore remains path-based because it points at repo files that are not themselves vault documents. Everything else that identifies canonical context uses IDs.

3. **Make plan entries canonical and the execution summary derived.** The earlier version risked duplicate truth by making both `execution-plan.md` and `PLAN-###` files canonical. This revision picks one source of truth: `PLAN-###` entries are canonical, and `vault/99_derived/execution-plan-summary.md` is generated from them. That is simpler to validate and less drift-prone.

4. **Define department mapping explicitly in a registry schema.** The earlier version implied the mapping between folder name, slug, and human title. This revision adds a normative department registry schema so Phase 2 cannot improvise. The registry is canonical for slug-to-folder-to-index resolution.

5. **Tighten ambiguous field contracts now rather than in implementation.** `owner` and `owners` are constrained to registered team slugs, human handles, or specific literals; `canonical_refs` accepts IDs only; `linked_output_files` allows files only, not directories; `status_snapshot` is explicitly non-semantic; and date-time fields are required to be ISO 8601 UTC. These choices make validator behavior predictable.

6. **Use timestamp-first handoff ordering with ID as tie-breaker.** Highest handoff ID alone is brittle if IDs are generated incorrectly. This revision requires both monotonic IDs and timestamps and makes validation fail when they disagree materially. Retrieval uses `created_at` first and `handoff_id` second.

7. **Keep reference documentation outside the runtime model.** `docs/phase1-persistent-project-brain.md` remains valuable, but it is classified as reference-only, not canonical runtime truth. Phase 2 should implement against the vault and schema contracts, not parse this design document during normal operation.

8. **Let canonical indexes stay lightweight; derive full inventories.** Requiring every `index.md` to hand-maintain a full child inventory will become tedious in larger repositories. This revision allows indexes to describe scope and point to the generated inventory in `99_derived/id-path-index.md`, which is a more maintainable compromise.

9. **Make version comparison semantics explicit.** `schema_version` remains a string for readability in YAML, but validators must parse it numerically as `major.minor`. That avoids subtle bugs once versions such as `1.10` appear.

10. **Separate rename policy from schema rules.** Rename safety is important enough to deserve its own meta document and validator responsibility rather than being implied indirectly by broken-link reports. This makes the operational policy visible and machine-checkable.

11. **Continue deferring parallel worktree support.** The design deliberately stops short of lock management or concurrent-branch coordination. The ID-first model and registry structure leave extension points for Phase 3 without adding premature complexity now.

## 5. Phase 2 implementation target and open questions

Phase 2 should implement the schema registry, ID registry builder, ID-to-path derived index generation, deterministic `/resume` and `/wrap-up` commands, rename-policy validation, output-file existence checks, handoff ordering validation, migration enforcement, and test fixtures exactly against the contracts above. The remaining open questions are intentionally narrow: whether Python or Node.js is the better scripting baseline for the team, how owner registries should be sourced locally in v1.0, and whether the derived ID-to-path index should be a markdown table only or also emitted as a machine-only JSON artifact alongside the markdown report. Those questions affect ergonomics, not the storage model, and should be resolved before implementation starts.
