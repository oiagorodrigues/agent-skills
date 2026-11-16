# Books behind the rules

Read this when you need the source of a rule in `SKILL.md` or its reference files, for example to cite it in a review or to read further. One line per book: what in this skill comes from it. Sources that aren't books (pstack, ub-mode, Matt Pocock's skills) are credited inline next to their rules.

- Designing Data-Intensive Applications, 1st edition (Kleppmann): name the system of record for every copy, monotonic clocks for durations and versions for ordering (`data-rules.md`); the rules against dual writes (outbox) and for idempotent consumers in the distributed-systems section.
- Designing Data-Intensive Applications, 2nd edition (Kleppmann and Riccomini): the same data rules, plus property-based tests for invariants (`testing-rules.md`).
- Database Internals (Petrov): no rule here. Its storage-engine material (B-trees and LSM trees, MVCC, the write-ahead log) backs `system-design` and `postgres-best-practices`.
- A Philosophy of Software Design (Ousterhout): deep modules, comments for the non-obvious why, split modules by the knowledge they hide, pull complexity down, define errors out of existence (`design-rules.md`).
- Working Effectively with Legacy Code (Feathers): sprout and wrap (`testing-rules.md`); lock in current behavior with tests before a rewrite (characterization tests); seams.
- Refactoring, 2nd edition (Fowler): the Flag Argument and Query With Side Effects rules, from its "Remove Flag Argument" and "Separate Query from Modifier" refactorings (`design-rules.md`).
- Tidy First? (Beck): tidy first as its own PR (`delivery-rules.md`); keep structure changes and behavior changes in separate PRs.
- Domain-Driven Design (Evans), Implementing Domain-Driven Design (Vernon) and Learning Domain-Driven Design (Khononov): change an invariant's rows together (`data-rules.md`), the anti-corruption layer and the domain's words (`design-rules.md`).
- Release It!, 2nd edition (Nygard): set retention deliberately (its Steady State pattern: everything that accumulates needs a purge). Its timeouts, circuit breakers and bulkheads live in `backend-design` and `system-design`.
- Site Reliability Engineering and The Site Reliability Workbook (Google): roll out risky changes to a slice first (`delivery-rules.md`); objectives from real baselines in the observability section.
- Software Engineering at Google (Winters, Manshreck, Wright): Hyrum's law (`data-rules.md`).
- Accelerate (Forsgren, Humble, Kim): small, single-purpose PRs.
- The Pragmatic Programmer, 20th anniversary edition (Thomas and Hunt): tracer bullets (`delivery-rules.md`); DRY applies to knowledge, not to similar-looking text.
- Building Evolutionary Architectures (Ford, Parsons, Kua): keep architecture rules in a checker, as fitness functions (`design-rules.md`).
- AI Engineering and Designing Machine Learning Systems (Huyen): no rule here. Their evaluation material backs the `ai-engineering` skill.
- Clean Code (Martin): names that reveal intent. Its tiny-function, comments-are-failures and Boy Scout rules are left out on purpose, because they conflict with deep modules, why-comments and staying in scope.
