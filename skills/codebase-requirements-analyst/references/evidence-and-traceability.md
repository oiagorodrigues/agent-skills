# Evidence and Traceability

How to cite code evidence and maintain traceability for code-derived requirements.

## Resolve Codebase Root (For Evidence and Traceability Only)

**Do not assume the codebase root.** Apply this only when generating the output document and writing evidence links—not during discovery or extraction.

**For a single codebase:** Ask the user:
> "Do you want to reference the codebase locally or in a GitHub (or other provider) repo?"

**For multiple codebases:** Resolve one root per codebase. For each codebase scanned, ask for its local name or repo URL. Do not assume.

**If the user wants remote (GitHub or other provider):**
- Ask: "Please provide the correct codebase URL (e.g., `https://github.com/owner/repo` or `https://gitlab.com/owner/repo`)."
- Use the provider's blob URL format for evidence links (see Citation Format below).

**If the user wants local:**
- Provide the path to the codebase root (e.g., `/Users/me/projects/repo` or `applications/repo`).
- Ask: "Is this path correct, or would you like to use a different codebase name/path?"
- Use the codebase name as the root prefix for evidence links.

**Record the resolved root(s)** in the output document's "Scope & Evidence Statement" so all evidence links are consistent. For multiple codebases, each requirement's evidence must use the correct root for that codebase.

## Citation Format

Evidence links must be **clickable or navigable**—either relative to a named codebase root or a full URL to the provider.

**Format A – Local (codebase name):**
```
<codebase_root>/path/to/file.ext:line
<codebase_root>/path/to/file.ext:start-end
```

Where `<codebase_root>` is the user-provided name.

**Examples:**
- `repo_1/src/auth/login.ts:45`
- `repo_2/src/orders/order.service.ts:89-123`
- `repo_3/config/security.ts:12`

**Format B – Remote (GitHub, GitLab, etc.):**
```
https://github.com/owner/repo/blob/main/path/to/file.ext#L123
https://github.com/owner/repo/blob/main/path/to/file.ext#L45-L67
```

**Provider-specific formats:**
- **GitHub:** `https://github.com/owner/repo/blob/<branch>/path/to/file.ext#L123` (single line) or `#L45-L67` (range)
- **GitLab:** `https://gitlab.com/owner/repo/-/blob/<branch>/path/to/file.ext#L123`
- **Bitbucket:** `https://bitbucket.org/owner/repo/src/<branch>/path/to/file.ext#lines-123`

Use the format the user provides when they give the repo URL.

## What Counts as Evidence

| Evidence type | Example (local) | Example (remote) | Usage |
|---------------|-----------------|-----------------|-------|
| Source code | `repo/src/services/order.ts:45` | `https://github.com/.../order.ts#L45` | Implementation of behavior or rule |
| Config file | `repo/config/cors.ts:8` | `https://github.com/.../cors.ts#L8` | NFR (security, limits, etc.) |
| Test file | `repo/tests/order.test.ts:23` | `https://github.com/.../order.test.ts#L23` | Asserts the requirement; secondary evidence |
| Schema/migration | `repo/schema/orders.sql:12` | `https://github.com/.../orders.sql#L12` | Data constraints as BR |
| Environment | `repo/.env.example` | `https://github.com/.../.env.example` | Runtime config; cite with caution |
| Comment/docstring | `repo/src/services/order.ts:42-44` | `https://github.com/.../order.ts#L42-L44` | Documents intent; use with code |

**Primary evidence:** The code that implements or enforces the requirement.  
**Secondary evidence:** Tests that assert it; comments that document it.

## Traceability Table

| Requirement ID | Type | Evidence Location | Notes |
|----------------|------|-------------------|-------|
| FR-01 | Functional | `repo/src/auth/login.ts:45-67` | Email validation |
| FR-01 | Functional | `repo/tests/auth.test.ts:23` | Test asserts validation |
| NFR-01 | Non-Functional | `repo/config/security.ts:12` | bcrypt cost factor |
| BR-01 | Business Rule | `repo/src/services/order.ts:89` | 30-minute cancel window |

**Rules:**
- Every requirement must have at least one primary evidence location
- All evidence locations must use the resolved codebase root (local name or full URL) for that codebase
- For multiple codebases: use the correct root per codebase (e.g., `repo_a/...` vs `repo_b/...`)
- Multiple locations per requirement are allowed (e.g., handler + validation)

## ID Stability

- Once assigned, do not change requirement IDs
- If a requirement is removed or invalidated, mark as `DEPRECATED` instead of deleting
- Use sequential numbering: FR-01, FR-02, NFR-01, NFR-02, BR-01, BR-02

## Gaps and Missing Evidence

If a requirement is inferred but no direct code evidence exists:
- Do not include it as a requirement
- Document it in "Assumptions & Gaps" as a potential gap

## Cross-Reference in Code

When the codebase already contains requirement tags (e.g., `@req: REQ-001`):
- Use those IDs if consistent
- Add evidence locations to the traceability table using the resolved root format
- If no tags exist, assign new IDs (FR-xx, NFR-xx, BR-xx)
