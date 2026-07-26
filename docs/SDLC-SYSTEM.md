# SDLC System Walkthrough

This project isn't just a Flask API — it's a demonstration of the **Hermes SDLC pipeline**: an 8-node AI-driven software delivery cycle modeled on Anthropic's production SDLC ([security](https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle), [identity](https://claude.com/blog/agent-identity-access-model), [migration](https://claude.com/blog/ai-code-migration)).

## The 8-Node Cycle

```
Ideation → Plan → Code → Test/CI → Deploy → Done
              ↑                           ↓
              └─────── Monitor ←──────────┘
                         ↑
                   Governance (cross-cutting, every card)
```

| Node | Who | What |
|------|-----|------|
| **Ideation** | Human or Monitor | Feature request or production anomaly |
| **Plan** | Orchestrator (Arx) | Decompose into cards, assign risk tier |
| **Code** | software-engineer subagent | TDD: write failing tests, implement, verify |
| **Test/CI** | 3 parallel reviewers + deterministic layer | Security, spec, quality — all must PASS |
| **Deploy** | Deploy worker | Staging → smoke → human gate (P0/P1) → prod |
| **Done** | Orchestrator | Card closed, metrics emitted |
| **Monitor** | sdlc-monitor (cron) | Log scan, dep audit, secrets scan → new cards |
| **Governance** | Score reader (cron) | Read score trends, edit AGENTS.md when thresholds cross |

See [ARCHITECTURE.md](ARCHITECTURE.md) for full mermaid diagrams and sequence flows.

## Where Everything Lives

| Component | Location |
|-----------|----------|
| **This project** | `~/git/sdlc-demo/` |
| **Kanban board** | Hermes kanban (`HERMES_KANBAN_BOARD=sdlc`) |
| **Orchestrator skill** | `~/.hermes/skills/workers/sdlc-orchestration/SKILL.md` |
| **Governance skill** | `~/.hermes/skills/workers/sdlc-governance/SKILL.md` |
| **Monitor skill** | `~/.hermes/skills/workers/sdlc-monitor/SKILL.md` |
| **Reviewer skills** | `~/.hermes/skills/workers/sdlc-security-review/`, `sdlc-spec-review/`, `sdlc-tiebreaker/` |
| **Worker skills** | `~/.hermes/skills/workers/software-engineer/`, `content-growth/`, `operations-research/` |
| **Monitor profile** | `~/.hermes/profiles/sdlc-monitor/` |
| **Cron scripts** | `~/.hermes/scripts/sdlc-log-scan.py` |
| **Scores** | Langfuse (Clickhouse, `http://localhost:3000`) |

## How a Card Moves Through the Pipeline

### 1. Card Creation

A human says "add password reset" or the monitor detects a production error. The orchestrator creates a kanban card:

```
SDLC-NNN: Add input validation to user creation
Risk: P1
Worker: software-engineer
DoD: - [ ] Tests pass - [ ] Security PASS - [ ] Spec PASS - [ ] Quality PASS
```

### 2. Code Stage

The orchestrator dispatches a `software-engineer` subagent with the card's goal, DoD checklist, and this project's `AGENTS.md` (which contains closed-loop rules from earlier cards — boolean-coercion guards, credential safety, input validation patterns).

The worker writes failing tests first, implements the feature, and verifies all tests pass. It commits to a branch and pushes.

### 3. Test/CI — Multi-Reviewer AND-Gate

Three reviewers run in parallel with isolated contexts:

- **Security reviewer** (adversarial): "Find evidence this code is exploitable. Don't validate; attack."
- **Spec compliance reviewer** (skeptic): "Assume the worker took shortcuts. Find the gap."
- **Code quality reviewer** (perfectionist): "Find the case the worker didn't test."

All three must return PASS. If they disagree, a **tiebreaker** subagent rules. After agent reviews pass, the **deterministic layer** (pytest, lint, type checking) acts as the mechanical referee.

### 4. Governance (Inline)

Before the card advances to Deploy, the **governance agent** reads the last 10 cards' scores from Langfuse and checks thresholds. If a pattern emerges — e.g., reviewers keep catching the same bug class across 2+ cards — the governance agent edits `AGENTS.md` with a permanent rule and commits with `sdlc: score-driven — <summary>`.

This is the **closed loop**: "You don't fix the code. You fix the process that produced the code."

### 5. Deploy

