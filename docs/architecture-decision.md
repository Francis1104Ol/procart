# ProCart Architecture Decision Record

## CAT-001 — Stack Decision and Running Service

Date: 2026-09-10

## 1. Context

ProCart is starting with no application code, database schema, or seed data.

The first sprint focuses on product catalogue search and filtering over a deliberately large dataset.

The catalogue is designed to support approximately 1 million products during the year, with a minimum benchmark seed of 500,000 products for this sprint.

The main technical concern is predictable query performance as the catalogue grows.

The important workload characteristics are:

- keyword search over product names
- category filtering
- price filtering
- stock-state filtering
- sorting
- pagination
- catalogue growth
- reads occurring alongside writes

The architecture therefore needs to make database behaviour observable and measurable.

---

## 2. Service

### Decision

Use Python with FastAPI.

### Why

FastAPI provides a small HTTP layer with automatic OpenAPI documentation and straightforward request/response handling.

The service layer should remain thin so that the sprint's technical focus stays on database behaviour rather than framework complexity.

### Alternatives considered

#### Node.js / Express

Rejected because it does not provide a significant advantage for this workload, while Python/FastAPI gives us a simple typed API layer and strong testing ergonomics.

#### NestJS

Rejected because its additional application structure is not necessary for the small read service being built in this sprint.

### Evidence that would overturn this decision

If API-layer overhead, ecosystem constraints, or operational requirements became a measurable bottleneck, the service framework would be reconsidered.

The datastore decision is independent of the API framework.

---

## 3. Data Store

### Decision

Use PostgreSQL.

### Why

The catalogue requires:

- structured filtering
- range queries
- sorting
- pagination
- indexing
- query-plan inspection
- predictable transactional behaviour

PostgreSQL provides the query planning and inspection tools needed to measure how the database answers these queries.

It also gives us multiple indexing strategies to evaluate as the search workload develops.

### Alternatives considered

#### MongoDB

Rejected because the primary workload is structured catalogue filtering and relational querying rather than document-oriented access.

The sprint also requires careful inspection of query plans and indexing behaviour in a relational database.

#### SQLite

Rejected because it is useful for local development but is not the intended production datastore for a catalogue designed around hundreds of thousands to millions of products and concurrent reads/writes.

### Evidence that would overturn this decision

We would reconsider PostgreSQL if, after exhausting appropriate query shapes, indexing, statistics, schema design, and database tuning, representative workloads still consistently failed the agreed latency target at the intended scale.

We do not get to blame PostgreSQL until we have demonstrated that we used PostgreSQL correctly.

---

## 4. API Shape

### Decision

Use a REST API.

### Why

The initial workload consists of predictable catalogue operations:

- list products
- search products
- filter products
- paginate products

REST gives the service a simple and explicit interface without introducing query-language complexity that is not required by this sprint.

### Alternative considered

#### GraphQL

Rejected because the initial catalogue read path does not require clients to construct arbitrary nested queries.

GraphQL may be reconsidered if future product requirements demonstrate a real need for flexible client-defined data selection.

### Evidence that would overturn this decision

If multiple clients require substantially different response shapes or increasingly complex resource traversal that creates meaningful duplication or API complexity, the API shape should be revisited.

---

## 5. Catalogue and Payments Separation

The catalogue read path must not depend on payment, checkout, or account functionality.

The catalogue service is responsible for catalogue concerns such as:

- product lookup
- search
- filtering
- sorting
- pagination

Payment functionality is a separate concern.

A future payment or checkout change should therefore not require changes to the catalogue query implementation unless there is an explicit product requirement connecting the two.

This separation keeps the search workload independently measurable.

---

## 6. Initial Search Hypothesis

A broad contains-match such as:

    WHERE name ILIKE '%pro%'

is expected not to benefit from a conventional B-tree index on `name`.

The leading wildcard prevents a normal B-tree index from efficiently narrowing the search space in the same way as an equality or prefix lookup.

This is a hypothesis, not an assumption to be treated as fact.

It will be tested with:

    EXPLAIN (ANALYZE, BUFFERS)

at the benchmark dataset sizes.

The prediction will be recorded before the plan is inspected.

---

## 7. Performance Measurement

The sprint's keyword-search target is one second on the reference machine at the full seed size.

Latency determines whether the performance target was met.

The query plan answers a different question: how PostgreSQL achieved that latency.

Therefore:

- a Sequential Scan can still pass the latency requirement
- an Index Scan can still fail the latency requirement

The plan explains behaviour; the measured number determines whether the agreed latency bar was met.

Every benchmark must record the dataset size against which it was run.

---

## 8. Performance Investigation Order

If a query misses the performance target, investigation proceeds in this order:

1. Query shape
2. Index strategy
3. Database statistics and configuration
4. Schema/data design
5. Application/API layer
6. Datastore choice

The intention is to investigate cheap and reversible causes before changing architectural decisions.

---

## 9. Architecture Exit Condition

The PostgreSQL decision should be reconsidered only when controlled experiments demonstrate that:

- the query shape is appropriate
- relevant indexes have been evaluated
- query plans have been inspected
- statistics are healthy
- database resources are sufficient
- schema choices have been considered
- application overhead has been separated from database latency

and the representative workload still consistently fails the agreed performance target at the intended scale.

The decision must be based on repeatable measurements rather than assumptions or preference.
