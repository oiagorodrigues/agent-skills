# Evals

## Contents

1. Error analysis
2. Synthetic inputs when there is no traffic
3. Checks: code first, then LLM judges
4. Validating an LLM judge
5. The eval set in the repo
6. RAG evals
7. Agent evals
8. Production signals
9. Worked example: support ticket triage
10. Sources

## 1. Error analysis

Error analysis comes before any metric. Generic scores (helpfulness, coherence, a 1 to 5 rating) don't tell you what to fix, so build the checks from the failures you see in your own traces.

1. Pull 30 to 100 traces from the call log (SKILL.md, "Log every call"), spread across user types, input lengths and the paths the feature takes. A trace is the whole run: inputs, retrieved context, tool calls, output.
2. Read each trace and write a one-line note on the first thing that went wrong, in plain words ("ignored the delivery date in the second paragraph"). Mark the trace pass or fail. This is open coding: don't use a fixed list of categories yet.
3. Group the notes into failure modes, each with a short name and a one-sentence definition precise enough that two people would label the same trace the same way. This is axial coding.
4. Count the traces per mode. Stop reading new traces when about 20 in a row add no new mode.
5. Pick one person who knows the domain to own the labels. Disagreements go to that person, so the definitions stay consistent.

The output is a table: mode, definition, count, one example trace id. The biggest count is the first thing to fix, and a mode a prompt change fixes for good may not need a check at all.

A simple trace viewer (a script that prints one trace per screen, with keys for pass, fail and a note) speeds this up more than any tool you'd buy, because reading is the slow part.

## 2. Synthetic inputs when there is no traffic

Before launch, generate inputs on purpose instead of asking a model for "100 varied examples", which returns 100 similar ones.

1. List the dimensions that change the feature's behavior, for example user role, request type, input length and missing fields.
2. Write combinations of values (tuples) by hand, a few dozen, covering the cases you expect to be hard.
3. Have a model turn each tuple into a realistic input, then read them and drop the unrealistic ones.
4. Run the feature on them and do error analysis as in section 1.

Replace synthetic cases with real traces as soon as traffic exists.

## 3. Checks: code first, then LLM judges

Each failure mode gets one check that returns pass or fail for one trace.

- Use code when a rule can decide it: the output parses, a required field is present, a value is in the allowed set, a date matches the source, the cited id exists in the retrieved chunks, the right tool was called with valid arguments, the answer is under a length limit. Code checks are free, fast and never drift.
- Use an LLM judge only for what code can't decide, such as "the summary leaves out a commitment the customer made". One judge checks one failure mode and returns pass or fail with a one-line reason. Never ask a judge for a score on a scale, since binary labels are easier to agree on and to act on.
- A judge prompt states the failure mode's definition, gives a few labeled examples of pass and fail (taken from the training split in section 4), and asks for the reason before the verdict.
- Prefer a reference-free judge (looks at input and output) when it can decide; use a reference answer only when the right output can't be told from the input.

## 4. Validating an LLM judge

A judge counts as a check only after it agrees with the domain owner's labels.

1. Label traces by hand for that one failure mode, with both passes and fails represented (at least a few dozen of each when you can get them).
2. Split the labeled traces: a small training set to pick few-shot examples for the judge prompt, a dev set to tune the prompt on, and a test set you look at once.
3. Tune the judge prompt on the dev set, then run it on the test set and report the true positive rate (share of human passes the judge passes) and the true negative rate (share of human fails the judge fails). Set the bar you need before you measure.
4. Write both rates next to the check in the repo. Re-measure them whenever the judge prompt or judge model changes.

The judge's raw pass rate on unlabeled traces is biased by its errors. To estimate the true pass rate, correct it: true rate = (observed pass rate + TNR - 1) / (TPR + TNR - 1). The correction only makes sense when TPR + TNR is well above 1.

A judge with a low true negative rate is the dangerous one, because it passes the failures you built it to catch.

## 5. The eval set in the repo

Keep the eval next to the feature code so a prompt change and its result land in the same PR. One layout that works:

```
evals/<feature>/
  cases.jsonl        # one input per line, with id, source trace id and tags
  labels.jsonl       # human pass/fail per case and failure mode, for judge validation
  checks.py          # code checks and judge calls, one function per failure mode
  judges/<mode>.md   # one judge prompt per mode, versioned like any prompt
  run.py             # runs the feature on every case, runs every check, prints pass rate per check
```

- The runner calls the real prompt file and model config the feature uses, never a copy.
- It prints the pass rate per check and the ids of failing cases, and writes results to a file so two runs can be diffed.
- Outputs vary between runs, so run the baseline twice before a change to see how much the pass rate moves on its own, and treat a smaller difference as noise.
- Keep two groups of cases. Regression cases must keep passing at close to 100%; capability cases are hard ones you're still working on.
- Real model calls cost money, so run the eval on changes to the prompt, model, parameters, retrieval or tools (CI path filter or a manual job), not on every commit. Code checks on fixed recorded outputs can run in the normal test suite.
- Never put production PII in the repo. Redact cases the way the call log does, or build them from synthetic inputs.

