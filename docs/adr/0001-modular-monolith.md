# ADR 0001: Keep execution in a modular monolith

- Status: accepted
- Date: 2026-10-01

## Decision

Boiler Reviews remains one Flask deployable with explicit domain and application modules, plus one durable worker process. Modules communicate through typed service contracts and database records rather than importing route handlers or constructing ORM queries in templates.

## Why

Catalog compilation and planning have meaningful isolation boundaries, but they need the same catalog, plan, and task state. A modular monolith keeps transactions and local development understandable while the worker isolates long-running imports and solver runs. Splitting CRUD into network services would add failure modes without solving a present execution problem.

## Consequences

- Routes translate HTTP into request schemas and call application services.
- Services own transaction boundaries and return typed outcomes.
- Prerequisite parsing, degree allocation, scheduling, and validation remain framework-independent.
- PostgreSQL is the production concurrency contract; SQLite is an isolated development/test option.
- Task leases and fencing provide process isolation for long-running work.
