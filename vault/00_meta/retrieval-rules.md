---
schema_version: "1.0"
doc_type: meta_document
doc_id: DOC-retrieval-rules
title: Retrieval Rules
status: active
owner: team-platform
---

## Purpose
Defines deterministic file loading for resume and wrap-up commands.

## Rules
Resume loads meta prerequisites, the target task, direct dependencies, matching plan entries, the department index, the latest valid handoff, linked canonical docs, and the ADRs declared by those docs.

## References
See [[DEPT-REGISTRY]] and [[DOC-schema-registry]].
