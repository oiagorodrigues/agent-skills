---
name: agent-guardrails
description: Defines and checks what an AI agent may do on its own, when a person must approve or take over, and whether the runtime settings and traces match that policy. Produces an action and data boundary matrix with owners, an approval control review for Claude Code, Codex, the Claude and OpenAI Agents SDKs, LangGraph and MCP, and allowed, blocked or escalated path findings from traces. Works from pasted tool lists, workflows, policies, configs, logs, transcripts and authorized files, and only returns reviewable text. Use when the user asks which tools an agent should have, what it can do without approval, who approves an action, how to make an agent ask before sending, where human-in-the-loop belongs, to review agent permission settings, or whether an agent acted before approval or after a rejection. Not for repairing MCP connections, scoring answer accuracy or general code security scanning.
---

# Agent guardrails

Ported from the `agent-guardrails` plugin by Sergey Skripko (MIT, see `LICENSE`). All paths below are relative to `~/.agents/skills/agent-guardrails/`. Each topic reviews an agent the user describes; it never changes settings, runs tools against the user's application or takes external actions.

## How to use

Match the question to one topic below and read only that topic's `README.md`. Each topic has its own procedure, deliverable and worked example, and links to `references/official-sources.md` for the dated official sources behind its control map.

Examples:

- "Here are our support agent's tools and policy. What can it do without me, and who approves refunds?": read `topics/agent-authority-map/README.md` and return the action matrix.
- "This LangGraph log shows `send_notice` ran twice after the approval interrupt. Did the gate work?": read `topics/agent-boundaries-check/README.md` and return path findings.

## Topics

- Action scope or approval ownership is undefined ("which tools should it have?", "what can it do without me?", "who approves these actions?"): `topics/agent-authority-map/README.md`.
- Designing approval points or reviewing proposed or effective runtime settings ("make it ask before sending", "review these permission settings", "where should human in the loop go?"): `topics/agent-controls-review/README.md`.
- Whether an observed action respected policy, even when configs come with the trace ("did it act before approval?", "was this denied tool really blocked?", "did the human handoff work?"): `topics/agent-boundaries-check/README.md`.

When a question spans two, start with the topic that answers the main question; each topic's "Routing" section says when to hand over to another.

## Source refresh

The topics fetch nothing by default. Only when the user asks for a source refresh, fetch the exact public official-documentation URLs the user supplies (plus robots.txt and redirects to official hosts) with the web tool, follow no other links, run no search and send no workflow contents in requests.
