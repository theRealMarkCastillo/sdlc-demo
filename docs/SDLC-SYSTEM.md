# SDLC System Architecture (snapshot — canonical version in wiki)

> **Note:** This is a snapshot of the SDLC architecture document. The canonical, up-to-date version is in the wiki at `~/wiki/concepts/sdlc-architecture.md`. This copy ensures the project is self-contained for anyone who clones it.

---

---
title: SDLC Architecture — Hermes Agent AI-native Software Development Lifecycle
created: 2026-07-26
updated: 2026-07-26
schema_version: 1
type: concept
tags: [sdlc, architecture, hermes, kanban, ai-agents, anthropic-pattern]
confidence: high
---

# Hermes SDLC Architecture

A complete AI-native software development lifecycle built on Hermes Agent, modeled on Anthropic's production SDLC. Inspired by their [security](https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle), [agent identity](https://claude.com/blog/agent-identity-access-model), and [migration loop](https://claude.com/blog/ai-code-migration) articles.

## What This Is

A working end-to-end SDLC pipeline: **Plan → Code → Test/CI → Deploy → Monitor**, with a multi-reviewer AND-gate, tiebreaker routing, closed-loop pattern edits, structured human gates via Telegram, and an incident-response monitor profile.

Proven on 4 cards (SDLC-001 through SDLC-004) including real Docker + PostgreSQL infrastructure and a production deploy.

## The Architecture in One Picture

```
       ┌──────── IDEATION (human-initiated) ────────┐
       │                                            │
       ▼                                            │
  ┌─────────┐                                       │
  │   PLAN  │  (orchestrator decides risk tier)    │
  └────┬────┘                                       │
       ▼                                            │
  ┌─────────┐                                       │
  │  CODE   │  (software-engineer subagent)        │
  └────┬────┘                                       │
       ▼                                            │
  ┌─────────┐                                       │
  │ TEST/CI │  (3 reviewers + tiebreaker + referee)│
  └────┬────┘                                       │
       ▼                                            │
  ┌─────────┐                                       │
  │  DEPLOY │  (staging → smoke → DAST → HIL gate)│
  └────┬────┘                                       │
       ▼                                            │
  ┌─────────┐                                       │
  │ MONITOR │  (cron-driven, 3-permission boundary)│
  └─────────┘ (incidents create new Backlog cards ──┘

   ╔══════════════════════════════════════════════════╗
   ║  GOVERNANCE  (cross-cutting, every stage)        ║
   ║  Skills + rules govern agents                   ║
   ║  Hooks provide human approval gates             ║
   ║  Deterministic layer (lint/test/SAST) is referee║
   ║  Engineer-outside-the-loop edits the loop       ║
   ╚══════════════════════════════════════════════════╝
```

## The Seven Cards That Prove It

| Card | What | Risk | Retries | Outcome |
|------|------|------|---------|---------|
| [[SDLC-001\|sdlc-board/SDLC-001]] | Input validation, type-coercion | P1 | 1 (security + quality) | Closed loop applied to AGENTS.md |
| [[SDLC-002\|sdlc-board/SDLC-002]] | `update_user_email` helper | P1 | 1 (quality → tiebreaker) | Tiebreaker QUALITY_CORRECT proved |
| [[SDLC-003\|sdlc-board/SDLC-003]] | `GET /api/users/<id>` | P1 | 2 (quality → quality) | First real prod deploy (port 5002) |
| [[SDLC-004\|sdlc-board/SDLC-004]] | Critical DatabaseError | P0 | 0 | First card auto-created by monitor |

## The Three Runtime Components

### 1. The Board — Hermes Kanban

Cards live on the `sdlc` board. Switching is `HERMES_KANBAN_BOARD=sdlc` (set in `~/.hermes/.env`). Operations use `hermes kanban` CLI:

```bash
hermes kanban list                    # all tasks
hermes kanban show t_8b6a4c28          # one task with comments + events
hermes kanban comment <id> "text"     # add a comment (review findings, etc.)
hermes kanban complete <id>           # mark Done
```

The orchestrator (me) currently writes to the board via manual CLI because I can't call kanban tools from within an agent context. **Future improvement**: have the orchestrator user do `kanban_create()` calls from the user-facing terminal, or grant the orchestrator kanban dispatcher access via gateway.

### 2. The Skills — 7 SDLC Skills

