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
- No hardcoded secrets — use env vars

## Security Rules (from SDLC-001 closed loop)
- Type-coercion check: `isinstance(x, int)` accepts `bool`. Use `type(x) is int` or `isinstance(x, int) and not isinstance(x, bool)`.
- Validate email as a string: always check `isinstance(email, str)` first.
- Input validation at the API boundary before database operations.

## Trace Conventions

Every card dispatched into this project is tracked in Langfuse (http://localhost:3000, project "Mac Mini"). Workers and reviewers must:

1. **Capture the trace ID** from your own run. Hermes auto-exports traces to Langfuse via OpenTelemetry. The trace is tagged with `["hermes", "langfuse"]` and appears automatically.

2. **Emit structured metadata on completion.** When `kanban_complete()` is called, include in metadata:
   - `trace_id`: the active trace for observability
   - `tests_run`, `tests_passed`: numeric
   - `files_changed`: list of absolute paths
   - `decisions`: list of design decisions made

3. **Keep `kanban_complete(summary=...)` under 120 characters.** The body goes in a kanban comment first if it's long.

4. **Reviewers reference their trace.** When a reviewer dispatches, annotate their verdict with the trace ID so the orchestrator can later score `sdlc_reviewer_thoroughness` and `sdlc_first_pass_pass`.

Example:
```python
kanban_complete(
    summary="added rate limiter with token bucket, 14/14 tests",
    metadata={
        "trace_id": "session_20260726_abc123",
        "tests_run": 14,
        "tests_passed": 14,
        "files_changed": ["/Users/markcastillo/git/sdlc-demo/app.py",
                          "/Users/markcastillo/git/sdlc-demo/tests/test_api.py"],
        "decisions": ["token bucket with user_id key, IP fallback for anon"]
    }
)
```

## Known CVE Mitigations

### CVE-2025-71176 — pytest insecure tmpdir (GHSA-6w46-j5rx-g56g)
- **Risk:** P2 — dev-only, local attack vector, no active exploitation
- **Affected:** pytest ≤ 9.0.2 (all versions; no fix released yet)
- **Mitigation:** `pytest.ini` + `tests/conftest.py` override basetemp to `.pytest_tmp/` (0o700) instead of `/tmp/pytest-of-{user}`
- **Scope:** Local dev only. CI/Docker environments have ephemeral filesystem isolation
- **Date applied:** 2026-07-26
- **Action on upstream fix:** remove `tests/conftest.py` basetemp override and this section

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