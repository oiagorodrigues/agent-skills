# Codebase Requirements Specification

**Version:** 1.0
**Date:** [YYYY-MM-DD]
**Codebase(s):** [Single: local name or repo URL. Multiple: list each resolved root, e.g., `repo_a`, `repo_b` or URLs]
**Status:** [Draft | Under Review | Approved]

---

## 1. Scope & Evidence Statement

### 1.1 What Was Scanned

- **Codebase(s) (resolved):** [Single: one root. Multiple: list each codebase and its root, e.g., `repo_a` (local), `repo_b` (https://github.com/owner/repo_b)]
- **Directories:** [List main directories analyzed]
- **File types:** [e.g., .ts, .py, config files, tests]
- **Excluded:** [Paths or patterns excluded from scan]

### 1.2 Scope Summary

**In scope:**
- [Area 1]
- [Area 2]

**Out of scope:**
- [What was not analyzed]

### 1.3 Confidence Level

- **High:** [Areas with strong evidence]
- **Medium:** [Areas with partial evidence]
- **Low:** [Areas with weak or inferred evidence]

---

## 2. Functional Requirements

### 2.1 [Module/Area Name]

| ID | Requirement | Evidence |
|----|--------------|----------|
| FR-01 | [EARS-style description] | `repo/src/auth/login.ts:123` |
| FR-02 | [EARS-style description] | `repo/src/orders/service.ts:45-67` |

### 2.2 [Another Module]

| ID | Requirement | Evidence |
|----|--------------|----------|
| FR-03 | ... | ... |

---

## 3. Non-Functional Requirements

### 3.1 Security

| ID | Requirement | Evidence |
|----|--------------|----------|
| NFR-01 | [Specific, measurable] | `repo/config/security.ts:8` |

### 3.2 Performance

| ID | Requirement | Evidence |
|----|--------------|----------|
| NFR-02 | ... | ... |

### 3.3 [Other NFR Categories]

Availability, Compliance, Usability, Maintainability as applicable.

---

## 4. Business Rules

| ID | Rule | Evidence |
|----|------|----------|
| BR-01 | [Domain constraint or logic] | `repo/src/orders/cancel.ts:22` |
| BR-02 | ... | ... |

---

## 5. Traceability & Evidence

| Requirement ID | Type | Evidence Location | Notes |
|----------------|------|-------------------|-------|
| FR-01 | Functional | `repo/src/auth/login.ts:45-67` | Email validation |
| NFR-01 | Non-Functional | `repo/config/security.ts:12` | bcrypt cost factor |
| BR-01 | Business Rule | `repo/src/services/order.ts:89` | Cancel window |

---

## 6. Assumptions & Gaps

### 6.1 Assumptions

- [Assumption 1: e.g., "Config values in env reflect production"]
- [Assumption 2]

### 6.2 Gaps

- [Area not covered or insufficient evidence]
- [Potential requirement not found in code]

### 6.3 Areas Not Analyzed

- [Directories or files not scanned]

---

## 7. Quality Checks

- **Completeness:** [0-100%] - [Brief assessment]
- **Evidence coverage:** [All / Most / Partial] requirements have code evidence
- **Status:** [Draft | Ready for Review | Approved]
- **Missing evidence:** [List requirement IDs without evidence, if any]
