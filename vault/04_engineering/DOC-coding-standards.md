---
schema_version: "1.0"
doc_type: architecture_doc
doc_id: DOC-coding-standards
title: Coding Standards
status: active
owners:
  - team-platform
department_slug: engineering
related_decisions:
  - ADR-002
related_tasks:
  - TASK-002
reviewed_at: "2026-03-23"
---

## Overview
Defines coding and validation expectations for the project brain implementation.

## Constraints
Use boring technology, keep state deterministic, and fail loudly on invalid vault state.

## Proposed Structure
Prefer small standard-library Python modules and testable validators.

## Operational Implications
Tasks that touch tooling should link this doc.

## References
ADR-002.
