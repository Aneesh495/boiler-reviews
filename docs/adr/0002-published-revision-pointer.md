# ADR 0002: Keep approved review content while edits are pending

- Status: accepted
- Date: 2026-10-01

A published review edit creates a new numbered revision, changes the workflow state to `submitted`, and leaves `published_revision` pointing to the last approved content. Public reads and aggregate reconciliation include `published` and `submitted` records only when that pointer exists, and always join the pointer rather than the pending revision.

This avoids making a student's approved evidence disappear while a moderator reviews an edit. A hidden or rejected record is excluded by state. Publishing a pending revision subtracts the old sufficient-statistics delta and adds the new one in the same transaction. A reconciliation scan is authoritative if a process dies between a write and a projection.
