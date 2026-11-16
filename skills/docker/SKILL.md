---
name: docker
description: Applies Docker's own guidance for containerizing projects and using Docker tools safely. Covers writing and reviewing Dockerfiles (multi-stage builds, layer caching, build secrets, non-root users, image size), docker compose files (services, health checks, depends_on, volumes, networks, dev overrides, Compose Watch), Dockerizing a project for the first time, image builds, Docker Agent (cagent agent.yaml, docker agent run, serve, share and eval) and Docker Sandboxes (sbx run, create and rm, sbxenv.yaml, kit spec.yaml, sbx policy, sbx secret). Sets the guardrails for destructive docker commands. Use when the user writes or debugs a Dockerfile, compose.yaml or .dockerignore, says an image is too big or a build is slow, wants to Dockerize a project or add a database to the stack, works with docker agent or sbx, and before running or suggesting docker rm, prune, compose down -v, volume rm, system prune or image rm, including requests to "clean up", "reset" or "start fresh".
---

# Docker

Docker's own guidance, ported from the `docker-skills` plugin by Docker, Inc. (Apache-2.0, see `LICENSE`) and split into topics. All paths below are relative to `~/.agents/skills/docker/`. Inside a topic, "this skill" means that topic, `<skill-dir>` means `~/.agents/skills/docker/topics/<topic>`, and a path like `topics/docker-compose-patterns/README.md` points to another topic.

## Before any destructive docker command

**Read `topics/docker-destructive-guardrails/README.md` before you run or suggest any command that deletes or resets Docker state**: `docker rm`, `docker kill`, any `prune` (system, container, image, volume, network, builder), `docker compose down -v`, `docker volume rm`, `docker rmi` or `docker image rm` on an image others use, `sbx rm`, `sbx prune` and `sbx policy reset`. This applies when the user only says "clean up", "reset" or "start fresh". For a Compose project's volumes also read `topics/docker-compose-patterns/README.md`; for sandboxes, `topics/docker-sandboxes-lifecycle/README.md`.

Local rule, stricter than that topic: never stop, remove or recreate a container, volume or network this session didn't start without asking the user first. That covers `docker stop`, `docker compose down`, and `docker compose up` runs that recreate existing services. It overrides the topic's Tier 1 exception for a stopped container this session didn't create.

## How to use

Match the task to a topic below and read only that topic's `README.md`. Each topic lists its own references, assets, scripts and checks; open those when the topic says to. When a task spans two topics, read both.

Examples:

- "Dockerize this Django app with Postgres and Redis": read `topics/docker-project-foundations/README.md`, then `topics/docker-compose-patterns/README.md` for the service wiring.
- "Our image is 1.2 GB and the build takes six minutes": read `topics/docker-build-strategies/README.md`.

## Topics

When the task is about one of these, read the matching file:

- Setting up or Dockerizing a project with no Docker setup yet, or adding a database, cache or queue to it instead of a host install: `topics/docker-project-foundations/README.md`.
- Writing, reviewing or optimizing a Dockerfile or `.dockerignore`: image size, slow builds, layer caching, multi-stage builds, build secrets and SSH, non-root users: `topics/docker-build-strategies/README.md`.
- Creating, changing or debugging `compose.yaml` or `compose.override.yaml`: service wiring, health checks, `depends_on`, volumes, networks, environment variables, Compose Watch, Compose's destructive commands: `topics/docker-compose-patterns/README.md`.
- Any destructive Docker command (see above): `topics/docker-destructive-guardrails/README.md`.
- Writing or editing a Docker Agent (cagent) `agent.yaml`: models, providers, built-in or MCP toolsets, `sub_agents` teams: `topics/docker-agent-config/README.md`.
- Running a Docker Agent: `docker agent run`, `--safety`, `--yolo`, `--sandbox` and its allowlist, aliases, `--worktree`, `docker agent doctor`: `topics/docker-agent-run/README.md`.
- Serving a Docker Agent (`serve mcp/api/a2a/acp/chat`), sharing it through a registry (`share push/pull`) or evaluating it (`docker agent eval`, `--baseline`): `topics/docker-agent-deploy/README.md`.
- Creating, reattaching to, listing, stopping or removing standalone `sbx` sandboxes, `--clone`, extra workspaces, `sbx exec`, `sbx cp`, `sbx ports`, `sbx prune`: `topics/docker-sandboxes-lifecycle/README.md`.
- What a sandbox can reach or which credentials it uses: `sbx policy`, `sbx secret`, registry pull credentials: `topics/docker-sandboxes-network-credentials/README.md`.
- A checked-in `sbxenv.yaml` and `sbx env create/run/plan/exec/rm`: `topics/docker-sandboxes-env/README.md`.
- A sandbox kit `spec.yaml` and `sbx kit validate/pack/push/pull/sign/verify/add`: `topics/docker-sandboxes-kits/README.md`.

When the user says "my sandbox", find out first whether they run `docker agent run --sandbox` (`topics/docker-agent-run/README.md`) or standalone `sbx` (the `docker-sandboxes-*` topics).
