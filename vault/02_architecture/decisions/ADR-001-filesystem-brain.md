---
schema_version: "1.0"
doc_type: decision_record
decision_id: ADR-001
title: Use a filesystem-backed markdown vault
status: accepted
date: "2026-03-23"
owners:
  - team-staff-eng
related_tasks:
  - TASK-001
related_docs:
  - DOC-product-scope
---

## Context
The system must work offline and remain easy to inspect.

## Decision
Use markdown files in Git as the durable store for project memory.

## Consequences
Humans can diff state, but validators must be strict.

## Alternatives Considered
SQLite and external hosted storage.

## References
Product scope and engineering standards.
