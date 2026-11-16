# Requirements Classification Guide

How to classify code evidence as Functional Requirements (FR), Non-Functional Requirements (NFR), or Business Rules (BR).

## Functional Requirements

**Definition:** User- or system-visible behaviors implemented by the codebase.

**Where to look:**
- API routes, endpoints, handlers
- Service methods, use cases, workflows
- UI components and event handlers
- Validation logic that blocks or allows actions
- Integration flows (e.g., external API calls)

**Heuristics:**
- If it changes system state or user-visible output → FR
- If it's triggered by user action or system event → FR
- If a test asserts "when X, then Y" → FR

**Examples:**
- `POST /orders` creates an order → FR
- `validateEmail()` rejects invalid format → FR
- `sendConfirmationEmail()` after payment → FR

**Edge cases:**
- Internal helper with no user/system impact → Not FR (unless it's a critical step in a flow)
- Config that enables a feature → Often NFR; the feature behavior is FR

## Non-Functional Requirements

**Definition:** Measurable or enforceable quality attributes visible in code or configuration.

**Where to look:**
- Security config (auth, encryption, CORS, CSP)
- Performance config (timeouts, limits, caching)
- Rate limits, throttling
- Logging, monitoring, health checks
- Test coverage thresholds
- Linting/formatting rules
- Accessibility attributes (aria-*, roles)
- Browser support config

**Heuristics:**
- If it constrains behavior without changing what the system does → NFR
- If it's a number, threshold, or policy (e.g., "must be < 2s") → NFR
- If it's about how the system is built or deployed → NFR

**Examples:**
- `bcrypt cost factor 12` → NFR (Security)
- `timeout: 5000` → NFR (Performance)
- `coverage: 80%` in jest config → NFR (Maintainability)
- `CORS allowedOrigins` → NFR (Security)

**Edge cases:**
- Business logic (e.g., "max 10 items per order") → BR, not NFR
- Feature flags → Often NFR (availability) or config for FR

## Business Rules

**Definition:** Domain constraints, calculations, eligibility rules, state transitions, thresholds, timing windows, or policy logic.

**Where to look:**
- Validation rules (e.g., "email must be unique")
- Domain services, calculators
- State machines, status transitions
- Permission/authorization logic
- Pricing, tax, discount rules
- Eligibility checks (e.g., "user must have active subscription")

**Heuristics:**
- If it encodes business policy or domain logic → BR
- If it's a constraint that could change without code refactor (e.g., "30 minutes") → BR
- If it's a calculation or formula → BR

**Examples:**
- "Order can be canceled only within 30 minutes" → BR
- "Commission is 5% of total" → BR
- "User can have only one active plan" → BR
- "Status transitions: pending → paid → shipped" → BR

**Edge cases:**
- Technical validation (e.g., "password must be 8+ chars") → Could be NFR (security) or BR (policy)
- Prefer BR if it's a business rule; NFR if it's a security/compliance standard

## Decision Flow

```
Is it behavior or quality?
  → Behavior (what the system does) → FR
  → Quality (how it does it) → NFR or BR

Is it domain logic or technical constraint?
  → Domain logic, policy, calculation → BR
  → Technical (security, performance, availability) → NFR
```

## When in Doubt

- Prefer FR over BR if the behavior is clearly user/system-triggered
- Prefer BR over NFR if it's business policy (e.g., "max 10 items")
- Prefer NFR over BR if it's a technical standard (e.g., "use HTTPS")
- If a single code block supports multiple requirements, split into FR + BR or FR + NFR as appropriate
