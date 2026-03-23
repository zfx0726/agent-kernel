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
  - ADR-002
related_tasks:
  - TASK-003
reviewed_at: "2026-03-23"
---

## Overview
Describes the trust boundaries for local CLI access to the vault.

## Constraints
No cloud account dependencies and no opaque authentication state.

## Proposed Structure
Trust the local filesystem and Git checkout as the execution boundary.

## Operational Implications
Resume and wrap-up operate only on the local repository state.

## References
ADR-002 and DOC-coding-standards.
