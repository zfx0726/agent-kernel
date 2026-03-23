---
schema_version: "1.0"
doc_type: task
task_id: TASK-006
title: Backfill migration example
status: complete
priority: low
owner: team-platform
department_slug: engineering
dependencies:
  - TASK-002
linked_output_files:
  - artifacts/missing-migration-report.md
linked_canonical_docs:
  - DOC-coding-standards
acceptance_criteria:
  - migration backfill report exists
created_at: "2026-03-23T11:30:00Z"
updated_at: "2026-03-23T14:00:00Z"
---

## Summary
Provide a deliberate validation failure for the example vault.

## Implementation Notes
This task intentionally references a missing file so `brain validate` reports a consistency error.

## Dependency Notes
Depends on TASK-002.

## Validation Plan
Run validate and confirm the missing output is reported.

## Change Log
- 2026-03-23: Task intentionally marked complete with a missing output for testing.
