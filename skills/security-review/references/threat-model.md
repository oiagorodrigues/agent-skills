# Threat model for a new surface

Adapted from openai/skills `security-threat-model` (Apache-2.0, https://github.com/openai/skills), cut down to fit inside a review.

Use it when a change adds an entry point. The output is one table in the report plus a list of review targets for step 3. Keep it to the new surface, not the whole system.

## Steps

1. Components and entry points. Name what the change adds and how it runs (HTTP endpoint, webhook, Celery task, CLI, Lambda, CI job, LLM tool), with `file:line`. Keep runtime code apart from CI, build and dev tooling, and from tests. Claim only components and controls you found in the code.
2. Assets. List what the surface can read, change or spend: company records (orders, prices, inventory, licenses), user PII, payment and bank details, credentials and tokens, sessions, AWS resources, CI secrets, paid API quota.
3. Trust boundaries. Write each one as an edge between components (browser to API, API to Celery through the broker, payment or webhook provider to API, service to AWS, GitHub Actions to AWS through OIDC, user content to LLM to tool). For each edge note authentication, authorization, input validation, encryption and rate limiting, with `file:line` or "not found".
4. Attackers. Describe what each realistic attacker can do (anonymous internet user, logged-in user of company A, staff or support user, fork PR author, author of a document or product description that an LLM reads) and what they can't (read server environment, push to protected branches). Non-capabilities keep severity honest.
5. Threats as abuse paths. Write each as attacker goal, path, asset ("buyer of company A changes `seller_id` in the order payload to read company B's prices"). Rate likelihood and impact low, medium or high with one reason each, and set priority from both, adjusted for controls that exist. Keep three to eight threats.
6. Assumptions. Name the assumptions that change the ranking (internet exposure, whether the surface is multi-company, data sensitivity). When one would move a threat by a whole priority level and the code can't settle it, ask the user one to three targeted questions before finishing. Otherwise state the assumption next to the threat.
7. Mitigations. For each threat, separate existing controls (with `file:line`) from recommended ones, and tie each recommendation to a location and a control type (permission class, scoped queryset, schema validation, signature check, rate limit, IAM condition). "Validate inputs" isn't a recommendation; "reject `seller_id` in `OrderCreateSerializer` and set it from the cart" is.

Done when every new entry point and every boundary from step 3 appears in at least one threat or is marked as covered by an existing control.

## Report table

```markdown
| # | Abuse path | Asset | Boundary | Likelihood | Impact | Priority | Existing control | Recommended |
|---|---|---|---|---|---|---|---|---|
| T1 | Buyer edits `seller_id` in the order payload to read another seller's prices | Seller price lists | Browser to API | Medium: field is in the request body | High: cross-company read | High | None found in `OrderCreateSerializer` | Make `seller_id` read-only, derive it from the cart (`orders/serializers.py:40`) |
```

Each high or medium threat becomes a review target in step 3. A threat with no control in the code is a candidate finding and goes through step 5 like any other.
