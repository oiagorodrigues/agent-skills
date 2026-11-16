---
name: codebase-requirements-analyst
description: Use when extracting business rules, functional requirements, and non-functional requirements from an existing codebase or codebases provided by the user. Produces an as-built requirements specification with evidence and traceability.
---

# Codebase Requirements Scan

Extract and document only the **business rules**, **functional requirements**, and **non-functional requirements** that the codebase currently implements or enforces. The output is an as-built requirements specification, not a product roadmap or future design.

**Scope:** Work with the codebase or codebases the user provides. If the user specifies multiple codebases (e.g., monorepo apps, multi-repo), extract from each and synthesize into a single document. If the user does not specify, scan the current working directory.

## Fundamental Principle

**Document only what the code proves.**

Every requirement must have evidence in the codebase: source files, configuration, tests, or runtime guards. Do not infer future intent, suggest improvements, or speculate on product strategy.

## Scope Boundaries

**Include:**
- Business rules (domain constraints, calculations, eligibility, state transitions, thresholds)
- Functional requirements (user- or system-visible behaviors implemented in code)
- Non-functional requirements (security, performance, availability, compliance, usability visible in code/config)

**Exclude:**
- Business vision, stakeholders, personas (cannot be reliably inferred from code)
- Future ideas or unimplemented features
- Refactor suggestions or improvement proposals
- Pure technical inventory without requirement implications
- Requirements without code evidence

For classification heuristics, see [references/requirements-classification.md](references/requirements-classification.md).

## Steps to Follow

1. **Read any directly mentioned files first:**
   - If the user mentions specific files or directories, read them fully in the main context window before spawning sub-tasks
   - This ensures context before decomposing the research

2. **Confirm the codebase or codebases to scan:**
   - If the user has specified a codebase or codebases, use those
   - If not specified, scan the current working directory
   - Record the target(s) for extraction and evidence resolution

3. **Analyze and decompose the extraction goal:**
   - Break each codebase into composable research areas (e.g., auth, payments, validation, config)
   - Identify where business rules, functional behaviors, and quality constraints live
   - Create a research plan using TodoWrite to track subtasks
   - Consider: routes, services, validators, config files, tests, middleware, guards

4. **Spawn parallel sub-agent tasks for comprehensive extraction:**
   - For a single codebase: spawn multiple Task agents for different areas concurrently
   - For multiple codebases: spawn sub-agents per codebase (and optionally per area within each)
   - Start with locator agents to find relevant code
   - Use analyzer agents on promising findings
   - Each sub-agent prompt must be specific and read-only

5. **Wait for all sub-agents to complete and synthesize findings:**
   - Wait for ALL sub-agent tasks before proceeding
   - Compile results and prioritize live codebase as primary source
   - Connect findings across components
   - Include specific file paths and line numbers for evidence
   - Classify each finding as FR, NFR, or BR

6. **Gather metadata for the output document:**
   - Filename: `dev/requirements/YYYYMMDD-codebase-requirements.md`
   - Format: `YYYYMMDD-codebase-requirements.md` (date + kebab-case description)
   - Collect: date, scope summary

7. **Generate the requirements document:**
   - Use the template at [assets/requirements-scan-template.md](assets/requirements-scan-template.md)
   - Structure: Scope & Evidence → Functional Requirements → Non-Functional Requirements → Business Rules → Traceability → Gaps & Assumptions → Quality Checks
   - **Before writing evidence links:** Resolve codebase root (see Evidence and Traceability below). Ask the user; do not assume.
   - Every requirement must cite evidence using the resolved root format
   - Use EARS-style syntax for functional requirements where applicable (see [references/ears-for-code-derived-frs.md](references/ears-for-code-derived-frs.md))

8. **Present findings:**
   - Summarize the extracted requirements for the user
   - Include key file references
   - Note confidence levels and gaps
   - Ask if follow-up extraction is needed

9. **Handle follow-up questions:**
   - Append to the same document with a new section
   - Update frontmatter `last_updated`
   - Spawn new sub-agents as needed

