# SDLC System Integration

This project is built and maintained through the **Hermes SDLC pipeline** — multi-reviewer AND-gate, retry protocol, automated monitor, structured Telegram human gates.

## Where the SDLC system lives

The pipeline itself is **separate from this repo**:

| Component | Location |
|-----------|----------|
| Board | Hermes kanban (`HERMES_KANBAN_BOARD=sdlc`) |
| Skills | `~/.hermes/skills/workers/sdlc*/` |
| Profile | `~/.hermes/profiles/sdlc-monitor/` |
| Plan | `~/.hermes/plans/2026-07-26-hermes-sdlc-architecture.md` |
| Cron scripts | `~/.hermes/scripts/sdlc-*.py` |
| **This project** | `~/git/sdlc-demo/` |

## What the orchestrator does with this repo

When a card reaches the **Code** stage, the orchestrator:

1. Reads this project's `AGENTS.md` (closed-loop rules from earlier cards)
2. Dispatches a worker subagent with goal + DoD + AGENTS.md context
3. Worker writes code, runs tests, commits to this repo's git history
4. Orchestrator dispatches 3 reviewers in parallel
5. AND-gate routes to deploy or retry per [REVIEW-PROCESS.md](REVIEW-PROCESS.md)
6. For P0/P1 cards, waits for human Telegram approval before deploying

## Where the SDLC gets its rules

The orchestrator edits the **rulebook** when patterns recur:

- **Code conventions** → this project's `AGENTS.md`
- **Security findings** → `AGENTS.md` Security Rules section
- **Process thresholds** → `~/.hermes/skills/workers/sdlc-governance/`
- **Tooling changes** → `~/.hermes/scripts/sdlc-*.py`

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full picture.