# Service Skill Handoff

**Do NOT answer the user's service-specific question until you have checked for the service skill using the approved methods below.** The service skill has deeper, more current guidance than the knowledge cards. If it is unavailable, follow the documented knowledge-card fallback.

## Before loading (skip once the service is known)

1. **Resolve the service** — if the service isn't already clear from context, map common names:
   - "Postgres" → Aurora PostgreSQL
   - "Aurora" / "my cluster" → Aurora PostgreSQL or Aurora MySQL (ask if unclear)
   - "MySQL" → Aurora MySQL or RDS for MySQL (ask if unclear)
   - "DynamoDB" / "my table" → DynamoDB
   - "DSQL" → Aurora DSQL
   - "Redis" / "Valkey" / "my cache" → ElastiCache
   - "Mongo" / "DocumentDB" → DocumentDB
   - Other service names → map directly to the service reference table
   - If you still can't determine the service, ask: "Which AWS database service are you using?"

2. **Confirm intent** — if the user's question is actually about choosing or comparing services ("should I be using this?" / "is there something better?"), re-route to `select` instead.

## How to load a service skill

Look up the skill name from the service reference table in `../README.md` (the `Service skill` column).

If the table shows `—` (no service skill listed), skip directly to "If the service skill is not available" below — answer using the knowledge card and documentation.

Otherwise, load it with one of these methods. Loading a skill this way does not require user consent. It is not software installation and does not authorize any AWS resource change.

### 1. Local topic

If `~/.agents/skills/aws/topics/<skill>/README.md` exists, read it. None of the database service skills is ported today, so this usually falls through to method 2.

### 2. Public Agent Toolkit repo

Read the skill from `aws/agent-toolkit-for-aws` as described in `~/.agents/skills/aws/SKILL.md` ("Skills a topic names that aren't ported"), for example `gh api repos/aws/agent-toolkit-for-aws/contents/skills/specialized-skills/database-skills/<skill>/SKILL.md -H 'Accept: application/vnd.github.raw'`. You already have the authoritative skill name from the table, so pass it directly.

## If the service skill is not available

If no service skill exists for this service (table shows `—`) or the skill cannot be loaded by any method above, **proceed immediately** using:

- The service's knowledge card (loaded from this skill)
- The service's `llms.txt` documentation index (URL in the knowledge card)
- AWS documentation: fetch the docs.aws.amazon.com page with the web fetch tool

Do NOT narrate failed attempts or explain which methods you tried. **Lead with the recommendation** — answer the user's question directly from the knowledge card first. Mention the service skill at the end, not the beginning.

If the service reference table lists a service skill but it can't be loaded by either method above, advise the user that installing the service-specific skill is the remaining option. Tell them they can find it by searching skills.sh for the exact skill name and verifying the source is `aws/agent-toolkit-for-aws`, or by searching the official `aws/agent-toolkit-for-aws` GitHub repository. Ask for consent before providing or running installation steps. Do not run a package manager, clone or copy a repository, or install the skill before the user explicitly agrees.

**Before taking any provisioning action**, confirm the service choice with the user. If the service skill can be loaded by either method above, load it immediately and follow its confirmation requirements before changing AWS resources. Skill loading does not itself require confirmation. If the service skill would first need to be installed, obtain installation consent as described above. If no service skill is listed, do not provision from this parent skill; provide guidance from the knowledge card and official AWS documentation instead. Consent to load or install a skill does not authorize resource creation or modification.
