# ADR 0002: Begin with PostgreSQL and normalized graph tables

- Status: Accepted as the production storage direction; deployment validation pending
- Date: 2026-10-03

## Context

The platform supports SQLite by default and PostgreSQL with full-text search and optional pgvector. The plan targets one project and warns against introducing multiple stores before measurements justify them. The target corpus size, concurrency, and OVH hardware are unknown.

## Decision

Keep SQLite for lightweight local development and use PostgreSQL as the initial shared-deployment database. Store graph nodes and edges in the existing relational persistence model. Use PostgreSQL full-text search and pgvector only where the selected embedding setup supports it. Do not add Qdrant, Neo4j, Elasticsearch, or Redis before a measured need is documented.

## Consequences

- The initial operational stack has one primary database.
- Schema and migration compatibility with the selected CodeWiki revision must be checked before deployment.
- Capacity, vector-search value, backup/restore, and indexing performance remain unmeasured until target data and host access are available.
