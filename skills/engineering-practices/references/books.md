# Books behind the rules

Read this when you need the source of a rule in `SKILL.md` or its reference files, for example to cite it in a review or to read further. One line per book: what in this skill comes from it. Sources that aren't books (pstack, ub-mode, Matt Pocock's skills) are credited inline next to their rules.

- Designing Data-Intensive Applications, 1st edition (Kleppmann): name the system of record for every copy, monotonic clocks for durations and versions for ordering (`data-rules.md`); the rules against dual writes (outbox) and for idempotent consumers in the distributed-systems section.
- Designing Data-Intensive Applications, 2nd edition (Kleppmann and Riccomini): the same data rules, plus property-based tests for invariants (`testing-rules.md`).
- Database Internals (Petrov): no rule here. Its storage-engine material (B-trees and LSM trees, MVCC, the write-ahead log) backs `system-design` and `postgres-best-practices`.
- A Philosophy of Software Design (Ousterhout): deep modules, comments for the non-obvious why, split modules by the knowledge they hide, pull complexity down, define errors out of existence (`design-rules.md`); classitis, the over-split side of single responsibility (`design-principles.md`).
- Working Effectively with Legacy Code (Feathers): sprout and wrap (`testing-rules.md`); lock in current behavior with tests before a rewrite (characterization tests); seams.
- Refactoring, 2nd edition (Fowler): the Flag Argument and Query With Side Effects rules, from its "Remove Flag Argument" and "Separate Query from Modifier" refactorings (`design-rules.md`); the rule of three (`design-principles.md`) and "Introduce Special Case" (`patterns.md`).
- Tidy First? (Beck): tidy first as its own PR (`delivery-rules.md`); keep structure changes and behavior changes in separate PRs.
- Domain-Driven Design (Evans), Implementing Domain-Driven Design (Vernon) and Learning Domain-Driven Design (Khononov): change an invariant's rows together (`data-rules.md`), the anti-corruption layer and the domain's words (`design-rules.md`); repository, specification and value object (`patterns.md`).
- Release It!, 2nd edition (Nygard): set retention deliberately (its Steady State pattern: everything that accumulates needs a purge). Its timeouts, circuit breakers and bulkheads live in `backend-design` and `system-design`, with a short entry each in `patterns.md`.
- Site Reliability Engineering and The Site Reliability Workbook (Google): roll out risky changes to a slice first (`delivery-rules.md`); objectives from real baselines in the observability section.
- Software Engineering at Google (Winters, Manshreck, Wright): Hyrum's law (`data-rules.md`).
- Accelerate (Forsgren, Humble, Kim): small, single-purpose PRs.
- The Pragmatic Programmer, 20th anniversary edition (Thomas and Hunt): tracer bullets (`delivery-rules.md`); DRY applies to knowledge, not to similar-looking text; orthogonality and "Crash Early" (`design-principles.md`).
- Building Evolutionary Architectures (Ford, Parsons, Kua): keep architecture rules in a checker, as fitness functions (`design-rules.md`).
- AI Engineering and Designing Machine Learning Systems (Huyen): no rule here. Their evaluation material backs the `ai-engineering` skill.
- Agile Software Development, Principles, Patterns, and Practices and Clean Architecture (Martin): the five SOLID principles and the acyclic and stable dependencies principles (`design-principles.md`); clean architecture and the dependency rule (`patterns.md`).
- Object-Oriented Software Construction (Meyer): open-closed and command-query separation (`design-principles.md`, `design-rules.md`).
- Design Patterns (Gamma, Helm, Johnson, Vlissides): composition over inheritance (`design-principles.md`) and the design patterns in `patterns.md`.
- Structured Design (Yourdon and Constantine): cohesion and coupling (`design-principles.md`).
- The Art of Unix Programming (Raymond): the rule of least surprise (`design-principles.md`).
- Patterns of Enterprise Application Architecture (Fowler): layering, service layer, repository, unit of work, active record and data mapper, data transfer object (`patterns.md`).
- Architecture Patterns with Python (Percival and Gregory): the same application patterns in Python (`patterns.md`).
- Fundamentals of Software Architecture (Richards and Ford): the architectural styles (layered, pipeline, microkernel, modular monolith) in `patterns.md`.
- Enterprise Integration Patterns (Hohpe and Woolf): pipes and filters, event-driven messaging and the dead-letter channel (`patterns.md`).
- Building Microservices (Newman) and Microservices Patterns (Richardson): microservices and sagas (`patterns.md`).
- Growing Object-Oriented Software, Guided by Tests (Freeman and Pryce): test data builders (`patterns.md`).
- Pattern Languages of Program Design 3 (Martin, Riehle, Buschmann, editors): Woolf's Null Object (`patterns.md`).
- Clean Code (Martin): names that reveal intent. Its tiny-function, comments-are-failures and Boy Scout rules are left out on purpose, because they conflict with deep modules, why-comments and staying in scope.
