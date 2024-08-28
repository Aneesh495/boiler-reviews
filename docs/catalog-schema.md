# Catalog snapshot and prerequisite contract

Catalog imports are authored JSON documents or adapters that produce the same document shape. A document has an institution identity, an immutable version, source/provenance metadata, courses, and optional academic terms. Course codes are display/version identifiers; `stable_code` is the identity used to retain review history across a title or code presentation change.

```json
{
  "schema_version": "1",
  "institution_code": "DEMO",
  "institution_name": "Demo University",
  "timezone": "America/Indiana/Indianapolis",
  "version": "demo-2026.10",
  "source_uri": "fixture://demo/catalog.json",
  "provenance": {"kind": "authored_fixture", "synthetic": true},
  "courses": [
    {"code": "CS101", "stable_code": "CS101", "title": "Foundations", "credits": 3, "prerequisites": "NONE", "availability": {"Fall": true}},
    {"code": "CS201", "title": "Data Structures", "credits": 3, "prerequisites": "CS101 AND (MA101 OR MA102)"}
  ]
}
```

Imports are parsed and validated in a transaction while the snapshot is `staged`. Duplicate identities, unknown prerequisite references, strict cycles, malformed credit values, and contradictory terms reject the transaction. Activation locks active snapshots for the institution, archives the prior active snapshot, marks the staged snapshot active, and records an audit event. A failed import cannot alter the active pointer.

## Prerequisite grammar

The parser accepts case-insensitive course references (`CS101` and `CS 101` normalize to `CS101`), `AND`, `OR`, parentheses, `GRADE>=B` after a course, `CREDITS>=30`, `PLACEMENT(name)`, `PERMISSION(name)`, and `COREQ(A, B)`. `OR` stays an `AnyOf` node and is never rewritten as `AllOf`. Unsupported catalog language is retained as original text with status `unsupported`; it is not treated as satisfied.

The compiler emits typed AST JSON and graph edges with the original prerequisite text as provenance. Strict strongly connected components are import errors. A component whose edges are all `corequisite` is reported as a legitimate co-requisite group and remains available to the scheduler. Eligibility returns `satisfied`, `unsatisfied`, or `unknown`, with a human-readable dependency path and an explicit reason for unresolved permission or placement predicates.
