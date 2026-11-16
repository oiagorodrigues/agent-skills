---
description: Run the bottom-up system-design workflow on a problem — clarify, estimate, design with building blocks, weigh trade-offs, stress-test, and diagram. Great for design questions and system-design interview practice.
argument-hint: <system to design, e.g. "a URL shortener" or "WhatsApp at 1B users">
allowed-tools:
- "Task"
- "Skill"
- "Read"
- "Write"
- "Glob"
- "Grep"
- "Bash"
---

Run the system-design process for: **$ARGUMENTS**

Drive this as a collaborative design session using this skill, following the GUIDE reasoning loop. Do not jump to a finished architecture.

1. **Launch the orchestrator.** Spawn a general-purpose subagent whose brief is the body of `agents/system-design-orchestrator.md` (everything below its frontmatter) plus the problem above. It reads `topics/system-design/README.md` (the method) and composes the building-block topic files.
   - If subagent launch is unavailable, run the loop inline yourself: read `topics/system-design/README.md` first, then route to building-block topic files as each concern arises — read each topic file, don't paraphrase it. The full catalog (the 20 building blocks, bottom-up layers) is `topics/system-design/references/building-blocks-index.md`; each bare name below means `topics/<name>/README.md`. Reach for whichever fit, including the less-obvious ones (`service-decomposition`, `dns`, `sequencer`, `blob-store`, `observability`, `distributed-logging`, `distributed-search`, `task-scheduling`, `sharded-counters`) alongside the core (`requirements-scoping`, `back-of-the-envelope`, `api-design`, `data-storage`, `caching`, `load-balancing`, `messaging-streaming`, `consistency-coordination`, `resilience-failure`, `content-delivery`, `scaling-evolution`). For "monolith vs microservices / where are the service boundaries", that is `service-decomposition`.

2. **Work the loop out loud:** clarify requirements (functional / non-functional / out-of-scope) → estimate scale with numbers → propose a high-level design + API → articulate trade-offs (solves / worsens / when-to-change) per major choice → stress-test failure modes → iterate, pivoting the affected part when a constraint changes.

3. **Ask** a clarifying question whenever an answer is load-bearing (consistency model, single vs multi-region, sync vs async) and cannot be assumed safely. Treat the user as a collaborator, not an audience.

4. **Capture & persist** the running design with `topics/system-design/assets/design-doc-template.md`, write the settled artifacts to a file (suggest `docs/design/<system>.md`), and when it stabilizes render it with `topics/architecture-diagram/README.md`.

5. **Score, then close.** Rate the design with the quality bar + Quick Diagnostic in `topics/system-design/references/failure-modes.md`, state the weakest dimension, then name the current bottleneck and what would change at the next order of magnitude. Never claim the design is perfect.

If `$ARGUMENTS` is empty, ask the user what system they want to design (and at what rough scale) before starting.
