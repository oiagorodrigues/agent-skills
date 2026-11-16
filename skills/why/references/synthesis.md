# Synthesis

Adapted from pstack's why (Lauren Tan, MIT, https://github.com/cursor/plugins/tree/main/pstack).

Merge the investigators' findings into one answer. Weigh the evidence yourself; investigators gathered material, not conclusions. Merge duplicate citations, keep contradictions visible, grade each claim with `epistemics.md`, and open any citation a conclusion rests on before using it. Write it with `plain-writing`. Drop a section that has nothing in it, except "What we don't know" and "Sources consulted".

## Output

```markdown
### The question
<one or two sentences>

### The code
<paths, line ranges, key symbols; two or three lines for a cold reader>

### What we found
- [Direct] <claim>. Source: PR #123 https://github.com/... "<short quote>"
- [Supported] <claim>. Evidence: <item and what it adds>, <item and what it adds>

### What we can reasonably infer
- [Inferred] <hedged claim>. Reasoning: <evidence and the inference step>

### Competing hypotheses
- Hypothesis: <one sentence>. For: <items>. Against or missing: <what would have to be true but isn't>

### What we don't know
- <the question, the sources searched, the queries, what came back>
- <who would likely know: the PR author, the ticket reporter, the owning team>

### Sources consulted
- Source control: <files, number of commits read, PRs>
- Jira: <keys fetched, JQL run> | skipped: <reason>
- Confluence: <pages, queries> | skipped: <reason>
- Slack: <queries, threads read> | skipped: <reason>
- Sentry: <issues, queries, window> | skipped: <reason>
- Datadog: <monitors, metrics, window> | skipped: <reason>
- Sigma: <tables, window, numbers> | skipped: <reason>

### Confidence
<one or two sentences: which parts are well supported, which are inferred, what couldn't be answered>
```

## Before changing the code

When the question leads to a change, add:

- **Preserve:** behavior the record shows someone needed, with the citation.
- **Change:** what the record shows no longer applies (the customer left, the error stopped in Sentry, the flag is fully on).
- **Avoid:** approaches the history shows were tried and reverted.
- **Risk:** what is still unknown and who to ask before removing it.

## Quality check

1. Every claim in "What we found" has a citation.
2. Wording matches the tier; inferred claims don't use "because".
3. Every contradiction noticed is shown, not resolved silently.
4. "What we don't know" names specific searches.
5. The user's own guess was tested, not confirmed by default.
6. No code is cited as evidence of its own intent.
