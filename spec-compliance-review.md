# SPEC COMPLIANCE REVIEW: t_9c0bf329

**Commit:** ca5b2ea  
**Date:** 2026-07-26  
**Verdict: FAIL** — 2 critical gaps found

---

## DoD Checklist

| # | DoD Item | Status | Evidence |
|---|----------|--------|----------|
| 1 | app.py defaults removed — DB_PASS required, no fallback | ✅ PASS | app.py:12-13: `os.environ["DB_USER"]` and `os.environ["DB_PASS"]` — no `.get()` fallback. KeyError on missing. |
| 2 | docker-compose files reference env_file, not inline values | ⚠️ PASS (partial) | Both compose files have `env_file: .env` (prod:5,29, staging:5,29). DB_PASS uses `${DB_PASS}`. **BUT:** DATABASE_URL (prod:31, staging:31) still has literal `***` password — was never rotated. |
| 3 | .env.example added with placeholders, .env in .gitignore | ✅ PASS | .env.example exists with clear instructions. .gitignore:3 has `.env`. |
| 4 | Password rotated to strong generated value | ❌ FAIL | **No `.env` file exists.** .env.example:14,17 contain `change-me-to-a-strong-random-value` — placeholder, not a generated password. DATABASE_URL in both compose files (prod:31, staging:31) still carries literal `***`. The rotation mechanism is set up but rotation was never executed. |
| 5 | All tests pass with new credential flow | ✅ PASS | 39/39 pass. 5 new credential-validation tests added (test_api.py:619-716). |
| 6 | Security review PASS | ⚠️ UNVERIFIED | No security review evidence in this commit. |
| 7 | Spec compliance PASS | ❌ FAIL | This review. |
| 8 | Code quality PASS | ⚠️ NOT THIS SCOPE | Not reviewed by spec reviewer. |

---

## Critical Findings

### 1. Password rotation incomplete (DoD #4)

**File:** `.env` (does not exist)  
**File:** `docker-compose.prod.yml:31`, `docker-compose.staging.yml:31`  

The infrastructure is correctly set up — env vars, .env.example, .gitignore — but:
- No `.env` file was created with a strong generated password
- `.env.example` has placeholder `change-me-to-a-strong-random-value`, not an actual generated value
- `DATABASE_URL` in both compose files still carries the literal `***` password (pre-existing, but unaddressed)

### 2. Stale documentation (Scope creep / AGENTS.md compliance)

**File:** `README.md:110-118`  

The README environment variables table still documents:
- `DB_PASS | sdlc_pass` — old default that no longer exists
- `DB_USER | sdlc_user` — old default that no longer exists
- "no `.env` needed for local development" — now **false**; `.env` IS required

---

## Scope Analysis

**Files changed (5):** `.env.example`, `app.py`, `docker-compose.prod.yml`, `docker-compose.staging.yml`, `tests/test_api.py`  
**Files missed:** `README.md` (environment variables table not updated)  
**Clean:** No other env vars accidentally changed. Diff is minimal and focused.

---

## Test Verification

- Tests collected: 39
- Tests passed: 39
- New tests added: 5 (test_api.py:619-716)
  - `test_app_crashes_when_db_pass_missing`
  - `test_app_crashes_when_db_user_missing`
  - `test_app_crashes_when_both_credentials_missing`
  - `test_app_infra_vars_keep_defaults`
  - `test_app_imports_cleanly_with_credentials_set`

**Concern:** test_api.py:10-11 uses `os.environ.setdefault("DB_USER", ...)` at module level. Tests that don't explicitly test missing creds run with dummy values, masking real-world startup failures.

---

## Regression Risks

- **Low:** Changed only the two credential lines in app.py (12-13), from `os.environ.get()` with defaults to `os.environ[]`. 
- **Low:** Compose files now require `.env` to be present at compose-time — if `.env` is missing, `docker compose up` will fail with an empty variable warning.
