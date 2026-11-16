---
name: to-questionnaire
description: "Turns an open decision the user can't settle alone into a questionnaire for one other person (a PM, PO, designer, another team, a customer contact) to fill in async or walk through in a meeting. Use when the user asks for a questionnaire or a list of questions to send someone, from product-lens's open questions, and whenever an open product question (a business rule, an edge case the ticket skips, who gets a feature) comes up while building a feature and only someone else can answer it."
---

# To questionnaire

Adapted from Matt Pocock's to-questionnaire (MIT, https://github.com/mattpocock/skills).

A questionnaire pulls knowledge out of someone who has it. Interview the user only about the send (who it goes to, what they need back), which they can always answer. The questions in the document then aim at the gap between what the recipient knows and what the user needs.

## Mid-feature trigger

When an open product question blocks a feature being built, stop guessing. Say in one line which question is open and that a guess would end up in code, then offer the questionnaire. If the user prefers a quick Slack question, draft it with `reply-with-standing` instead. Keep building the parts the answer doesn't change.

## Steps

1. **Who is it going to?** Ask, in one message, the recipient's role, what they know that the user doesn't, and how they relate to the user. When this comes from `product-lens`, its open questions already name who should answer each; group them by person and make one questionnaire per person. **Done when** you know the recipient and their area.
2. **What do you need back?** Ask, in one message, the decisions or facts the user can't settle alone. Pre-fill the list from the conversation (product-lens's open questions, the ticket, the code you read) and let the user cut or add. **Done when** you have a concrete list of what the user must be able to decide afterwards.
3. **Gather what you can first.** Drop any question the code, Jira, Confluence or Slack already answers, and use that answer as context instead. The recipient's time is the expensive part.
4. **Write the questionnaire** with the structure below, in the user's voice (`plain-writing`). Save it to the scratchpad directory when there is one, else the current directory, as `questionnaire-<slug>.md`, and give the absolute path. **Done when** the file exists and every item from step 2 has a question.

Ask before sending, posting or sharing it anywhere (Slack, Jira, Confluence, email). Any message that carries it follows `reply-with-standing`.

## Structure

Order questions most important first, since async answers may come in one pass. Group under `##` themes once there are more than five questions.

```markdown
# <Title>

**Purpose:** <the decision riding on this, one sentence>
**From:** <the user> **To:** <the recipient> **Used for:** <where the answers go: a ticket, a PR, a design>

## Context

<One paragraph a recipient who wasn't in the user's head can answer from. Link the ticket or PR.>

## How to answer

<Deadline and rough effort. "I don't know" and partial answers help; flag what you're unsure of instead of skipping it.>

## <Theme>

### <One question, one idea, never compound>

_Why this matters: <one line, only when the question could be misread or invite a throwaway answer>_

> 

## Anything else?

Is there anything we didn't ask that we should know?
```

Prefer questions with concrete options when you can name them ("When a buyer has two licenses in different states, should the order use A) the ship-to license or B) the bill-to license?") over open ones. Put each option's consequence in the "why this matters" line when it changes what gets built.
