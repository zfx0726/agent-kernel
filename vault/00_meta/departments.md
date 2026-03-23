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
Defines the authoritative mapping between department slugs and folder locations.

## Department Entries
See frontmatter for the authoritative mapping.

## Change Rules
Update this file and regenerate derived indexes in the same change.

## Validation Notes
Reject duplicate slugs, missing indexes, and unknown task departments.