The deploy worker builds staging, runs smoke tests, and for P0/P1 cards, requests human approval via Telegram. Once approved, it deploys to production.

### 6. Monitor

Three cron jobs run continuously on the `sdlc-monitor` profile:

| Job | Schedule | What |
|-----|----------|------|
| Log scan | Every 15 min | Scans `docker logs` for ERROR patterns, creates cards for new anomalies |
| Dep audit | Daily 9 AM | Checks for CVEs in `requirements.txt` and Docker base image |
| Secrets scan | Every 4 hours | Greps commits and configs for credentials in source |

When the monitor finds an issue, it opens a new card on the kanban board. A separate `software-engineer` subagent fixes it through the full Test/CI gate. The monitor **cannot fix anything itself** — it has exactly 3 permissions: read logs, write docs, post to Telegram.

## The Scoring System

Every completed card emits 7 scores to Langfuse (`http://localhost:3000`, Clickhouse):

| Score | Type | What it measures |
|-------|------|------------------|
| `sdlc_first_pass_pass` | boolean | Card passed all reviews on first attempt |
| `sdlc_reviewer_agreement` | 1-3 | unanimous / tiebreaker / partial |
| `sdlc_retries_used` | 0-3 | How many retries needed |
| `sdlc_stage_latency_seconds` | numeric | Time in Test/CI stage |
| `sdlc_human_approved` | boolean | Human approved the deploy |
| `sdlc_deploy_succeeded` | boolean | Docker compose up succeeded |
| `sdlc_reviewer_thoroughness` | 1-3 | shallow / adequate / thorough |

The governance agent queries these scores daily and edits AGENTS.md when thresholds cross. Current governance thresholds:

| Score | Threshold | Action |
|-------|-----------|--------|
| `sdlc_first_pass_pass` | < 50% true | Strengthen worker skill with examples |
| `sdlc_reviewer_agreement` | > 50% tiebreaker | Clarify card DoD template |
| `sdlc_reviewer_thoroughness` | > 50% shallow | Strengthen adversarial reviewer instructions |
| `sdlc_retries_used` | avg > 1.5 | Audit recurring bug class, edit AGENTS.md |
| `sdlc_deploy_succeeded` | < 80% | Review deploy config or staging health |

## How to Add a New Feature

1. Tell the orchestrator what you want (e.g., "add password reset endpoint")
2. The orchestrator creates a kanban card and dispatches a worker
3. The worker implements it with TDD
4. Three reviewers vet it
5. Governance checks score trends
6. Deploy to staging → human approves → production
7. Monitor watches for regressions

Or, for a manual approach: branch off main, follow AGENTS.md conventions, open a PR, run the tests (`TEST_URL=http://localhost:5001 pytest tests/ -v`), and merge.

## Running the System

```bash
# Start staging
docker compose -f docker-compose.staging.yml -p sdlc-staging up -d --build

# Start production (deployed via SDLC pipeline after human approval)
docker compose -f docker-compose.prod.yml -p sdlc-prod up -d --build

# Run tests against staging
TEST_URL=http://localhost:5001 pytest tests/ -v
```

## Cron Jobs

All active SDLC cron jobs (visible via `hermes cron list`):

| Job | Schedule | Description |
|-----|----------|-------------|
| `sdlc-log-scan` | */15 min | Scan docker logs for errors |
| `sdlc-dep-audit` | Daily 6 AM | Check dependencies for CVEs |
| `sdlc-secrets-scan` | Every 4h | Scan commits for hardcoded secrets |
| `sdlc-governance` | Daily 9 AM | Board metrics + stale card alerts |
| `sdlc-governance-scores` | Daily 8 AM | Read score trends, auto-edit AGENTS.md |

## Langfuse Dashboard

Scores are viewable at `http://localhost:3000` (project "Mac Mini"). Direct Clickhouse query for governance scripts:

```bash
docker exec langfuse-stack-clickhouse-1 clickhouse-client --query \
  "SELECT name, count() FROM default.scores WHERE name LIKE 'sdlc_%' GROUP BY name"
```

## Identity Scopes

| Scope | Hermes mechanism | Used for |
|-------|-----------------|----------|
| **Workspace** | Default profile (Arx) + `sdlc-monitor` profile | Orchestration, monitoring, governance |
| **Private channel** | Per-dispatch toolset restrictions on subagents | Software-engineer, reviewers, deployer |
| **Personal DM** | Local terminal only | Mark's manual work, prod deploy keys |
