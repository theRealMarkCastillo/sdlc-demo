# Security Review: Card t_9c0bf329 — Credential Rotation (commit ca5b2ea)

**Verdict: FAIL**
**Reviewer: sdlc-security-review subagent**
**Date: 2026-07-26**

## Summary

No CRITICAL or HIGH exploitable vulnerabilities in the credential rotation itself. The change is a net security improvement — it removes hardcoded `sdlc_pass` from version control. Two pre-existing MEDIUM issues were left unaddressed, and three new LOW deployment footguns were introduced. No injection, auth-bypass, or data-leak paths exist in the changed credential flow.

---

## Findings

### M-1: Health endpoint leaks infrastructure details (MEDIUM)

- **File:** app.py:30
- **Pre-existing:** Yes
- **Exploit:** `GET /health` returns `str(e)` on DB failure. Verified psycopg2 `OperationalError` messages include host, port, username:
  ```
  connection to server at "localhost" (::1), port 5433 failed:
    FATAL: password authentication failed for user "sdlc_user"
  ```
  Password is NOT leaked (confirmed via live test). But host/port/username enable network reconnaissance.

### M-2: Database ports exposed on 0.0.0.0 (MEDIUM)

- **Files:** docker-compose.prod.yml:11, docker-compose.staging.yml:11
- **Pre-existing:** Yes
- **Exploit:** `ports: - "5434:5432"` and `"5433:5432"` bind to all interfaces. PostgreSQL reachable directly from any network. Attacker can brute-force without going through the app.

### L-1: Missing .env silently propagates empty credentials (LOW, NEW)

- **Files:** docker-compose.prod.yml:5,20, docker-compose.staging.yml:5,20
- **Introduced by this commit:** Yes
- **Exploit:** `env_file: .env` + no .env in repo → `${POSTGRES_PASSWORD}`/`${DB_PASS}` → empty strings. Postgres 16-alpine refuses to start (mitigation). App gets `fe_sendauth: no password supplied`. Risk in misconfiguration/older images.

### L-2: Test module sets credential defaults at import time (LOW, NEW)

- **File:** tests/test_api.py:10-11
- **Introduced by this commit:** Yes
- **Exploit:** `os.environ.setdefault("DB_USER", "sdlc_user_test")` runs at import. If imported in non-test context, sets test credentials globally. Low probability, defense-in-depth violation.

### L-3: DATABASE_URL with literal `***` password (LOW, PRE-EXISTING)

- **Files:** docker-compose.prod.yml:31, docker-compose.staging.yml:31
- **Pre-existing:** Yes (from commit 2ca436e)
- **Exploit:** `DATABASE_URL: postgresql://sdlc_user:***@db:5432/sdlc_demo` has `***` as literal password. entrypoint.sh → alembic upgrade head → auth fails → container crashes. Docker deployments broken. Commit touched these lines without fixing.

### L-4: .env.example weak placeholder values (LOW, NEW)

- **File:** .env.example:14,17
- **Introduced by this commit:** Yes
- **Risk:** `change-me-to-a-strong-random-value` — weak if copy-pasted. Acceptable for a template with remediation comment (`openssl rand -hex 32`).

### L-5: README stale — claims .env not needed (LOW, NEW)

- **File:** README.md:119
- **Introduced by this commit:** Yes
- **Risk:** "no .env needed for local development" — now false after DB_PASS moved to ${DB_PASS}. Operator following README gets broken deployment.

---

## Verified Safe

- **SQL injection via credentials:** Impossible — credentials flow to psycopg2.connect() keyword args, never interpolated into SQL. All queries use %s parameterized placeholders.
- **Auth bypass via missing credentials:** Impossible — os.environ[] raises KeyError at import, app crashes before serving requests.
- **.env committed to git:** Confirmed .env in .gitignore since initial commit. No .env in git history.
- **Hardcoded secrets elsewhere:** Searched entire repo. Only `sdlc_user` (username, not secret) remains. All password instances removed from compose files.
- **Password in error messages:** Verified — psycopg2 OperationalError does NOT include password value.

---

## Tally

| Severity | Count | New | Pre-existing |
|----------|-------|-----|--------------|
| CRITICAL | 0 | 0 | 0 |
| HIGH | 0 | 0 | 0 |
| MEDIUM | 2 | 0 | 2 |
| LOW | 5 | 3 | 2 |
