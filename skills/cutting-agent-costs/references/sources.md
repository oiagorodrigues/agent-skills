# Sources

Read the source before quoting a number to someone else; provider prices and defaults change.

## Claude Code
- Prompt caching in Claude Code (TTL, what breaks the cache): https://code.claude.com/docs/en/prompt-caching
- Managing costs (hooks that trim output, LSP plugins): https://code.claude.com/docs/en/costs
- Headless mode (`-p`, JSON output, `--bare`, structured output): https://code.claude.com/docs/en/headless
- CLI flags: https://code.claude.com/docs/en/cli-reference
- Skills (listing cost, `skillOverrides`): https://code.claude.com/docs/en/skills
- OpenTelemetry metrics and `OTEL_RESOURCE_ATTRIBUTES`: https://code.claude.com/docs/en/monitoring-usage
- Cost tracking fields in the Agent SDK: https://code.claude.com/docs/en/agent-sdk/cost-tracking
- Environment variables (`CLAUDE_CONFIG_DIR`, cache TTL): https://code.claude.com/docs/en/env-vars

## Prompt caching by provider
- Anthropic: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- OpenAI: https://developers.openai.com/api/docs/guides/prompt-caching
- Gemini: https://aistudio.google.com/docs/caching
- Manus, KV-cache hit rate as the main metric: https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus

## Context engineering
- Effective context engineering for agents: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Context management (clearing tool results, memory tool): https://claude.com/blog/context-management
- Context editing API: https://platform.claude.com/docs/en/build-with-claude/context-editing
- Compaction API: https://platform.claude.com/docs/en/build-with-claude/compaction
- Tool search and programmatic tool calling: https://www.anthropic.com/engineering/advanced-tool-use
- Code execution with MCP: https://www.anthropic.com/engineering/code-execution-with-mcp
- Observation masking vs summarization (JetBrains): https://arxiv.org/abs/2508.21433
- Harness design for long-running apps (stage cost mix, sprint contracts): https://www.anthropic.com/engineering/harness-design-long-running-apps
- Aider repo map: https://aider.chat/docs/repomap.html

## Memory
- Components of agent memory: https://www.anthropic.com/engineering/components-of-agent-memory
- Memory tool: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- ACE, itemized context updates (numbers not checked): https://arxiv.org/abs/2510.04618

## Routing
- LiteLLM auto-routing benchmark: https://docs.litellm.ai/docs/proxy/auto_routing_benchmark
- Escalation handoff tax: https://arxiv.org/abs/2608.24358
- Trajectory-conditioned routing: https://arxiv.org/abs/2607.00053
- Cross-family code review direction: https://arxiv.org/abs/2607.21656
- Self-attribution bias in code review: https://arxiv.org/abs/2603.04582
- OpenRouter model routing: https://openrouter.ai/docs/guides/features/model-routing
- FrugalGPT (older baseline): https://arxiv.org/abs/2305.05176
- RouteLLM (older baseline): https://arxiv.org/abs/2406.18665

## Deterministic pipelines
- Stripe Minions, part 1: https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents
- Stripe Minions, part 2: https://stripe.dev/blog/minions-stripes-one-shot-end-to-end-coding-agents-part-2
- Agentless: https://arxiv.org/abs/2407.01489
- SWE-agent ACI: https://arxiv.org/abs/2405.15793
- Codex non-interactive mode: https://developers.openai.com/codex/noninteractive

## Budgets and effort
- Effort parameter: https://platform.claude.com/docs/en/build-with-claude/effort
- Task budgets (API only): https://platform.claude.com/docs/en/build-with-claude/task-budgets
- Batch processing: https://platform.claude.com/docs/en/build-with-claude/batch-processing
- OpenAI flex processing: https://developers.openai.com/docs/guides/flex-processing

## Evaluation
- Evals for agents: https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Infrastructure noise in agent evals: https://www.anthropic.com/engineering/infrastructure-noise
- OpenTelemetry GenAI semantic conventions: https://github.com/open-telemetry/semantic-conventions-genai