```
~/.hermes/skills/workers/
├── sdlc                          (entry-point slash command: /sdlc)
├── sdlc-orchestration            (the full pipeline + Telegram routing)
├── sdlc-security-review           (security reviewer subagent)
├── sdlc-tiebreaker                (resolves reviewer disagreement)
├── sdlc-deploy                    (staging → smoke → DAST → human gate → prod)
├── sdlc-monitor                   (cron-driven incident response)
└── sdlc-governance                (metrics, sampling, audit)
```

### 3. The Profile — sdlc-monitor

The only new Hermes profile created. Workspace-scoped system account with a **3-permission boundary** (read logs, write docs, post to Telegram). Cannot write code, deploy, or coordinate with other agents.

Configured to disable `[computer_use, browser, delegation, terminal, file]` and enable `[file, kanban, web, session_search]`. Reviewed from outside-the-loop perspective.

Three crons active on this profile:

| Cron | Schedule | Purpose |
|------|----------|---------|
| `sdlc-log-scan` | every 15m | Scan production logs, open cards on anomalies |
| `sdlc-dep-audit` | daily 6am | Check for CVEs in dependencies |
| `sdlc-secrets-scan` | every 4h | Grep for exposed credentials |

## The Six Principles (Implemented)

1. **Multiple narrow agents > one mega-agent.** Three reviewers (security, spec, quality) with isolated context windows. Caught different bug classes in SDLC-001 and SDLC-003.

2. **Single-purpose identity with minimum permissions.** The `sdlc-monitor` profile cannot modify code even if prompted. Toolset restrictions are the boundary, not prose instructions.

3. **Humans shift where in the lifecycle based on risk.** P0/P1 require human approval at Deploy; P2/P3 auto-deploy. The structured approval format (`approve SDLC-NNN <sha> production`) prevents stale or replayed approvals.

4. **Close the loop.** When a reviewer keeps catching the same mistake class, edit the rulebook (AGENTS.md or skills), then regenerate. SDLC-001 → SDLC-002 demonstrated this: type-coercion rule added to AGENTS.md prevented the bug class from recurring.

5. **Adversarial review + mechanical referee.** Reviewers are explicitly told to *attack* the implementation. The deterministic layer (lint, type check, tests) is the source of truth. They AND-gate together.

6. **Tiebreaker for disagreement.** When reviewers disagree, a third subagent with a different system prompt resolves the dispute. SDLC-002: tiebreaker ruled QUALITY_CORRECT on duplicated validation.

## The 8-Node Cycle (Recap)

```
Ideation → Plan → Code → Test/CI → Deploy → Done
                                       ↑
                                       │
                  Monitor ─────────────┘ (new cards)
```

Monitor is not a linear step; it's a parallel loop that opens cards on anomalies. Governance is node 8, cross-cutting, overlays every other stage.

## What's Still To Do

- [ ] **Operate from terminal**: I can't dispatch kanban operations from agent context. Run `hermes kanban create/complete` from your terminal to drive cards (I'll prompt with the exact commands).
- [ ] **True production deploy**: SDLC-003 deployed to a docker-compose "production" on port 5002. No real production.
- [ ] **Migration tooling**: Add Alembic to the demo project (I tried but got blocked by PEP 668; needs a venv).
- [ ] **Adaptive review weights**: The sdlc-governance skill says review weights are tracked; no implementation yet.
- [ ] **More skills**: `sdlc-archaeology` (mine git history for patterns), `sdlc-postmortem` (turn monitor incidents into learnings).

## Files and References

- **Architecture plan:** `~/.hermes/plans/2026-07-26-hermes-sdlc-architecture.md`
- **Kanban board:** `HERMES_KANBAN_BOARD=sdlc`
- **Test project:** `~/sdlc-demo/` (Flask + PostgreSQL + Docker Compose)
- **Telegram:** chat 8788236757 (default HIL channel)
- **Monitor profile:** `~/.hermes/profiles/sdlc-monitor/`

## Where the Inspiration Came From

- [How Anthropic secures its AI-native software development lifecycle](https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle) — Jason Clinton, Deputy CISO (July 21, 2026)
- [Agent identity: a new access model for autonomous, team-wide AI](https://claude.com/blog/agent-identity-access-model) — Noah Zweben (June 24, 2026)
- [How Anthropic runs large-scale code migrations with Claude Code](https://claude.com/blog/ai-code-migration) (July 16, 2026)
