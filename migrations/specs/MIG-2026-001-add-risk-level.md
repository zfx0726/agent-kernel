---
schema_version: "1.0"
doc_type: migration_spec
migration_id: MIG-2026-001
title: Add risk_level to task schema
status: approved
target_file_types:
  - task
introduced_in_version: "1.1"
requires_backfill: true
approved_by:
  - team-platform
approved_at: "2026-03-23T16:00:00Z"
---

## Change Summary
Introduce a required risk_level field for task documents.

## Rationale
Task priority alone does not communicate operational review needs.

## Compatibility Impact
All existing tasks need a backfilled risk_level before task schema 1.1 can go active.

## Migration Steps
```yaml
operations:
  - type: add_frontmatter_field
    target: task
    field: risk_level
    value: medium
```

## Validation Requirements
Validation must fail mixed usage after the registry activates schema 1.1.

## Rollback / Supersession
Supersede with a follow-up migration if the field shape changes.
