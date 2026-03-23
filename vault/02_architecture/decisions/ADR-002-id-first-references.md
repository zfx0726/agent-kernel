---
schema_version: "1.0"
doc_type: decision_record
decision_id: ADR-002
title: Use ID-first canonical references
status: accepted
date: "2026-03-23"
owners:
  - team-staff-eng
related_tasks:
  - TASK-002
  - TASK-003
related_docs:
  - ARCH-auth-strategy
  - DOC-coding-standards
---

## Context
Path-based references create rename drift and silent invalid context loading.

## Decision
Use stable IDs for canonical references and derive an ID-to-path index.

## Consequences
Renames become safer but require generated indexes to stay fresh.

## Alternatives Considered
Path-only references and fuzzy retrieval.

## References
Architecture and engineering docs.
