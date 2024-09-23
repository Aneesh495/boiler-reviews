# Extended domain contracts

The catalog adapters accept canonical JSON and a documented flat CSV format. They attach source hashes and provenance, reject malformed credits, preserve original prerequisite text, and never scrape a private university system. Catalog impact analysis compares stable identities across snapshots and marks saved plans needing review when selected courses change credits, prerequisites, availability, or identity presentation.

Review reads use stable keyset cursors when a client needs repeatable pagination. Instructor and cohort breakdowns retain denominators. Duplicate contribution policy is explicit and account/course/term scoped; the policy explains that it mitigates abuse but cannot prove enrollment or identity uniqueness. A process-local token bucket protects write endpoints without becoming an identity claim.

Planning prechecks catch impossible pins, capacity totals, and requirement shortages before constructing the model. Alternative objective vectors can be compared for non-dominance without calling the result an exhaustive Pareto frontier. Linked lecture/lab groups validate required components separately from meeting conflicts. Outbox projection helpers require the event owner and make duplicate application visible in audit events.
