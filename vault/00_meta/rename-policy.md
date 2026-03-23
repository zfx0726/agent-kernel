---
schema_version: "1.0"
doc_type: meta_document
doc_id: DOC-rename-policy
title: Rename Policy
status: active
owner: team-platform
---

## Purpose
Protect canonical IDs from silent drift when files are renamed or moved.

## Rules
Keep document IDs stable, update location metadata in the same change, and fail validation on unresolved inbound references.

## References
See DOC-changelog and DOC-retrieval-rules.
