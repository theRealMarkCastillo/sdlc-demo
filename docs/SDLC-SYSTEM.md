# SDLC Integration

This project is built incrementally through the **Hermes SDLC pipeline** (multi-reviewer AND-gate, retry protocol, automated monitor).

The SDLC orchestrator lives separately (not in this repo). It handles:
- Decomposing feature requests into cards on the **Hermes kanban board** (`HERMES_KANBAN_BOARD=sdlc`)
- Dispatching cards to specialized worker subagents (software-engineer, three reviewers, deployer)
- Applying the multi-reviewer AND-gate (security, spec, quality)
- Routing reviewer disagreements to a tiebreaker
- Forcing rulebook updates (AGENTS.md) when patterns recur (closed loop)
- Sending human-in-the-loop approvals via Telegram

This project's role in that flow: a **target project**. The orchestrator dispatches code-generation tasks here, runs tests against staging (port 5001), and ships production (port 5002) after human approval.

## Project conventions used by the SDLC system

When a worker subagent generates code in this repo, it reads `AGENTS.md` first. The `AGENTS.md` here encodes:
- Tech stack and Python conventions
- Closed-loop rules from earlier cards (e.g., type-coercion handling)
- Never-log-PII rule

## Verifying an SDLC card against this project

When a card on the Hermes kanban board reaches Test/CI stage for code in this repo, the three reviewers verify against:
1. **Security** — OWASP checks, parameterized queries (psycopg2 `%s`), no hardcoded secrets
2. **Spec** — tests in `tests/` cover the DoD; live staging (`localhost:5001`) passes
3. **Quality** — type hints, docstrings, no dead code, DRY (no duplication per the closed-loop rule)

## Deploy via SDLC

The orchestrator runs:
```bash
# Staging
docker compose -f docker-compose.staging.yml -p sdlc-staging up -d --build
curl http://localhost:5001/health

# Production (after human approval)
docker compose -f docker-compose.prod.yml -p sdlc-prod up -d --build
curl http://localhost:5002/health
```

See `docs/DEPLOYMENT.md` for details.
