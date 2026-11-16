# Cross-Skill Destructive Command Index

A single-page index of destructive or irreversible Docker commands documented across all Docker skills, so agents and reviewers can see the full picture without hunting through every skill. Each row's detail lives in the owning skill — this table only tracks what exists and where. Every command below requires explicit user confirmation before running, except the narrow Tier 1 exception in `topics/docker-destructive-guardrails/README.md` — see that skill's Core guidance for exactly which cases qualify.

| Command | What's lost | Owning skill |
|---|---|---|
| `docker rm` | Stopped container and its writable layer; low-risk removal (Tier 1 in the guardrail model) | `topics/docker-destructive-guardrails/README.md` |
| `docker rm -f` | Container removed without graceful shutdown; un-persisted in-container state | `topics/docker-destructive-guardrails/README.md` |
| `docker container prune` | All stopped containers on the host at once | `topics/docker-destructive-guardrails/README.md` |
| `docker kill` | Container killed via SIGKILL with no grace period; always Tier 2 | `topics/docker-destructive-guardrails/README.md` |
| `docker system prune` (esp. `-a`/`--volumes`) | Stopped containers, unused networks, dangling/all unused images, build cache, and (with `--volumes`) unused *anonymous* volume data | `topics/docker-destructive-guardrails/README.md` |
| `docker rmi` / `docker image rm` | A specific image | `topics/docker-destructive-guardrails/README.md` |
| `docker image prune -a` | All images not used by an existing container, including tagged ones | `topics/docker-destructive-guardrails/README.md` |
| `docker network rm` | A specifically named network's configuration | `topics/docker-destructive-guardrails/README.md` |
| `docker network prune` | All unused user-defined networks and their configuration | `topics/docker-destructive-guardrails/README.md` |
| `docker builder prune` (esp. `-a`) | Build cache; with `-a`, also internal helper/frontend images and cache shared with other build outputs | `topics/docker-destructive-guardrails/README.md` |
| `docker buildx rm` | A builder instance's configuration/state (not its build cache) | `topics/docker-destructive-guardrails/README.md` |
| `docker context rm` | Local context configuration (endpoint, TLS references) for a Docker host | `topics/docker-destructive-guardrails/README.md` |
| `docker volume rm` / `docker volume prune` (standalone, no Compose project in play) | Volume data, directly | `topics/docker-destructive-guardrails/README.md` |
| `docker compose down -v` / `docker compose down --volumes` | Named volumes and their data (e.g. database state) | `topics/docker-compose-patterns/README.md` |
| `docker volume rm` / `docker volume prune` (a Compose project's volumes) | Volume data, directly | `topics/docker-compose-patterns/README.md` |
| `docker compose rm -v` | Anonymous volumes attached to removed containers | `topics/docker-compose-patterns/README.md` |
| `sbx rm` / `sbx prune` | Sandbox containers, Git worktrees, state, and sandbox-scoped secrets; for a clone-mode sandbox, any unfetched commits too | `topics/docker-sandboxes-lifecycle/README.md` |
| Docker Desktop destructive commands | Pending — see PR #14, not yet merged. Do not assume content until that skill ships. | *pending* |

## Notes

- This table is a routing aid, not a replacement for the owning skill's detail. Read the owning skill (`references/docker-cli-destructive-commands.md` in this skill, or the equivalent reference in `topics/docker-compose-patterns/README.md`) before advising on or running any of these commands.
