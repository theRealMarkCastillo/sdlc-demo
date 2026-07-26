# AGENTS.md — SDLC Demo Project

> You are a software engineer worker in the SDLC system. Follow TDD always.

## Tech Stack
- Python 3.12+
- Flask 3.x
- PostgreSQL
- pytest + requests for testing
- Docker + docker compose for deployment

## Code Conventions
- Type hints on all functions
- Docstrings on all public functions
- Validation functions should raise ValueError with descriptive messages
- RESTful API design: proper status codes, JSON error responses
- Never log PII
- No hardcoded secrets — use env vars, no defaults for credentials (`os.environ.get("DB_USER")` — no second argument)

## Security Rules (from SDLC-001 closed loop)
- Type-coercion check: `isinstance(x, int)` accepts `bool`. Use `type(x) is int` or `isinstance(x, int) and not isinstance(x, bool)`.
- Validate email as a string: always check `isinstance(email, str)` first.
- Input validation at the API boundary before database operations.

## Security Rules (from SDLC-009 / t_9c0bf329 closed loop)
- Credential env vars must NOT have defaults. `os.environ.get("DB_USER", "default")` defeats the secret rotation — set defaults only for non-sensitive config (host, port, dbname).
- `.env` files must be in `.gitignore`; provide `.env.example` with placeholder values for local dev.
- Docker compose files must reference env vars, not literal credentials. Use `${DB_USER}` interpolation from a `.env` or `secrets:` block.
- Tests must set required credential env vars at module load (before importing the app) so unit tests don't depend on ambient shell state.

## Security Rules (from SDLC-012 / t_481f1498 closed loop)
- **LIKE/ILIKE wildcards MUST be escaped in user-supplied search terms.** PostgreSQL interprets `%` (any sequence) and `_` (any single char) as wildcards inside bound parameter values. Before building a LIKE pattern, escape them: `safe = q.replace("%", r"\%").replace("_", r"\_")`. A bare `?q=%` must not match every row.
- **Search inputs need validation at the API boundary.** Strip whitespace and cap length (`q = q.strip()[:200]`). Whitespace-only queries should behave as "no filter," not as literal whitespace searches.
- **Case-insensitive search demands a case-variation test.** If the implementation uses ILIKE, a test must prove that `?q=lowercase` matches `UPPERCASE` data.

## Trace Conventions

Every card dispatched into this project is tracked in Langfuse (http://localhost:3000, project "Mac Mini"). Scores are emitted retroactively by the orchestrator after each stage transition — the orchestration skill handles this.

1. **Emit structured metadata on completion.** When `kanban_complete()` is called, include in metadata:
   - `trace_id`: the active trace for observability
   - `tests_run`, `tests_passed`: numeric
   - `files_changed`: list of absolute paths
   - `decisions`: list of design decisions made

2. **Keep `kanban_complete(summary=...)` under 120 characters.** The body goes in a kanban comment first if it's long.

3. **Reviewers reference their trace.** When a reviewer dispatches, annotate their verdict with the trace ID so the orchestrator can later score `sdlc_reviewer_thoroughness` and `sdlc_first_pass_pass`.

4. **Scores are in Clickhouse, not OpenTelemetry.** The orchestrator emits scores directly to the Langfuse API. Hermes does NOT auto-export traces via OpenTelemetry — score emission is manual via the `governance_scores.py` script. Do not assume trace IDs appear automatically.

Example:
```python
kanban_complete(
    summary="added rate limiter with token bucket, 14/14 tests",
    metadata={
        "trace_id": "session_20260726_abc123",
        "tests_run": 14,
        "tests_passed": 14,
        "files_changed": ["app.py", "tests/test_api.py"],
        "decisions": ["token bucket with user_id key, IP fallback for anon"]
    }
)
```

## Score Conventions (see sdlc-orchestration skill)

Your work is scored on these Langfuse metrics:

| Score | What | Range |
|-------|------|-------|
| `sdlc_first_pass_pass` | Card passed all 3 reviewers on first attempt | BOOLEAN |
| `sdlc_reviewer_agreement` | How much reviewers agreed | unanimous=1 / tiebreaker=2 / partial=3 |
| `sdlc_retries_used` | How many retries needed | 0-3 |
| `sdlc_stage_latency_seconds` | Time in each stage | NUMERIC |
| `sdlc_human_approved` | Human approved the deploy | BOOLEAN |
| `sdlc_deploy_succeeded` | Deploy completed cleanly | BOOLEAN |
| `sdlc_reviewer_thoroughness` | Review quality | shallow=1 / adequate=2 / thorough=3 |

Scores are emitted automatically by the orchestrator at each stage transition. You don't need to score yourself — just emit trace IDs and structured metadata, and the orchestrator handles the rest.