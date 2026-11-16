---
name: ai-engineering
description: Engineering rules for LLM features and agents, built around evals (error analysis on real traces, one binary check per failure mode, LLM judges validated against human labels, an eval set run on every prompt or model change), plus shape choice, tool design, output validation, call logging and RAG retrieval evals. Use when writing or changing a prompt, LLM call, agent, model-facing tool or RAG pipeline, when asked to write evals or an LLM judge or whether an AI feature is good enough, and when an AI feature gives wrong answers.
---

# AI engineering

How to build an LLM feature or agent that you can show works, and keep it working when the prompt, model or data changes. Built from Hamel Husain's evals FAQ, Chip Huyen's AI Engineering, Eugene Yan's LLM patterns and Anthropic's "Building effective agents" (links in `references/evals.md`, "Sources").

Model ids, parameters, pricing, structured output and tool-use API details change often. For Claude, read the `claude-api` skill; for other providers, read their current docs. Read the model id from the app's config and never write one from memory into code, prompts or docs.

## Workflow

Follow these steps for a new feature, and from step 3 for a change to an existing one.

1. Name the job and pick the shape. Write one sentence on what the feature returns and who or what acts on it, then pick the simplest shape under "Shape". Done when the design names the shape and, if it isn't a single call, the failure that rules out the simpler one.
2. Build the boundary in code: the prompt in a versioned file, the output validated against a schema, every call logged (sections below). Done when you can replay one call from its log row and get a validated result.
3. Read 30 to 100 real traces, or synthetic inputs when there is no traffic yet, and group the failures into named modes with counts. Follow `references/evals.md`, "Error analysis". Done when you have a table of failure modes, each with a count and one example trace id.
4. Write one binary pass/fail check per failure mode. Use code where a rule can catch it and an LLM judge only where it can't, and accept a judge only after it agrees with human labels on a held-out set. Done when every check has a pass rate on the eval set and every judge has its true positive and true negative rates written next to it.
5. Commit the eval set and its runner to the repo, and run it on every change to the prompt, model, parameters, retrieval or tools. Done when the PR shows the pass rate per check before and after the change.
6. After release, keep reading sampled logs and user signals. Done when each new failure you find is a case in the eval set, and a check if it's a new mode.

Fix the biggest failure mode first, and change one thing per eval run so you know which change moved the number.

## Shape

Use the simplest shape that passes the evals, in this order:

1. One LLM call, with retrieval or examples in the prompt when it needs knowledge.
2. A fixed workflow, where code decides the steps: a chain of calls, a router, parallel calls, or a generate-then-check loop.
3. An agent, where the model picks its next step and tool, only when the steps can't be known before the run.

Every loop, in a workflow or an agent, has a turn cap, a budget cap and a stop condition that code checks. For the workflow patterns and when each one fits, read `references/agent-shapes-and-tools.md`.

## Tools the model calls

Design each tool so the wrong call is hard to make: typed arguments, enums instead of free text, ids instead of names, absolute paths, one clear job per tool with no two tools that overlap. Errors tell the model what to do next ("order 123 not found; call search_orders with the buyer name first"). Test a tool by running sample tasks and reading where the model misuses it, then change the tool, not only its description. Details and a checklist are in `references/agent-shapes-and-tools.md`.

## Validate output at the boundary

Parse every model output into a typed object (Pydantic, Zod, a JSON schema) before any code uses it, even when the provider's structured output mode is on, since that guarantees shape and not that the values are allowed. On a failed parse or a value outside the allowed set, retry once with the validation error in the prompt, then take the non-AI path (a default, a queue for a person, an error the user sees). Unvalidated model text never reaches a database write, a query, a tool call, another prompt's instructions or rendered HTML.

## Log every call and version the prompt

- Keep each prompt in its own file in the repo, with a version id that changes with its content (a hash or an explicit version). A prompt change goes through a PR that shows the eval results.
- Log one row per model call: call id, feature, prompt version, model id, parameters, the inputs that filled the template, retrieved document ids, tool calls and results, raw output, validation result, latency, tokens and cost, and the user's reaction when there is one (accepted, edited, rejected). Redact PII and secrets the way the repo already does for other logs.
- Keep a replay script that re-runs a logged call with a different prompt version or model. Logged failures become eval cases through it.

## RAG

Evaluate retrieval on its own before tuning generation. Build a labeled set of queries with the ids of the chunks that answer them, measure recall@k at the k the prompt uses, and tune chunking, embeddings, filters and reranking against that number. Then check generation for answers grounded in the retrieved text and for saying it can't answer when the text isn't there. The method is in `references/evals.md`, "RAG evals".

## Other skills for the rest

- Cost, latency, token budgets, model and effort per stage, prompt caching: `cutting-agent-costs`.
- What an agent may do alone, approvals and human-in-the-loop: `agent-guardrails`.
- Prompt injection, tool authority and model output reaching sinks: `security-review`, whose LLM checks are in `~/.agents/skills/security-review/references/llm-and-agents.md`.
- Connecting a model to company systems (MCP servers, connectors, deployment): `ai-integration-architect`.
- Tuning a prompt or parameter automatically against a fixed eval: `autoresearch`.

## References

- `references/evals.md`: error analysis, code checks and LLM judges, judge validation, the eval set in the repo, RAG and agent evals, production signals and a worked example. Read it for steps 3 to 6 and for any request about evals or judges.
- `references/agent-shapes-and-tools.md`: the workflow patterns, when an agent is worth it, stop conditions and the tool design checklist. Read it when choosing a shape or writing tool definitions.
