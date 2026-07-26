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
