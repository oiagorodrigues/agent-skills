---
name: business-requirements-analyst
description: Complete methodology for software and business requirements gathering. Use when you need to document a new project, validate a business idea, create technical specifications, or generate complete documentation covering business vision, stakeholders, processes, functional and non-functional requirements, data model, integrations, risks, and roadmap. Ideal for projects requiring quoting, development, delegation, or presentation to investors.
license: MIT
metadata:
  author: github.com/gmdaos
  version: '2.0.0'
---

# Requirements Gathering

This Skill provides a professional and complete methodology for conducting requirements gathering that covers all business layers, not just "the app" or "the system."

## Fundamental Principle

**Requirements gathering is NOT just a list of functionalities.**

Good requirements gathering covers all business layers:

- 🧠 Idea and objective
- 👥 Users
- 💼 Operation
- 💰 Money
- ⚙️ Technology
- ⚠️ Risks
- 📈 Growth
- 🔗 **Traceability** (from Business to Code)
- ⚖️ **Quality Gates** (Validation standards)

## Available Methodologies

### 1. Design Thinking (for new ideas)

**Ideal when:**

- The idea is still being validated
- Not everything is clear
- You want to truly understand the user

**Phases:**

1. **Empathize** - Understand users
2. **Define** - Identify key problems
3. **Ideate** - Generate solutions
4. **Prototype** - Create early versions
5. **Test** - Validate with real users

**Note:** Used to discover what to build, not to document everything.

### 2. Business Analysis (BABOK)

**The most complete and professional.**

**Covers:**

- Business requirements
- Functional requirements
- Non-functional requirements
- Business rules
- Stakeholders
- Processes

**Note:** This is what's used to create formal documents.

### 3. Lean / Startup Canvas (quick vision)

**Useful for:**

- Organizing the idea
- Seeing if the business makes sense

**⚠️ Important:** DOES NOT replace complete requirements gathering.

## Recommended Approach

Combine 3 key elements:

1. **Business vision**
2. **Processes**
3. **System / product**
4. **Traceability & Validation** (Ensure everything is connected and meets quality standards)

And document everything in a **single master artifact** or a structured layer system.

## Structure of the Complete Requirements Document

The document has 14 sections: 1. Business Vision, 2. Stakeholders, 3. User Types (Personas), 4. Business Processes, 5. Functional Requirements, 6. Non-Functional Requirements, 7. Business Rules, 8. Data Model (High Level), 9. Integrations, 10. Risks and Assumptions, 11. Roadmap / Phases, 12. Architecture Decision Records (ADR), 13. Traceability Matrix & Tags, 14. Quality Gates & Score.

Before drafting or reviewing any section, read [references/document-sections.md](references/document-sections.md). It gives what each section must include, its ID format (FR-01, NFR-01, BR-01, R-01, S-01, ADR-001) and a Markdown example.

## Gathering Process (Step by Step)

### 0. Process Kickoff & Roadmap

**Instruction:** At the very beginning of the interaction, you MUST:

1.  **Introduce yourself:** Briefly explain you are a Business Requirements Analyst using a professional methodology.
2.  **Present the Roadmap:** Explain the 6 phases you will follow (Discovery → Vision → Processes → Functional/Non-Functional → Data Model → Roadmap) so the user knows what to expect.
3.  **Acknowledge Documentation:** If the user has provided files or previous context, state that you will analyze them first to avoid asking for information already provided.

### 1. Discovery & Context Analysis (Smart Discovery)

**Instruction:**

- **Analyze First:** Before asking any questions, scan all provided files (images, text, documents).
- **Find Gaps:** Extract all possible information (Stakeholders, Problem, Goals) from the context.
- **Zero Redundancy Rule:** Never ask "What is the problem?" if it's already in the documents. Instead, validate: "I've analyzed the documents and understood the problem as [X]. Is that correct?".

### 2. Interviews & Deep Dive

**Instruction:** Focus only on the gaps. **Even if you are the stakeholder yourself**, perform the exercise of answering:

- What problem does this solve?
- Who will use it?
- How will they use it?
- What alternatives exist?
- Why is this better?

### 2. Uncomfortable Questions

**Fundamental for discovering edge cases:**

- What happens if the payment fails?
- What happens if the user loses connection?
- What happens if there is duplicate data?
- What happens if the external service is down?

### 3. Diagram Flows

Create visual diagrams of:

- User flows
- Business processes
- System architecture

### 4. Write → Validate → Adjust

**Iterative process:**

1. Write the first version of the document
2. Review with stakeholders
3. Identify gaps and ambiguities
4. Adjust and refine
5. Repeat until consensus is reached

### 5. Entity & Data Model Synthesis (Auto-ERD)

**Instruction:**

- **Active Extraction:** Throughout the entire process, identify all key entities mentioned (e.g., Orders, Users, inventory items).
- **Auto-Generation:** At the end of the analysis, if entities were detected, generate the Data Model section automatically.
- **Visual Diagram:** You MUST include a visual Entity-Relationship Diagram using **Mermaid.js** syntax for better clarity.

### 6. Living Document

**Keep it updated:**

- Use Markdown format for versioning
- Tools: Notion, Confluence, GitHub Wiki
- Update when requirements change

## Complete Template

For a ready-to-use template, see [assets/requirements-template.md](assets/requirements-template.md).

## Final Result

When you finish the complete gathering, you have:

- ✅ **Document for development** - Clear specifications
- ✅ **Basis for quoting** - Defined scope
- ✅ **Guide for delegating** - Complete instructions
- ✅ **Material to present** - To partners or investors

## Important Tips

1. **Don't start by writing requirements** - Start by understanding the business as if it already existed
2. **Be specific** - "Fast" is not a requirement, "< 2 seconds" is
3. **Include the "why"** - Not just the "what," but the reason behind it
4. **Document decisions** - Why a certain technology or approach was chosen
5. **Keep updated** - An outdated document is worse than no document at all

## Additional References

For advanced techniques and specific examples:

- **Complex process mapping:** [references/process-mapping.md](references/process-mapping.md)
- **Advanced data modeling:** [references/data-modeling.md](references/data-modeling.md)
- **Detailed use cases:** [references/use-cases.md](references/use-cases.md)
- **EARS Methodology:** [references/ears-methodology.md](references/ears-methodology.md)
- **ADR Templates:** [references/adr-template.md](references/adr-template.md)
- **Traceability Guide:** [references/traceability-guide.md](references/traceability-guide.md)
