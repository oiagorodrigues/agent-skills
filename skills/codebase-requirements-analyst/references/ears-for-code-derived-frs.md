# EARS for Code-Derived Functional Requirements

Adapt EARS (Easy Approach to Requirements Syntax) when writing functional requirements extracted from code.

## Why EARS for Code-Derived FRs

- **Eliminates ambiguity:** Avoids vague terms like "handles," "manages," "processes"
- **Standardization:** Every FR follows a predictable structure
- **AI-friendly:** Structured syntax is easier for models to parse and validate

## The 5 Patterns

| Pattern | Keyword | Formula | Use when |
|---------|---------|---------|----------|
| Ubiquitous | (Always) | The [System] shall [response] | Always-true behavior |
| Event-Driven | WHEN | WHEN [trigger] THE [System] shall [response] | Triggered by event |
| State-Driven | WHILE | WHILE [state] THE [System] shall [response] | System in specific state |
| Unwanted | IF | IF [condition] THEN THE [System] shall [response] | Error or edge case |
| Optional | WHERE | WHERE [feature] THE [System] shall [response] | Conditional feature |

## Examples

**From code:** `if (user.role === 'admin') { allowCancel(); }`

**EARS:** WHEN the user is an administrator THE System shall allow order cancellation regardless of status.

---

**From code:** `if (payment.failed) { showError(); }`

**EARS:** IF the payment fails THEN THE System shall display an error message and allow retry.

---

**From code:** `while (order.status === 'pending') { checkInventory(); }`

**EARS:** WHILE the order is pending THE System shall validate inventory availability.

---

**From code:** `validateEmail(email)` rejects invalid format

**EARS:** IF the user enters an invalid email format THEN THE System shall reject the input and display a validation error.

## Best Practices

1. **One "shall" per requirement** - Split if multiple behaviors
2. **Be specific** - "The Order Service" not "The system" when the component is known
3. **Avoid conjunctions** - No "and," "or," "also" in the response part
4. **Match code intent** - The EARS statement should reflect what the code does, not what it might do

## When EARS Doesn't Fit

- **Complex flows:** Use a single EARS statement for the main behavior; document details in notes
- **Business rules:** Often better as BR with plain language (e.g., "BR-01: An order cannot be canceled after 30 minutes")
- **NFRs:** Use measurable language (e.g., "NFR-01: Passwords must be hashed with bcrypt, cost factor >= 12")

## Cheat Sheet

```
Ubiquitous:  The [S] shall [R]
Event:       WHEN [T] THE [S] shall [R]
State:       WHILE [ST] THE [S] shall [R]
Unwanted:    IF [U] THEN THE [S] shall [R]
Optional:    WHERE [F] THE [S] shall [R]
```
