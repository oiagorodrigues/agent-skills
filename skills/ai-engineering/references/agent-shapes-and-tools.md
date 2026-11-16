# Agent shapes and tools

From Anthropic's "Building effective agents" (https://www.anthropic.com/engineering/building-effective-agents), including its appendix on prompt engineering tools.

## Pick the shape

A workflow is code that calls the model in fixed steps. An agent is a loop where the model picks its next tool call until it decides it's done. Workflows are cheaper, faster and easier to evaluate, so start there and move to an agent only when an eval shows the workflow can't handle the task.

| Pattern | What code does | Fits when |
|---|---|---|
| Single call | One prompt, with retrieved context or examples | The task is one step; most features start here |
| Prompt chain | Runs calls in sequence, each on the last one's output, with a code check between steps | The task splits into fixed subtasks, such as draft, then translate |
| Router | One call classifies the input, code sends it to a specialized prompt, model or non-AI handler | Inputs fall into kinds that need different handling, such as refund questions versus how-to questions |
| Parallel calls | Splits the task into independent parts (sectioning), or runs the same task several times and combines the answers (voting) | Parts don't depend on each other, or one answer isn't reliable enough |
| Orchestrator and workers | One call plans the subtasks at run time, worker calls do them, code collects the results | The subtasks depend on the input and can't be listed in advance |
| Generate and check | One call drafts, a second call or a code check reviews it against criteria, loop until it passes or hits the cap | The criteria are clear and a review measurably improves the result |
| Agent | The model calls tools in a loop, reads each result and decides the next step | The number and order of steps can't be known up front, and the environment returns a result after each step |

For an agent:

- Code enforces the stop: a maximum number of turns, a token or dollar budget, a wall-clock limit, and a check that the goal state was reached. The model saying it's done isn't enough.
- Give the model real results from the environment at each step (the test output, the API response), not its own guess about them.
- Put a human checkpoint before actions that are hard to undo; `agent-guardrails` decides which actions those are.
- Start without a framework, calling the model API directly. A framework hides the prompts and responses you need to read during error analysis; adopt one only when you can read what it sends.

## Design tools for the model

Treat the tool interface like a public API for a junior developer who reads only the docs. Anthropic reports spending more time on tools than on the prompt for its coding agent, and fixing its model's mistakes with relative paths by making the tool require absolute paths.

Checklist for each tool:

- [ ] The name and description say what it does, when to use it instead of the neighboring tools, and what it returns. Include one example call.
- [ ] Arguments are typed. Fixed sets are enums, records are referenced by id, paths are absolute, dates use one format, and every argument has a description.
- [ ] Mistakes are hard to make: no free-text argument where an enum works, no two tools that do almost the same thing, no argument whose meaning depends on another.
- [ ] Errors say what went wrong and what to do next, in words the model can act on ("buyer_id must be an integer; use search_buyers to find it"), and never a bare stack trace.
- [ ] Results are short and in a format the model reads easily: only the fields the task needs, paginated, with ids it can pass to the next tool. Formats that make the model count lines or escape text in JSON cause errors.
- [ ] Side effects are idempotent (an idempotency key or a natural key), so a retried call doesn't act twice.
- [ ] The handler checks the requesting user's permission on the exact resource in the arguments, since a schema checks shape and not authority (`~/.agents/skills/security-review/references/llm-and-agents.md`).
- [ ] The tool was tried on sample tasks, and the transcripts were read for wrong tool choices, bad arguments and repeated calls. Each mistake led to a change in the tool itself where possible, and in its description otherwise.
