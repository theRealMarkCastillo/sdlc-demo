# SDLC System Design Plan

> Canonical design document. Originally written 2026-07-26, updated as the system evolved.
> Live at `~/git/sdlc-demo/docs/PLAN.md`. The copy at `~/.hermes/plans/` is a snapshot.

---

# Hermes SDLC — Agentic Software Development Lifecycle

> Design plan for a separate SDLC system alongside the existing CoS kanban. Based on Anthropic's AI-native SDLC architecture, implemented with Hermes profiles, subagents, and a kanban board as state.

**Author:** Arx (default profile, Chief of Staff)
**Based on:**
- [How Anthropic secures its AI-native software development lifecycle](https://claude.com/blog/how-anthropic-secures-its-ai-native-software-development-lifecycle) (Jason Clinton, Deputy CISO, July 21, 2026)
- [Agent identity: a new access model for autonomous, team-wide AI](https://claude.com/blog/agent-identity-access-model) (Noah Zweben, June 24, 2026)
- [How Anthropic runs large-scale code migrations with Claude Code](https://claude.com/blog/ai-code-migration) (July 16, 2026)
**Date:** 2026-07-26 (revised: added identity model + cycle framing)

---

## Overview

Anthropic runs an SDLC where AI authors ~80% of merged code and more than half of all code is merged by autonomous agents. They didn't build one mega-agent — they built **multiple specialized agents with hard identity boundaries**, each scoped to one stage and one purpose. The kanban board is the shared state.

This plan maps that architecture to Hermes:

| Anthropic | Hermes equivalent |
|-----------|-------------------|
| Claude agents (separate instances) | Hermes **profiles** — isolated skills, memories, cron, toolset restrictions |
| CLAUDE.md files | AGENTS.md + shared skills loaded by profiles |
| /security-review | Custom skill loaded at code-generation time |
| Multiple review agents per PR | Multiple `delegate_task` subagents, each with different review scope |
| Agent-to-agent over Slack | Gateway (Telegram/Discord) |
| SIEM / audit trail | Session DB + git history on wiki + cron logging |
| Kanban board | Hermes kanban board `sdlc` (managed via `kanban_create`, `kanban_comment`, `kanban_complete`) |
| Risk-tiered codebase | Card priority (P0-P3) + human-gate placement |

---

## Core Design Principles (from Anthropic)

1. **Multiple narrow agents > one mega-agent.** They don't share blindspots. If one is compromised, others catch it. Effort isn't spread too thin.

2. **Each agent gets single-purpose identity with minimum permissions.** Not just what a model _can_ do — what it's _allowed_ to do. Hard boundaries around access and actions, including access to other agents. (Refined by the agent-identity blog: identity is **per-scope** — workspace, private channel, or personal DM — not per-user.)

3. **Humans stay in the loop but shift where based on risk.** Human accountability is still central, but at different points depending on the nature of the codebase. Risk-tier everything.

4. **Close the loop.** Vulnerability found → agent instructions updated → future code avoids it. (Refined by the migration blog: "You don't fix the code. You fix the process (loop) that produced the code." A repeated miss → one sentence in the rulebook → regenerate the affected batch. Engineer stays outside the loop and edits it.)

5. **Adversarial review + mechanical verification.** (From the migration blog: implementer + 2 reviewers + fix agent, with disagreement routing to a tiebreaker. The compiler/test suite is the mechanical referee, not human judgment.) Deterministic + adversarial AND-gated.

6. **Dynamic testing matches deployment cadence.** If code ships faster, testing must run faster. Continuous, not periodic.

7. **Monitor loops, not individual bugs.** The security engineer's job evolves from monitoring bugs to monitoring loops. Agents are treated as a new type of insider threat.

8. **The SDLC is a cycle, not a pipeline.** Monitor → new Ideation. The 8th node is **cross-cutting governance** that overlays every other stage. Skills govern agents; hooks provide human gates at critical junctures.

---

## System Architecture

The SDLC is a **cycle**, not a pipeline. Monitor feeds back to Ideation. Governance is **cross-cutting**, not a stage.

```
              ┌─────────── IDEATION (human-initiated) ───────────┐
              │                                                 │
              ▼                                                 │
        ┌──────────┐                                            │
        │   PLAN   │ (Claude)                                   │
        └────┬─────┘                                            │
             ▼                                                  │
        ┌──────────┐                                            │
        │   CODE   │ (Claude + AGENTS.md + skills)               │
        └────┬─────┘                                            │
             ▼                                                  │
        ┌──────────┐                                            │
        │ TEST/CI  │ (3 review subagents + deterministic layer) │
        └────┬─────┘                                            │
             ▼                                                  │
        ┌──────────┐                                            │
        │  DEPLOY  │ (deploy subagent + human gate for P0/P1)   │
        └────┬─────┘                                            │
             ▼                                                  │
        ┌──────────┐                                            │
        │ MONITOR  │ (cron-driven, 3-permission boundary) ──────┘
        └──────────┘   (production issues create new Ideation)

   ┌─────────────────────────────────────────────────────────────┐
   │  GOVERNANCE  (cross-cutting, every stage)                    │
   │  Skills govern agents · Hooks provide human gates           │
   │  Risk tiers · Sampling · Audit trail · Shadow mode          │
   │  Refereed by: deterministic layer (compiler/lint/test/SAST) │
   └─────────────────────────────────────────────────────────────┘
```

**Eight nodes. One board. Governance overlays everything.**

The orchestrator is **outside the loop** — it doesn't do the work, it edits the loop (skills, AGENTS.md, governance thresholds). The workers are **inside the loop** — implementer + 2 reviewers + fix agent per stage, with disagreement routing to a tiebreaker reviewer.

### The Board as State

The SDLC board is a **Hermes kanban board** (`HERMES_KANBAN_BOARD=sdlc`). Every card carries enough context for a fresh subagent to pick it up. Cards flow through stages tracked via kanban comments and assignee changes — not wiki files. The wiki is for companions only; SDLC state lives in the kanban system and git commits on the project repo.

**The cycle on the board:**

```
        ┌─ Ideation (humans)
        │      │
        │      ▼
   Done ← Deploy ← Test/CI ← Code ← Plan
    ↑                                │
    │                                ▼
   Monitor ── (incident creates new Backlog/Ideation card)
```

The Monitor lane on the board is for **post-deploy verification** of in-flight cards. Production incidents detected by the monitor profile create **new Backlog/Ideation cards** — the loop closes.

Cards stuck in Monitor generate new cards back in Backlog — the closed loop.

---

## Identity Scopes (per agent-identity blog)

Hermes profiles map to Anthropic's identity scopes. The model: **identity is per-scope, not per-user.** A shared workspace identity can be invoked by anyone; a private channel identity is restricted to its members; personal-scope actions always run as the user.

| Scope | Who can invoke | What it has | Hermes equivalent |
|-------|---------------|-------------|-------------------|
| **Workspace** | Anyone (anyone in the workspace/reef) | Broad, low-risk tools: read access, kanban, log scans | Default profile (Arx) + sdlc-monitor profile (3-permission subset) |
| **Private channel** | Cleared few (orchestrator, deployer) | Higher trust: write access, deploy credentials, prod | software-engineer subagent (when given repo write); deploy subagent (staging creds) |
| **Personal DM** | The user only | User's own credentials, personal repos, local env secrets | Local terminal — not a profile, not a subagent |

**Mapping rules:**
- The default profile (Arx) is the **workspace identity** — it has the broad toolset, can dispatch work, but does NOT have personal credentials.
- Each SDLC subagent (engineer, reviewer, deployer) gets a **scoped toolset per dispatch** — narrower than the default. This is "private channel" in the Anthropic model.
- Personal-scope actions (Mark's GitHub PAT, prod deploy keys) are **not** baked into any profile. They live in the user's terminal session and are only injected by the user when needed.
- Revoking an identity means deleting the profile. A `sdlc-monitor` profile that goes rogue? Delete it. Audit trail stays in git.

## Stage 1: PLAN

### Profile: SDLC Orchestrator (me, default profile)
### Worker: operations-research (subagent)

**What happens:**
- Human gives a feature request or bug report
- SDLC Orchestrator decomposes it into a card with clear DoD
- If the card is P0/P1 (high risk): operations-research subagent does a security/feasibility analysis
  - Analyzes against known vulnerability patterns
  - Checks against project AGENTS.md for conflicts
  - Returns risk assessment + suggested mitigations
- Card is placed in Backlog with risk tier assigned

**Risk tiers:**
| Tier | Description | Human gate |
|------|-------------|------------|
| P0 | Auth, payment, PII, infra | Human must approve Plan AND Deploy |
| P1 | Business logic, data mutations | Human must approve Deploy |
| P2 | UI, non-critical features | Human samples only |
| P3 | Docs, config, tests | Auto-merge eligible |

### Toolset: web, file, terminal (for operations-research)

---

## Stage 2: CODE

### Worker: software-engineer (subagent)

**What happens:**
- Orchestrator dispatches card to software-engineer worker
- Worker loads AGENTS.md + security skills at session start
- Generates code with TDD (from subagent-driven-development skill)
- Security guidance is baked into the generation, not bolted on after
- Egress-restricted: terminal + file only (no web, no delegation)
- Commits with conventional commit format
- Produces a PR-like deliverable (branch or patch file)

### Closed loop:
- If a review agent finds a bug class → update AGENTS.md or the relevant skill
- Next code generation avoids that class
- This is the "vulnerability discovered → instructions updated → future code safe" loop

### Toolset: terminal, file (hard boundary — no web, no delegation)

---

## Stage 3: TEST/CI (Adversarial Review + Mechanical Verification)

The migration blog's key insight: **"Don't focus on individual failures. Make review adversarial and verification mechanical."** Each stage has implementer + reviewers + fix agents, with the deterministic layer as the referee.

### Workers: 3 specialized review subagents (dispatched in parallel, **adversarially**)

This is the key innovation. Three agents review with isolated context windows, and they **disagree on purpose** — they assume each other can be wrong, and disagreement routes to a tiebreaker.

#### Reviewer 1: Security (the breaker)
- **Focus:** Injection, auth bypass, data leaks, supply chain, suspicious dependencies
- **Toolset:** file, terminal
- **Checks:** OWASP Top 10, credential exposure, input validation, auth boundaries, dependency audit
- **Output:** PASS/FAIL + specific findings with file:line references

#### Reviewer 2: Spec Compliance (the skeptic)
- **Focus:** Does the implementation match the card's DoD? What's missing or extra?
- **Toolset:** file
- **Checks:** Every DoD item verified, nothing extra (scope creep), nothing missing
- **Output:** PASS/FAIL + gap analysis

#### Reviewer 3: Code Quality (the perfectionist)
- **Focus:** Style, error handling, edge cases, test coverage, performance
- **Toolset:** file, terminal (for running tests)
- **Checks:** Project conventions, linting, test coverage, error paths, edge cases, DRY violations
- **Output:** PASS/FAIL + categorized issues (critical/important/minor)

### Adversarial protocol (NEW)

The three reviewers don't just independently vote. They are explicitly told to **assume the implementation is wrong** and look for evidence of it. This is a different mindset from "review what I built" — it's "attack what I built."

### Tiebreaker routing (NEW)

If reviewers **disagree** (e.g., security says PASS, quality says FAIL on the same line), the orchestrator dispatches a **tiebreaker reviewer** subagent with a different system prompt: given the conflict, decide which finding is correct. Tiebreaker is a separate dispatch, fresh context. The tiebreaker's verdict is final for that finding.

### Deterministic layer: the mechanical referee

After agent reviews pass, the **compiler/lint/type-check/test/SAST** is the source of truth. No human judgment needed for "does it compile" or "do tests pass." This is the migration blog's "let scripts be the referee" principle.

- Linting passes
- Tests pass
- Type checking passes
- SAST scan (if tooling available)

If deterministic layer FAILs after agent reviews PASS, the card goes back to Code with **deterministic findings** (not the agents' findings — the deterministic layer's output is the authority).

### Review Gate: AND-gated, retry-bounded

All three reviewers must PASS, AND the deterministic layer must PASS. If any FAIL:
- Findings are appended to the card context
- Card goes back to Code with specific failure notes
- Max 3 retries, then escalate to Requires Approval

### Closed loop (NEW framing)

When a reviewer keeps catching the same mistake class across cards, the **fix is not per-file**. The orchestrator updates the rulebook: AGENTS.md, the relevant skill, or a sub-skill. The affected batch regenerates. The reviewer no longer needs to find it next time — the prevention is in the source-of-truth instructions.

This is the migration blog's "**repeated miss → one sentence in the rulebook → batch regenerates**" pattern.

### Shadow mode for new reviewers

New review agent types start in shadow — they post comments but don't block. After N successful runs where a human confirms accuracy, they become gating. The orchestration skill tracks shadow-mode trust on the board.

---

## Stage 4: DEPLOY

### Worker: deploy profile / subagent

**What happens:**
- Deploy to staging environment
- Smoke tests
- DAST-like scan (operations-research subagent pointed at staging URL)
- If P0/P1: human approval gate before production
- If P2/P3: auto-deploy with sampling

### Toolset: terminal, file, web (for hitting staging endpoints)

**Pitfall — this is the highest-risk stage.** Deploy should be a separate profile with minimum permissions: can deploy to staging, can run smoke tests, CANNOT modify code, CANNOT access production without human approval.

---

## Stage 5: MONITOR

### Worker: Incident Response profile (separate Hermes profile)

**What happens:**
- Cron-driven: scans logs, watches for anomalies
- Opens cards on the SDLC board for issues found
- Has exactly 3 permissions: read logs, write docs, post to Telegram
- CANNOT write code, cannot deploy, cannot access other profiles
- Separate fixer agent (software-engineer) handles the actual code change

**This is the hardest boundary in the system.** The monitor agent identifies problems but cannot fix them. A separate agent fixes them and a third agent reviews. This is the "blast radius containment" principle applied to production.

### Profile config:
```yaml
# Incident response profile — minimum permissions
disabled_toolsets: [computer_use, terminal, file_write, delegation]
enabled_toolsets: [web, file_read, kanban]
```

### Cron schedule:
- Log scan: every 15m
- Dependency audit: daily
- Secrets scan: every 4h

---

## Stage 6: GOVERNANCE

### Profile: SDLC Orchestrator (me, default profile)

**What happens:**
- Risk-tier the board (P0 = human must approve, P3 = auto-merge)
- Shadow mode for new review agents
- Sample completed cards for human review (e.g., 10% of P2, 100% of P0)
- Dashboard metrics: cards/week, review pass rate, retry rate, time-in-stage
- Every state change committed to git (audit trail)
- Every agent action logged (session DB + board commits)
- Agents treated as insider threat — alerts when they act out of alignment

### Metrics dashboard (board header):
```markdown
## SDLC Metrics
- **Cards this week:** N
- **Review pass rate:** X% (spec: Y%, security: Z%, quality: W%)
- **Retry rate:** X%
- **Avg time in stage:** Plan: Xh, Code: Yh, Review: Zh, Deploy: Wh
- **Stale cards (>3d):** N
- **Human escalations this week:** N
```

---

## New Profiles Required

| Profile | Purpose | Toolsets | Gateway? | Cron? |
|---------|---------|----------|----------|-------|
| `sdlc-orchestrator` | Default profile — plan, dispatch, govern | all | Yes (Telegram) | Yes |
| `sdlc-developer` | Code generation (software-engineer worker) | terminal, file | No | No |
| `sdlc-security-reviewer` | Security review subagent | file, terminal | No | No |
| `sdlc-spec-reviewer` | Spec compliance subagent | file | No | No |
| `sdlc-quality-reviewer` | Code quality subagent | file, terminal | No | No |
| `sdlc-deployer` | Staging deploy + smoke tests | terminal, file, web | No | No |
| `sdlc-monitor` | Incident response | web, file_read, kanban | Yes (Telegram) | Yes |

**Implementation note:** The three review agents don't need separate Hermes profiles — they run as subagents via `delegate_task` from the orchestrator. Only the long-lived roles (orchestrator, monitor) need persistent profiles. The developer and deployer could also be subagents, or could be profiles if they need cron/gateway.

---

## New Skills Required

### 1. `sdlc-orchestration` (the main skill)
- SDLC board management
- Card decomposition (adapted from cos-orchestration)
- Worker dispatch (adapted from cos-orchestration)
- Multi-reviewer dispatch and gate logic
- Risk tiering logic
- Escalation protocol
- Metrics computation

### 2. `sdlc-security-review`
- OWASP Top 10 checklist
- Credential exposure patterns
- Input validation patterns
- Auth boundary analysis
- Dependency audit commands
- Output format: file:line findings

### 3. `sdlc-code-generation`
- TDD workflow (from test-driven-development)
- AGENTS.md loading
- Security skill loading
- Conventional commits
- Closed-loop: if review found X, update AGENTS.md

### 4. `sdlc-deploy`
- Staging deploy commands
- Smoke test patterns
- DAST scan dispatch
- Human approval gate protocol

### 5. `sdlc-monitor`
- Log scanning patterns
- Anomaly detection heuristics
- Card creation from alerts
- Permission boundary enforcement

---

## Board Structure

The SDLC board is a **Hermes kanban board** (`sdlc`). All operations go through `kanban_create`, `kanban_comment`, `kanban_complete`, `kanban_list`. The board config lives in Hermes state, not in the wiki.

```
hermes kanban list          # View all cards on the sdlc board
hermes kanban show <id>     # View a card's full body + comments
```

Archive state is the git history of the project repo (`~/git/sdlc-demo`), not wiki files. Every card completion is a commit; every closed-loop edit to AGENTS.md is a commit.

### Card Template (extends CoS card format with SDLC-specific fields):

```markdown
### SDLC-NNN: [Title]
**Status:** Backlog | Plan | Code | Test/CI | Deploy | Monitor | Done
**Risk:** P0 | P1 | P2 | P3
**Worker:** software-engineer
**Created:** YYYY-MM-DD

**Feature:** [One sentence — what the user gets]

**Goal:** [What must be true when Done]

**Tech Stack:** [Languages, frameworks, services touched]

**Context:** [File paths, AGENTS.md refs, related cards, constraints]

**Deliverable:** [Branch name, PR, or patch file]

**Definition of Done:**
- [ ] Tests pass (coverage >= X%)
- [ ] Security review PASS
- [ ] Spec compliance PASS
- [ ] Code quality PASS
- [ ] Linting PASS
- [ ] Deployed to staging, smoke tests PASS
- [ ] [If P0/P1] Human approved
- [ ] Committed and pushed

**Review Results:**
- Security: [PASS/FAIL] — [findings summary]
- Spec: [PASS/FAIL] — [gap summary]
- Quality: [PASS/FAIL] — [issue summary]

**Retries:** 0/3

**Assigned:** YYYY-MM-DD
**Completed:** [blank until Done]
```

---

## Comparison: CoS vs SDLC

| Dimension | CoS System | SDLC System |
|-----------|-----------|-------------|
| Scope | General task management | Software delivery |
| Workers | content-growth, software-engineer, operations-research | software-engineer, 3 reviewers, deployer, monitor |
| Review | Single QC pass | 3 parallel reviews AND-gated |
| Risk model | Priority (P0-P3) | Risk tier + human gate placement |
| Deploy stage | None | Staging + smoke + DAST + approval |
| Monitor | None | Cron-based incident response |
| Closed loop | None | Bug class → AGENTS.md → future code |
| Audit trail | Kanban comments + session DB | Kanban comments + session DB + Langfuse scores + git history |

---

## Implementation Phases

All six phases were completed July 2026 across 8 SDLC cards (SDLC-001 through SDLC-008). The system is operational, not theoretical.

### Phase 1: Core SDLC Orchestration ✅
- Created `sdlc-orchestration` skill (workers/sdlc-orchestration/SKILL.md)
- Created kanban board `sdlc` (Hermes kanban, not wiki)
- Implemented card template with SDLC-specific fields
- Implemented risk tiering logic (P0-P3)
- Ported card decomposition from cos-orchestration

### Phase 2: Multi-Reviewer Pattern ✅
- Created `sdlc-security-review` skill
- Implemented spec compliance + code quality review logic
- Implemented AND-gate (all three must pass)
- Implemented retry loop (max 3, then escalate)
- Proven via SDLC-006 (deactivate endpoint) — first pass PASS on all 3 reviewers

### Phase 3: Closed Loop ✅
- Implemented AGENTS.md update on review findings (SDLC-001 security rule)
- Implemented skill patching from discovered bug classes
- Verified: type-coercion bug found → AGENTS.md updated → SDLC-002 avoided it
- Verified: rollback-crash bug → app.py patched → SDLC-008 closed the loop

### Phase 4: Deploy Stage ✅
- Created `sdlc-deploy` skill
- Implemented staging deploy workflow (docker compose)
- Implemented smoke tests
- Implemented human approval gate for P0/P1 (Telegram DMs, structured approval format)
- Staging at port 5001, production at port 5002

### Phase 5: Monitor Stage ✅
- Created `sdlc-monitor` skill + separate Hermes profile
- Implemented log scanning cron (15m), dep audit (daily), secrets scan (4h)
- Implemented card creation from alerts (SDLC-004, SDLC-005 auto-created)
- Verified permission boundary (monitor cannot deploy)
- Recurrence dedup proven (SDLC-005)

### Phase 6: Governance ✅
- Implemented Langfuse score conventions (7 score types)
- Implemented inline governance (closed-loop check after each Test/CI stage)
- Implemented score-driven process edits
- Agent-action audit trail via session DB + kanban comments + git history

---

## Risks and Open Questions

1. **Subagent reliability** — Three review subagents per card means 3x the chance of a subagent hallucinating a finding or missing a real one. Shadow mode mitigates but doesn't eliminate. Start with high overlap (all three reviewers) and reduce as confidence grows.

2. **Context budget** — Each review subagent needs enough context to be useful. A 500-line PR may need 2000+ lines of surrounding code for context. The orchestrator must curate context carefully.

3. **Deploy safety** — The deploy stage is where real damage happens. Start with staging-only deploys. Add production deploys only after the human gate is proven.

4. **Monitor vs. Fixer separation** — This is the most important boundary. The monitor profile must be genuinely unable to deploy. Test this by having it try.

5. **Profile proliferation** — How many separate Hermes profiles is too many? The three reviewers don't need profiles (they're subagents). The developer and deployer could be subagents too. Only the orchestrator and monitor genuinely need persistent profiles. Start lean.

6. **Integration with existing CoS** — The two systems should share workers where possible (software-engineer is the same worker type). But the SDLC review process is fundamentally different from CoS QC. Different board, different skill, different gates.

---

## Current State (2026-07-26)

All six implementation phases complete. 8 cards through the system. The SDLC orchestration, multi-reviewer AND-gate, closed-loop editing, deploy pipeline, monitor profile, and Langfuse governance are all operational.

**Open work:**
- README endpoint table is missing `POST /api/users/<id>/deactivate`
- Shadow mode for new reviewer types (implemented in code, hasn't been exercised yet)
- Metrics sampling (10% P2, 100% P0 — governance hook exists, needs a cron trigger)
- `PATCH /api/users/<id>` endpoint (RESTful update)
- `DELETE /api/users/<id>` endpoint (RESTful delete)
- Email format validation hardening (current: only checks for `@`)
