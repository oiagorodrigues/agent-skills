# Example: Codebase Requirements Output

This example shows the expected structure and granularity for a code-derived requirements specification.

---

## 1. Scope & Evidence Statement

### 1.1 What Was Scanned

- **Codebase root (resolved):** `my_repo` (local) — user confirmed path
- **Directories:** `src/`, `config/`, `tests/`
- **File types:** `.ts`, `.tsx`, `.json`, `*.config.ts`
- **Excluded:** `node_modules/`, `dist/`, `*.test.ts` (used as secondary evidence only)

### 1.2 Scope Summary

**In scope:**
- Authentication and authorization
- Order creation and cancellation
- Payment validation

**Out of scope:**
- Admin dashboard (not analyzed)
- Email sending implementation

### 1.3 Confidence Level

- **High:** Auth, order validation (strong code evidence)
- **Medium:** Payment flow (config present, some logic inferred)
- **Low:** Rate limiting (mentioned in comments, not fully traced)

---

## 2. Functional Requirements

### 2.1 Authentication

| ID | Requirement | Evidence |
|----|--------------|----------|
| FR-01 | WHEN the user submits credentials THE System shall validate email format and password length | `repo/src/auth/validate.ts:12-23` |
| FR-02 | IF the credentials are invalid THEN THE System shall return a 401 and not reveal whether email or password failed | `repo/src/auth/login.ts:45-52` |
| FR-03 | WHEN the user successfully authenticates THE System shall create a session with a JWT token | `repo/src/auth/login.ts:67-78` |

### 2.2 Order Management

| ID | Requirement | Evidence |
|----|--------------|----------|
| FR-04 | WHEN the user submits an order THE System shall validate cart contents and availability | `repo/src/orders/order.service.ts:34-56` |
| FR-05 | IF the order total exceeds the user's limit THEN THE System shall reject the order | `repo/src/orders/order.service.ts:89` |
| FR-06 | WHEN the user requests cancellation THE System shall check BR-01 before proceeding | `repo/src/orders/cancel.ts:12-18` |

---

## 3. Non-Functional Requirements

### 3.1 Security

| ID | Requirement | Evidence |
|----|--------------|----------|
| NFR-01 | Passwords must be hashed with bcrypt, cost factor >= 12 | `repo/config/security.ts:8` |
| NFR-02 | All API requests must use HTTPS; TLS 1.3 enforced | `repo/config/server.ts:15` |
| NFR-03 | JWT tokens shall expire after 24 hours | `repo/src/auth/jwt.ts:5` |

### 3.2 Performance

| ID | Requirement | Evidence |
|----|--------------|----------|
| NFR-04 | API responses must complete within 5 seconds (timeout) | `repo/config/axios.ts:12` |
| NFR-05 | Rate limit: 100 requests per minute per IP | `repo/src/middleware/rate-limit.ts:8` |

---

## 4. Business Rules

| ID | Rule | Evidence |
|----|------|----------|
| BR-01 | An order cannot be canceled more than 30 minutes after creation | `repo/src/orders/cancel.ts:22` |
| BR-02 | A user can have at most one active order in "pending" status | `repo/src/orders/order.service.ts:78` |
| BR-03 | Commission is calculated as 5% of the order total | `repo/src/orders/commission.ts:4` |

---

## 5. Traceability & Evidence

| Requirement ID | Type | Evidence Location | Notes |
|----------------|------|-------------------|-------|
| FR-01 | Functional | `repo/src/auth/validate.ts:12-23` | Email validation |
| FR-02 | Functional | `repo/src/auth/login.ts:45-52` | Generic error on invalid creds |
| FR-03 | Functional | `repo/src/auth/login.ts:67-78` | JWT creation |
| FR-04 | Functional | `repo/src/orders/order.service.ts:34-56` | Order validation |
| FR-05 | Functional | `repo/src/orders/order.service.ts:89` | Limit check |
| FR-06 | Functional | `repo/src/orders/cancel.ts:12-18` | Cancel flow |
| NFR-01 | Non-Functional | `repo/config/security.ts:8` | bcrypt |
| NFR-02 | Non-Functional | `repo/config/server.ts:15` | TLS |
| NFR-03 | Non-Functional | `repo/src/auth/jwt.ts:5` | Token expiry |
| NFR-04 | Non-Functional | `repo/config/axios.ts:12` | Timeout |
| NFR-05 | Non-Functional | `repo/src/middleware/rate-limit.ts:8` | Rate limit |
| BR-01 | Business Rule | `repo/src/orders/cancel.ts:22` | 30-min window |
| BR-02 | Business Rule | `repo/src/orders/order.service.ts:78` | Single pending |
| BR-03 | Business Rule | `repo/src/orders/commission.ts:4` | 5% commission |

---

## 6. Assumptions & Gaps

### 6.1 Assumptions

- Config values in `config/` reflect production or intended defaults
- JWT secret is set via environment (not in codebase)

### 6.2 Gaps

- Email sending: integration found but not fully traced
- Admin override for BR-01: mentioned in comments, not found in code

### 6.3 Areas Not Analyzed

- `src/admin/` (admin dashboard)
- `src/reports/` (reporting module)

---

## 7. Quality Checks

- **Completeness:** 75% - Core auth and orders covered; admin and reports not analyzed
- **Evidence coverage:** All listed requirements have at least one code evidence location
- **Status:** Draft
- **Missing evidence:** None for listed requirements
