# Requirements document sections

## Contents

- [Structure of the Complete Requirements Document](#structure-of-the-complete-requirements-document)
  - [📌 1. Business Vision](#-1-business-vision)
  - [📌 2. Stakeholders](#-2-stakeholders)
  - [📌 3. User Types (Personas)](#-3-user-types-personas)
  - [📌 4. Business Processes](#-4-business-processes)
  - [📌 5. Functional Requirements](#-5-functional-requirements)
  - [📌 6. Non-Functional Requirements](#-6-non-functional-requirements)
  - [📌 7. Business Rules](#-7-business-rules)
  - [📌 8. Data Model (High Level)](#-8-data-model-high-level)
  - [📌 9. Integrations](#-9-integrations)
  - [📌 10. Risks and Assumptions](#-10-risks-and-assumptions)
  - [📌 11. Roadmap / Phases](#-11-roadmap--phases)
  - [📌 12. Architecture Decision Records (ADR)](#-12-architecture-decision-records-adr)
  - [📌 13. Traceability Matrix & Tags](#-13-traceability-matrix--tags)
  - [📌 14. Quality Gates & Score](#-14-quality-gates--score)

## Structure of the Complete Requirements Document

### 📌 1. Business Vision

Include:

- **Problem solved** - What pain or need does it address?
- **Value proposition** - Why is it better than alternatives?
- **Business objective** - Clear and measurable goals
- **Main KPIs** - Success metrics
- **Scope** - What IS and what is NOT included

**Format example:**

```markdown
## Business Vision

### Problem

[Description of the problem being solved]

### Value Proposition

[What makes this product/service unique]

### Objectives

- Objective 1: [Description]
- Objective 2: [Description]

### KPIs

- KPI 1: [Specific metric]
- KPI 2: [Specific metric]

### Scope

**Includes:**

- [Element 1]
- [Element 2]

**Does not include:**

- [Element 1]
- [Element 2]
```

### 📌 2. Stakeholders

Identify all involved actors:

- **Business owners** - Who makes decisions
- **End users** - Who will use the system
- **Administrators** - Who will manage the system
- **Suppliers** - External services or products
- **Third parties** - Payments, logistics, integrations, etc.

**Suggested format:**

```markdown
## Stakeholders

| Type  | Name/Role | Interest          | Influence         |
| ----- | --------- | ----------------- | ----------------- |
| Owner | [Name]    | [High/Medium/Low] | [High/Medium/Low] |
| User  | [Type]    | [High/Medium/Low] | [High/Medium/Low] |
```

### 📌 3. User Types (Personas)

For each user type, document:

- **What they need** - Key functionalities
- **What pain they have** - Current problems
- **What they expect from the system** - Expectations

**Example:**

```markdown
## Personas

### End Customer

- **Needs:** Make fast and secure purchases
- **Pain:** Complicated checkout processes
- **Expectation:** Checkout in less than 3 clicks

### Administrator

- **Needs:** Manage inventory and orders
- **Pain:** Lack of real-time visibility
- **Expectation:** Dashboard with updated metrics
```

### 📌 4. Business Processes

**⚠️ VERY IMPORTANT - This is where many fail.**

Document complete flows:

- How a customer enters
- How a sale is generated
- How payment is collected
- What happens if the payment fails
- How a claim is handled

**Express as step-by-step flows:**

```markdown
## Process: Product Purchase

1. User browses catalog
2. User adds products to cart
3. User proceeds to checkout
4. System validates availability
5. User enters payment details
6. System processes payment
   - **If success:** Confirms order and sends email
   - **If failure:** Shows error and allows retry
7. System generates shipping order
8. User receives confirmation
```

For complex processes, see [references/process-mapping.md](process-mapping.md).

### 📌 5. Functional Requirements

Standard format:

- **FR-01:** The system must allow...
- **FR-02:** The user will be able to...

**Common categories:**

- User registration
- Order management
- Payments
- Notifications
- Reports

**Example:**

```markdown
## Functional Requirements

### Authentication

- **FR-01:** The system must allow registration with email and password
- **FR-02:** The system must send a verification email
- **FR-03:** The user will be able to recover a forgotten password

### Order Management

- **FR-04:** The user will be able to view order history
- **FR-05:** The system must allow canceling orders in "pending" status
```

### 📌 6. Non-Functional Requirements

**This separates the amateur from the professional.**

Key areas:

- **Security** - Authentication, authorization, encryption
- **Performance** - Response times, capacity
- **Scalability** - Expected growth
- **Availability** - Uptime, redundancy
- **Legal compliance** - GDPR, data protection
- **UX / Usability** - Accessibility, responsive

**Example:**

```markdown
## Non-Functional Requirements

### Performance

- **NFR-01:** The system must respond in < 2 seconds for 95% of requests
- **NFR-02:** The system must support 1000 concurrent users

### Security

- **NFR-03:** All passwords must be hashed with bcrypt
- **NFR-04:** Communications must use HTTPS/TLS 1.3

### Compliance

- **NFR-05:** The system must comply with GDPR for European user data
```

### 📌 7. Business Rules

Domain-specific logic:

**Examples:**

```markdown
## Business Rules

- **BR-01:** An order cannot be canceled after 30 minutes of creation
- **BR-02:** A user can only have one active plan at a time
- **BR-03:** Commissions are calculated as 5% of the total amount
- **BR-04:** Taxes are applied according to the buyer's region
```

### 📌 8. Data Model (High Level)

**Conceptual, not SQL yet.**

Document:

- **Primary entities** - User, Order, Product, etc.
- **Relationships** - One to many, many to many
- **Critical data** - Essential fields

**Example:**

```markdown
## Data Model

### Primary Entities

**User**

- id (PK)
- email (unique)
- name
- registration_date

**Order**

- id (PK)
- user_id (FK)
- status
- total
- creation_date

**Product**

- id (PK)
- name
- price
- stock

### Relationships

- A User can have many Orders (1:N)
- An Order can contain many Products (N:M)
```

For complex models, see [references/data-modeling.md](data-modeling.md).

### 📌 9. Integrations

Necessary external services:

- **Payment gateways** - Stripe, PayPal, etc.
- **External APIs** - Third-party services
- **Third-party services** - Email, SMS, analytics

**Example:**

```markdown
## Integrations

### Payment Gateway

- **Provider:** Stripe
- **Functionality:** Credit card processing
- **Data exchanged:** Amount, currency, card token

### Email Service

- **Provider:** SendGrid
- **Functionality:** Sending notifications
- **Data exchanged:** Recipient, subject, HTML body
```

### 📌 10. Risks and Assumptions

Identify potential problems:

- **Technical risks** - Dependencies, scalability
- **Legal risks** - Compliance, privacy
- **Business assumptions** - Assumptions that must be validated

**Example:**

```markdown
## Risks

### Technical

- **R-01:** Dependency on external API may cause downtime
  - _Mitigation:_ Implement caching and fallback system

### Legal

- **R-02:** Changes in data protection regulation
  - _Mitigation:_ Modular design for rapid adaptation

## Assumptions

- **S-01:** Users have stable internet access
- **S-02:** Initial volume will not exceed 10,000 users
```

### 📌 11. Roadmap / Phases

Divide into manageable stages:

**Example:**

```markdown
## Roadmap

### MVP (Phase 1) - 3 months

- Registration and authentication
- Product catalog
- Shopping cart
- Basic payment with Stripe

### Phase 2 - 2 months

- Notifications system
- Order history
- Basic administration panel

### Phase 3 - 3 months

- Advanced reports
- Logistics integration
- Recommendations system
```

### 📌 12. Architecture Decision Records (ADR)

Document critical technical decisions to preserve context.

**Example:**

- **ADR-001:** Use PostgreSQL for relational data integrity.
- **ADR-002:** Implement Redis for real-time notification caching.

See [references/adr-template.md](adr-template.md) for details.

### 📌 13. Traceability Matrix & Tags

Embed cumulative tags to bridge the gap between requirements and implementation.

**Format:** `@brd: BRD.01.01 @req: REQ-001`

See [references/traceability-guide.md](traceability-guide.md).

### 📌 14. Quality Gates & Score

Evaluate the maturity of the documentation before proceeding.

- **Maturity Level:** [0-100%]
- **Status:** [Draft | Ready for Dev | Approved]
- **Missing Items:** List of gaps to be filled.
