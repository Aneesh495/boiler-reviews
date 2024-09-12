# System and data architecture

Boiler Reviews is a modular monolith with one durable worker. Flask translates HTTP into typed application-service calls. Domain modules do not import Flask or construct ORM queries: catalog compilation, prerequisite evaluation, degree allocation, planning, section scheduling, validation, and task leasing remain executable as ordinary Python contracts. SQLAlchemy owns persistence and ordered migrations; PostgreSQL is the production concurrency contract and SQLite is an isolated development/test option.

```mermaid
flowchart LR
  U[Course and planning interface] --> H[Flask application services]
  H --> DB[(PostgreSQL / local SQLite)]
  I[Canonical catalog JSON/CSV adapter] --> C[Catalog staging and compiler]
  C --> DB
  DB --> G[Typed prerequisite graph]
  G --> S[CP-SAT planner]
  S --> V[Independent validator]
  V --> H
  H --> O[(Transactional outbox)]
  O --> W[Durable worker]
  W --> DB
```

```mermaid
erDiagram
  INSTITUTION ||--o{ ACCOUNT : contains
  INSTITUTION ||--o{ CATALOG_SNAPSHOT : publishes
  CATALOG_SNAPSHOT ||--o{ COURSE_VERSION : freezes
  COURSE ||--o{ COURSE_VERSION : identity
  INSTITUTION ||--o{ COURSE : owns
  COURSE ||--o{ REVIEW : receives
  ACCOUNT ||--o{ REVIEW : authors
  REVIEW ||--o{ REVIEW_REVISION : versions
  REVIEW ||--o{ MODERATION_DECISION : judged
  COURSE ||--o{ COURSE_AGGREGATE : aggregates
  TERM ||--o{ COURSE_AGGREGATE : scopes
  ACCOUNT ||--o{ STUDENT_PLAN : owns
  STUDENT_PLAN ||--o{ PLAN_ITEM : contains
  COURSE_VERSION ||--o{ PLAN_ITEM : selects
  DURABLE_TASK ||--o{ OUTBOX_EVENT : produces
```

The stable `courses` row is the review-history identity. `course_versions` is a snapshot-specific presentation and prerequisite contract. Plans keep both the catalog snapshot and degree-rule version that produced them, so a later catalog cannot silently rewrite a historical plan. Review aggregates contain counts and sufficient sums by course/term; the authoritative published revision pointer is the reconciliation input.

```mermaid
sequenceDiagram
  participant Import as Catalog importer
  participant DB as Database
  participant Active as Active snapshot
  Import->>DB: validate staged document and prerequisite AST
  DB-->>Import: reject on duplicate, unknown reference, or strict cycle
  Import->>DB: transactionally stage snapshot and course versions
  Import->>DB: lock institution active pointer
  DB->>Active: archive previous active snapshot
  DB-->>Import: activate new immutable snapshot and audit event
```

```mermaid
flowchart TD
  T[Original prerequisite text] --> L[Tokenizer]
  L --> P[Typed parser]
  P --> A{Parsed?}
  A -->|yes| AST[AND / OR / grade / credit / predicate / coreq AST]
  A -->|no| UN[Unsupported and unresolved with diagnostics]
  AST --> E[Provenance graph edges]
  E --> SCC[Strongly connected components]
  SCC -->|strict cycle| REJECT[Import rejection]
  SCC -->|corequisite group| GRAPH[Readable dependency graph]
```

```mermaid
sequenceDiagram
  participant Owner
  participant API
  participant DB
  participant Agg as Course aggregate
  participant Outbox
  Owner->>API: submit or edit review with revision token
  API->>DB: transition, revision, audit, aggregate delta, outbox event
  DB->>Agg: lock affected course/term rows in stable order
  DB-->>API: commit all or roll back all
  API-->>Owner: state and revision
  Outbox->>DB: claim with lease and fencing token
  Outbox-->>DB: idempotent projection completion
```

```mermaid
stateDiagram-v2
  [*] --> queued
  queued --> running: worker claims lease
  running --> succeeded: fenced result commit
  running --> failed: fenced error commit
  running --> cancelled: cancellation observed
  running --> queued: lease expires and recovery requeues
  running --> running: heartbeat extends lease
```

```mermaid
flowchart LR
  R[Completed and planned courses] --> A[Requirement allocation]
  A --> G1[Core group]
  A --> G2[Elective group]
  A --> X{Double counting explicitly allowed?}
  X -->|no| ONE[At most one group allocation]
  X -->|yes| MULTI[Rule permits reuse]
  G1 --> AUDIT[ satisfied / pending / unsatisfied / unknown audit]
  G2 --> AUDIT
```

```mermaid
flowchart TD
  Fail[Process interruption] --> Lease[Lease expires]
  Lease --> Fence[Incremented fencing token]
  Fence --> Retry[New worker retries idempotent task]
  Fail --> Tx[Database transaction rollback]
  Tx --> Pointer[Active catalog/review aggregate remains prior consistent state]
  Retry --> Validate[Independent validator/reconciliation]
  Validate -->|pass| Publish[Commit result]
  Validate -->|fail| Audit[Replayable failure audit event]
```

These diagrams describe the modules in `src/boiler_reviews`, not a proposed future service mesh. A separate process exists only for long-running tasks and projection isolation.