## Output Structure

The generated document must follow this structure:

| Section | Purpose |
|---------|---------|
| Scope & Evidence Statement | What was scanned (codebase(s)), what is in/out of scope, confidence |
| Functional Requirements | Behaviors implemented (FR-01, FR-02, ...) with evidence |
| Non-Functional Requirements | Quality attributes in code/config (NFR-01, NFR-02, ...) with evidence |
| Business Rules | Domain logic and constraints (BR-01, BR-02, ...) with evidence |
| Traceability & Evidence | Table mapping requirement IDs to code locations |
| Assumptions & Gaps | What could not be inferred, areas not covered |
| Quality Checks | Completeness score, missing evidence, status |

## Classification Rules

**Functional requirement:** User- or system-visible behavior implemented by code paths, routes, jobs, workflows, validations, or integrations. Example: "WHEN the user submits the form, THE System shall validate email format."

**Non-functional requirement:** Measurable or enforceable quality attribute visible in code/config. Examples: bcrypt for passwords, rate limits, CORS config, timeout values, TLS settings, test coverage thresholds.

**Business rule:** Domain constraint, calculation, eligibility rule, state transition, threshold, timing window, or policy logic. Example: "An order cannot be canceled after 30 minutes."

See [references/requirements-classification.md](references/requirements-classification.md) for heuristics and edge cases.

## Evidence and Traceability

**Use only when generating the output document** (step 7). Do not apply during discovery or extraction.

Before writing evidence links, resolve the codebase root(s) for each codebase scanned:
- For a single codebase: Ask "Do you want to reference the codebase locally or in a GitHub (or other provider) repo?" Resolve and record one root.
- For multiple codebases: Resolve and record one root per codebase. Ask for each: local name or repo URL. Do not assume.
- **If remote:** Ask for the repo URL. Use blob URLs for evidence links.
- **If local:** Provide the path to the codebase root. Ask: "Is this path correct, or would you like to use a different codebase name?" Use the codebase name for evidence links.

Every requirement must cite at least one evidence location:
- Source file and line range
- Configuration file and key
- Test file that asserts the behavior
- Comment or docstring that documents the rule

**Format (after resolving root):**
- **Local:** `<codebase_root>/path/to/file.ext:123` (e.g., `web/src/auth/login.ts:45`)
- **Remote:** Full blob URL (e.g., `https://github.com/owner/repo/blob/main/path/to/file.ext#L123`)

See [references/evidence-and-traceability.md](references/evidence-and-traceability.md) for the full flow and citation patterns.

## Critical Ordering

- ALWAYS read mentioned files first before spawning sub-tasks (step 1)
- ALWAYS resolve codebase root(s) only when writing evidence links (step 7), not during discovery
- ALWAYS wait for all sub-agents to complete before synthesizing (step 5)
- ALWAYS gather metadata before writing the document (step 6 before step 7)
- ALWAYS filter the gathered evidences to avoid duplicates and unnecessary noise
- NEVER write the document with placeholder values
- NEVER include requirements without code evidence

## Important Notes

- Use parallel Task agents to maximize efficiency
- Run fresh codebase research; do not rely solely on existing docs
- Each sub-agent prompt must be specific and read-only
- If the user provides multiple codebases (monorepo, multi-repo), spawn sub-agents for each codebase concurrently and synthesize into one document
- Keep the main agent focused on synthesis and classification
- Focus on concrete file paths and line numbers
- Document only what exists; do not suggest changes

## Additional References

- [assets/requirements-scan-template.md](assets/requirements-scan-template.md) - Output template
- [references/requirements-classification.md](references/requirements-classification.md) - How to classify code as FR/NFR/BR
- [references/evidence-and-traceability.md](references/evidence-and-traceability.md) - Citation and traceability patterns
- [references/ears-for-code-derived-frs.md](references/ears-for-code-derived-frs.md) - EARS adaptation for code-derived FRs
- [examples/example-output.md](examples/example-output.md) - Example of expected output
