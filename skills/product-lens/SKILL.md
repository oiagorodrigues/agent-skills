---
name: product-lens
description: Reads a proposed change (feature, bug fix, refactor, ticket, idea, branch or PR) the way a PO, PM, CTO, CEO and GTM team would. Traces what it touches beyond the edited code (the company's other repos, customer workflows, integrations, reporting, compliance, billing, support, sales), raises the questions those roles would ask, and pairs it with the build and rollout that fit. Use when the user runs /product-lens, asks for a product, business or GTM view of a change, asks "what does this affect", "who does this impact", "should we build this", "how does this fit the product", or wants a ticket or PR reviewed beyond the code. For a ticket or thread that reports a problem or asks a question (a bug, a customer or GTM question), use triage instead.
---

# Product lens

Look at one change with the eyes of everyone who will live with it: the customer, the PO who owns the workflow, the PM who owns the roadmap, the CTO who owns the system, the CEO who owns the business and the people who sell and support it. Then say how to build and ship it so it holds up.

Every lens answers the same question: are we delivering the right thing, with the right business outcome? A change that is well built but moves no outcome anyone needs is the wrong thing to build, and the output says so.

The value is in specifics. "This serializer is also read by the reporting ETL in another repo" or "customers on the free plan lose this export" helps. "Consider the impact on users" doesn't. A lens with nothing specific to say stays silent.

Workspace values (where local clones live, the GitHub org, a map of repos by area, the product's personas and regulatory rules, the prod data source) come from the workspace's own instructions; load the workspace skill for the repo first, when one exists, and read its "Values for product-lens" section and its repo routing.

## 1. Pin down the change

Read the source in full: the Jira ticket with comments and linked issues, the PR and its diff, the Slack thread, or the user's description. When the source is a PR, check that the ticket it tags matches its diff, using the "Checking whether a ticket or PR is related" check in the `jira-workflow` skill, and flag a mismatch instead of analyzing the wrong ticket. Then write down for yourself:

- The type: new feature, change to an existing feature, bug fix, refactor or tech debt, infra, data or reporting change.
- The change in one sentence: what changes, for whom, and why.
- The problem behind it. A request often names a solution ("add a CSV export") when the need is something else ("finance reconciles orders by hand every Friday"). Analyze the problem, and say so when the proposed solution doesn't fit it.
- What success looks like and how anyone would know: a metric, fewer tickets, a customer unblocked, a deal closed.
- The business outcome it should move (revenue, retention, cost, risk, support load, team time) and why that outcome matters now more than the other work it competes with. If the only benefit is technical (faster API, more automation throughput, a cleaner architecture), trace it to the outcome it changes or flag that it has none.

If you can't name the user, the problem and the success signal from what you have, stop after a quick look at the code and lead the output with questions (see section 6). Analysis built on guesses about intent is noise.

## 2. Map the blast radius

Find what the change touches, starting from the code it edits and working outward. Every claim cites a `repo/path:line`, a PR, a ticket or a data point.

1. Owner code: the model, view, serializer, component, task or event the change edits. Use `rg -n "<term>" --glob '!node_modules' --glob '!*.lock'` in the local clones (the workspace values say where they live), and `gh search code --owner <org> "<term>"` for repos that aren't cloned.
2. Consumers: who reads what changes. Look for other repos importing the model or calling the endpoint, events published from it, ETL and scheduled data jobs reading the table, integrations and webhooks sending it out, the frontend screens rendering it, emails and notifications built from it, permission rules guarding it and feature flags gating it. When the workspace values include a map of repos by area, start from it.
3. Contracts at the edges: public or partner API fields, event schemas, report columns, CSV exports, webhook payloads. These break customers and partners silently, so call out each one.
4. History: `git log` on the touched paths, related Jira tickets (`searchJiraIssuesUsingJql`) and Slack threads. Earlier attempts and complaints say more about the real need than the ticket does. Read each candidate in full and run the "Checking whether a ticket or PR is related" check in the `jira-workflow` skill before using it; a ticket that only shares keywords says nothing about the need.

When the sweep spans several repos, run parallel `Explore` agents, one per repo or area, each given the change, the search terms and what you've ruled out.

## 3. Get the facts that size it

Business weight comes from numbers, not adjectives. For each claim that drives the analysis, find the evidence or mark it as an assumption.

- Usage and reach: how many companies, users or orders go through this path. Load the `prod-evidence` skill for Datadog RUM, APM and logs, and the prod data source from the workspace values for business data when it's available. Report the number, the window and the query.
- Who: which customer types and plans are affected, and whether key accounts are among them.
- Pain: support tickets, Slack escalations, churn or deal notes mentioning it.

Never invent revenue, customer counts or adoption figures. "Unknown, ask Sales" is a valid answer and goes in the questions.

## 4. Read it through each lens

Go through every lens, but write up only the findings that name something specific. Each finding says what, who it affects, the evidence, and how much it matters (blocks it, should change it, or worth knowing).

**Customer and PO (workflow owner)**
- Which persona does the work: a customer role the product serves (the workspace values list them) or an internal CS or admin user. What job are they doing when they hit this?
- What changes in their day: a new step, a removed step, a moved button, different numbers in a report they already trust. Behavior changes to existing workflows hurt more than new features.
- Edge cases the ticket skips: permissions and roles, multi-company users, empty and error states, large accounts, state-specific rules, mobile, existing data that doesn't fit the new rule.
- Acceptance criteria that are missing or can't be tested.

**PM (product and roadmap)**
- Does it solve the problem from section 1, and is there a smaller version that solves most of it?
- Does it overlap with, contradict or block another product area or a planned initiative?
- Does it set a precedent: a pattern other teams will copy, or a promise customers will expect everywhere?
- How will we measure that it worked, and is that instrumentation part of the work?

**CTO (system and team)**
- Fit with the architecture the codebase already uses, or a new pattern, dependency or service. New things need a reason the existing ones can't cover.
- Reversibility: a flagged UI change is a two-way door. A schema change, a public API contract, a data backfill or a message to customers is one-way, and needs more care.
- Cost after launch: on-call load, new failure modes, data growth, query load on hot tables, manual ops steps.
- Security, privacy and compliance: the regulatory rules the product falls under (the workspace values name them), financial data, PII, audit trails.
- Ownership: which team owns each touched area, and whether another team needs to review or ship something first.

**CEO (business)**
- What it does for revenue, retention, cost or risk, in numbers when you have them.
- Whether a customer, a contract or a deal depends on it, and any deadline that comes with it.
- Whether it's worth what it costs against other work, judged by the facts gathered, not by the ticket's priority field.

**GTM (sales, CS, support, marketing)**
- Does anyone outside engineering need to know before it ships: CS for accounts whose workflow changes, Support for the questions it will bring, Sales for what they can now promise or must stop promising?
- Plan gating, pricing or packaging: who gets it, and whether that's decided.
- Help-center articles, release notes, in-app messaging, training.
- Rollout to key accounts first, or a customer communication for a behavior change.

## 5. Pair it with the engineering approach

Recommend how to build and ship it, grounded in what the touched code already does. Build on the patterns already in the repo before proposing new ones.

- The approach: where the logic belongs, which existing pattern, service or component to extend, and the design pattern only when it solves a problem this change has. Always include the do-less option (config, an existing feature, a manual step, not building it) when it's credible.
- Compatibility: expand and contract for schema and API changes, versioned or additive fields for events, exports and partner APIs, and backfills that can be rerun safely.
- Rollout: a feature flag, staged by company or plan, a dark launch for risky paths, and how to roll back.
- Observability: the metric or log that proves success (section 1) and the alert that catches failure.
- Tests that protect the contracts found in section 2, not only the edited function.

For a deeper design, point to the matching skill instead of redoing it: `backend-design:design` for a component, `backend-design:review-migration` for a migration, `system-design-skills:design` for a system, `perf-review` for speed questions.

## 6. Write the output

Load the `plain-writing` skill. Keep it short enough to read in two minutes. Detail goes in evidence links, not in prose. Use this shape and drop any section with nothing in it:

1. **The change**: one or two sentences, including the problem behind it, the business outcome it should move and the success signal. If the request's solution doesn't fit the problem, or the outcome doesn't justify the work, say so here.
2. **What it touches**: a list of affected products, repos, contracts and customer groups, each with its evidence (`repo/path:line`, PR, ticket, number with window and query).
3. **Findings**: the specific findings from section 4, most serious first, each tagged with its lens. Mark each one as verified or as an inference.
4. **Recommended approach**: the build and rollout from section 5 in a few lines, with the do-less option if there is one.
5. **Open questions**: ranked by how much the answer would change what gets built. Each names who should answer it (PO, PM, CS, Sales, Finance, eng lead of team X). Three to seven questions, not twenty. When the answers must come from someone else, offer to turn them into a questionnaire for that person with `to-questionnaire`.
6. **Decision needed**: one line on what has to be decided, and by whom, before work starts or continues. When the decision hinges on a technical trade-off, give the options in business terms (what each costs, risks and delivers, and when), with the recommendation, so the PO, PM or leadership can decide with the full picture.

When the input was too thin (section 1), lead with the open questions, add a short "What I found so far" from the code, and stop there.

## Rules

- Report only. Don't change code, tickets or anything else, and don't post anywhere. If findings deserve a ticket, offer to run the `jira-workflow` skill. If the user wants to turn the result into a pitch for stakeholders, hand off to `business-first-pitch`.
- Don't pad lenses. If the change is an internal refactor with no customer effect, say that in one line and spend the output on the CTO lens and the approach.
- Say plainly when the change is fine as specified, and why. Don't invent objections to look thorough.