## 6. RAG evals

Evaluate retrieval first, because generation can't use a chunk it never sees.

1. Build a labeled set of 50 or more real queries, each with the ids of the chunks that answer it. Pull queries from logs; have the domain owner mark the right chunks.
2. Measure recall@k, the share of queries where at least one right chunk is in the top k, at the k the prompt actually uses. Also look at the rank of the first right chunk (MRR) when you add a reranker.
3. Tune chunking, embedding model, metadata filters, hybrid keyword search and reranking against recall@k, one change per run.
4. Then check generation with the section 3 method. Common modes are an answer not supported by the retrieved text (a judge with the chunks as input), a wrong or missing citation (code: the cited id must be in the retrieved set) and answering when the text doesn't hold the answer (include queries with no answer in the corpus).

Retrieval filters by tenant or permission are a security property. Test them in `security-review`, not only for recall.

## 7. Agent evals

- Check the end state first: did the order get created with the right lines, was the ticket closed with the right status. Do this in code against the system's state.
- Check tool calls next: right tool for the step, valid arguments, no calls the task didn't need, no repeated identical calls.
- Check the trajectory only for modes you've seen in error analysis, because many paths can reach a correct end state.
- Record turns, tokens, cost and wall time per case, and fail a case that hits the turn or budget cap.
- Run each case more than once; agents vary more than single calls.

## 8. Production signals

- Log the user's reaction to each output where the UI shows one: accepted as is, edited (and the diff), rejected, retried. The accept rate is the production quality number to watch per prompt version.
- Sample logged traces every week (more right after a release or model change) and repeat error analysis on them.
- Turn every new failure into an eval case through the replay script, and into a new check if it's a new mode.
- Watch for drift: a shift in input mix, a new model version behind the same alias, a retrieval index that changed. Re-run the eval when any of them happens.

## 9. Worked example: support ticket triage

The feature reads an inbound support ticket and returns `{category, priority, summary}`; code routes the ticket by category and priority. Numbers below are illustrative.

Shape. One call with the category list in the prompt. A router or agent adds nothing, because the steps are fixed.

Boundary. The prompt lives in `prompts/ticket_triage.md`; its version is the file's content hash. The output parses into a Pydantic model where `category` is an enum and `priority` is `low | normal | urgent`. A parse failure retries once, then sends the ticket to the manual queue. Each call logs the prompt version, model id, ticket id, output and validation result.

Error analysis. 80 logged tickets, read with a small trace viewer. Notes grouped into modes:

| Mode | Definition | Count |
|---|---|---|
| missed-urgency | Ticket says a delivery or payment is blocked today, priority isn't urgent | 11 |
| wrong-billing | A billing question routed to a non-billing category | 6 |
| summary-omits-ask | Summary leaves out what the customer asked for | 5 |
| invalid-category | Category not in the enum (caught by validation, retried) | 2 |

Checks.

- invalid-category: code, already enforced by the schema; the check counts retries.
- wrong-billing: code, because labeled cases have an expected category to compare.
- missed-urgency: code against the human label on each case.
- summary-omits-ask: needs reading, so an LLM judge with the definition above and four labeled examples.

Judge validation. The domain owner labeled 120 summaries (78 pass, 42 fail). 20 went to training examples, 50 to dev, 50 to test. On test the judge reached TPR 0.94 and TNR 0.88, above the bar of 0.85 set before measuring, so it was accepted. Observed pass rate on all 80 cases was 0.90; corrected: (0.90 + 0.88 - 1) / (0.94 + 0.88 - 1) = 0.78 / 0.82 = 0.95.

Eval set. `evals/ticket_triage/` with the 80 cases (redacted), labels, `checks.py`, `judges/summary-omits-ask.md` and `run.py`. CI runs it when `prompts/ticket_triage.md`, the model config or `evals/ticket_triage/` changes.

Iteration. Two baseline runs gave missed-urgency pass rates of 86% and 88%, so differences of a couple of points are noise. The fix for the biggest mode added a sentence to the prompt defining urgent as "a delivery, payment or login blocked today" with two examples. The PR shows missed-urgency 87% to 96%, the other checks within noise. After release, a weekly sample found tickets in Spanish being marked low priority; they became 10 new cases and a check.

## 10. Sources

- Hamel Husain, evals FAQ: https://hamel.dev/blog/posts/evals-faq/
- Eugene Yan, Patterns for building LLM-based systems and products: https://eugeneyan.com/writing/llm-patterns/
- Chip Huyen, AI Engineering (O'Reilly), chapters on evaluation: https://www.oreilly.com/library/view/ai-engineering/9781098166298/
- Anthropic, Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
