---
name: system-design
description: Works through backend and distributed-system design by reasoning from requirements and numbers instead of recalled diagrams. Clarifies scope, estimates scale, composes building blocks, states what each choice solves, worsens and when to change it, stress-tests failure modes, scores the design and renders an icon-based architecture diagram as SVG (embeddable in Markdown) or HTML. Use for open-ended "design X" problems (a URL shortener, WhatsApp, a news feed, a rate limiter), system design interview practice, architecture reviews, and single building-block questions such as caching strategy, SQL vs NoSQL, sharding, queues vs streams, consistency models, load balancing, CDN, DNS, unique IDs, search, logging, observability, job scheduling, counters at scale, resilience or how a design scales. Run as /system-design design [problem] for the full workflow.
argument-hint: design <system to design, e.g. "a URL shortener" or "WhatsApp at 1B users">
---

# System design

A port of the MIT-licensed `system-design-skills` plugin (Proyecto 26, see `LICENSE`). It runs a reasoning loop (clarify, estimate, design, trade-offs, failure modes, iterate) and keeps each building block in its own topic file, so you load only the part the question needs.

## How to use

There are two ways in.

- Full design. The user runs `/system-design design <problem>` or asks an open-ended "design X" question, wants interview practice, or wants an architecture reviewed across several components. Read `commands/design.md` and follow it. It dispatches the orchestrator (`agents/system-design-orchestrator.md`), which reads `topics/system-design/README.md` for the reasoning loop and then reads each building-block topic as its concern comes up. Example: `/system-design design a URL shortener that handles 10k writes/sec and billions of reads`.
- Single topic. When the question is about one component ("what cache eviction policy for a session store?", "how do I shard this table?"), read only that topic's file from the list below and answer from it. Don't run the orchestrator for a one-part question. Example: `/system-design what caching strategy for a read-heavy feed, and how do I stop stampedes?`

## Routing

If the arguments ($ARGUMENTS in Claude Code) start with `design`, read `commands/design.md` and follow it. In that file, `$ARGUMENTS` means the problem text after `design`. If nothing follows `design`, ask what system to design and at what rough scale.

When the command dispatches the orchestrator (subagent_type `system-design-skills:system-design-orchestrator`), spawn a general-purpose subagent whose brief is the body of `agents/system-design-orchestrator.md` plus the problem. In a tool without subagents, follow that file yourself.

Path rules for every file in this skill:

- A bare block name such as `caching` or `data-storage`, or "invoke"/"trigger" a block, means read `topics/<name>/README.md` and apply it.
- `topics/...` paths are relative to this skill's folder (`~/.agents/skills/system-design`).
- Inside a topic file, `references/`, `assets/` and `scripts/` paths are relative to that topic's folder.

## Topics

Each topic file defaults to a vendor-neutral recipe. When the user names a cloud, it points to `references/providers/<aws|azure|gcp|temporal>.md` in its folder.

- When the question is a whole design ("design X", "how would you architect...", interview practice), read `topics/system-design/README.md`. It holds the reasoning loop, the ten failure modes, the trade-off framework, the building-blocks index and the design-doc template.
- When the question is about clarifying requirements, functional vs non-functional, scope or which questions to ask, read `topics/requirements-scoping/README.md`.
- When the question is about estimating QPS, storage, bandwidth, server count, peak load or capacity, read `topics/back-of-the-envelope/README.md` (it ships `scripts/botec.py`).
- When the question is about endpoints, request/response shape, pagination, idempotency keys, versioning, error contracts, or REST vs gRPC vs GraphQL vs WebSocket, read `topics/api-design/README.md`.
- When the question is about monolith vs microservices, service boundaries or granularity, API gateway/BFF, service discovery or a mesh, read `topics/service-decomposition/README.md`.
- When the question is about SQL vs NoSQL, which database, data model, schema, indexing, sharding, partitioning or replication, read `topics/data-storage/README.md`.
- When the question is about what to cache, read/write-through vs write-back, eviction, invalidation, Redis vs Memcached, stampedes or hot keys, read `topics/caching/README.md`.
- When the question is about load balancers, L4 vs L7, balancing algorithms, health checks, sticky sessions, reverse proxies or TLS termination, read `topics/load-balancing/README.md`.
- When the question is about CDNs, edge caching, static or media delivery, push vs pull CDN, cache-control headers or origin shield, read `topics/content-delivery/README.md`.
- When the question is about DNS, GeoDNS, latency/weighted/failover routing, record types, anycast or TTL, read `topics/dns/README.md`.
- When the question is about queues, Kafka, pub/sub, streams, event-driven design, delivery guarantees, ordering, dedup, DLQs, backpressure, sagas or durable workflows, read `topics/messaging-streaming/README.md`.
- When the question is about job schedulers, cron at scale, delayed or recurring tasks, worker pools, task leasing or duplicate execution, read `topics/task-scheduling/README.md`.
- When the question is about CAP, PACELC, consistency models, quorum, consensus (Raft/Paxos), leader election, consistent hashing, 2PC or distributed transactions, read `topics/consistency-coordination/README.md`.
- When the question is about unique IDs at scale, Snowflake, UUID vs auto-increment, time-sortable IDs or ticket servers, read `topics/sequencer/README.md`.
- When the question is about object storage, S3, storing images/video/files, multipart or resumable uploads, signed URLs, tiering or erasure coding, read `topics/blob-store/README.md`.
- When the question is about counting likes or views at high write rates, hot counter contention, approximate counts or HyperLogLog, read `topics/sharded-counters/README.md`.
- When the question is about full-text search, inverted indexes, Elasticsearch/OpenSearch, ranking, autocomplete or indexing pipelines, read `topics/distributed-search/README.md`.
- When the question is about fault tolerance, circuit breakers, retries with backoff, timeouts, bulkheads, SPOFs, failover, graceful degradation or rate limiting, read `topics/resilience-failure/README.md`.
- When the question is about monitoring, metrics/logs/traces, health checks, SLOs and error budgets, alerting or dashboards, read `topics/observability/README.md`.
- When the question is about log aggregation, ELK/EFK, log shipping, structured logging, correlation IDs or log retention, read `topics/distributed-logging/README.md`.
- When the question is about how a design scales, 10x growth, the next bottleneck, vertical vs horizontal scaling or a scaling roadmap, read `topics/scaling-evolution/README.md`.
- When the user wants the architecture drawn (components, data flow, regions, failure paths), read `topics/architecture-diagram/README.md` and render a JSON spec with its `scripts/render_diagram.py`: an `.svg` to embed in Markdown, or an `.html` page.
