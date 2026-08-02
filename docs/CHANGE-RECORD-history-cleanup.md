# CHANGE RECORD: SDLC-NNN — Purge hardcoded credentials from git history

**Card:** t_5aba022d (root) / t_c05558a7 (purge) / t_ee597242 (reviews)
**Date:** 2026-08-01
**Risk:** P1 (HIGH) — type=secret | file=git-history | hash=ca5b2ea~1
**Status:** Ready for force-push approval (see "Outstanding Step")

---

## 1. Summary

Hardcoded database credentials (`sdlc_user` / `sdlc_pass`) were committed
across the repository's git history. A rotation commit (ca5b2ea) cleaned
HEAD, but the credentials remained recoverable from ~30 prior commits via
`git log -p`. This change record summarizes the history rewrite that
removes them, the verification performed, and the reviews obtained.

## 2. What was changed

| Artifact | Change |
|----------|--------|
| Git history (all 13 branches, 71 commits) | `sdlc_pass` → `REDACTED`, `sdlc_user` → `REDACTED` via `git filter-repo --replace-text` |
| `docker-compose.prod.yml` | `POSTGRES_USER` / `DB_USER` / healthcheck now use `${DB_USER}` interpolation instead of literal `sdlc_user` |
| `docker-compose.staging.yml` | Same interpolation fix |
| `.env.example` | `DB_USER` placeholder (`change-me-db-user`) instead of `sdlc_user` |
| `tests/test_secrets.py` | Removed unused `tempfile` import (ruff F401) |

### Why the compose fix was required before the purge

Filter-repo rewrites **every** commit, including HEAD. If the compose
files had kept the literal `sdlc_user`, the rewrite would have produced
`POSTGRES_USER: REDACTED` at HEAD — a broken deployment config (the DB
user would literally be named "REDACTED"). Interpolating `${DB_USER}`
from `.env` (per AGENTS.md: "compose files must reference env vars, not
literal credentials") keeps HEAD functional and removes the literal from
history. The live `.env` files already define `DB_USER` and are
gitignored (mode 600).

## 3. Verification

### 3.1 Secrets audit — filtered repo (`/tmp/sdlc-filtered3.git`)

| Check | Result |
|-------|--------|
| `sdlc_pass` occurrences in `git log --all -p` | **0** |
| `sdlc_user` occurrences in `git log --all -p` | **0** |
| Commit count preserved | **71 / 71** |
| Branches preserved | **13 / 13** |
| `REDACTED` replacements | 118 (112 literal + compose/test contexts) |
| AWS `AKIA*` / GitHub `ghp_*` / Slack `xox*` / OpenAI `sk-*` / private keys | 0 |
| `test-api-key-for-sdlc-demo` (synthetic test fixture, documented zero-exposure) | present only in tests |

### 3.2 Structural integrity

- Original mirror clone: `/tmp/sdlc-audit-20537.git` (70 commits, pre-fix)
- Filtered repo HEAD tree differs from original **only** in the 8
  credential-bearing files (`.env.example`, compose files, README,
  docs/DEPLOYMENT.md, spec-compliance-review.md, test fixtures,
  `.hermes/artifacts/t_9c0bf329-security-review.md`) — expected.
- Filtered `fix/rotate-staging-secrets` branch includes the lint fix and
  compose interpolation (verified: `import tempfile` count = 0).

### 3.3 Deterministic layer (`scripts/deterministic-check.sh`)

| Tool | Result |
|------|--------|
| ruff | PASS (after F401 fix) |
| mypy | PASS |
| bandit | PASS (with pyproject.toml skips B101/B104/B110/B608 — documented) |
| pytest (unit: test_secrets, test_deploy, test_monitor) | 40/40 PASS |
| pytest (test_api) | Requires live server (`TEST_URL=http://localhost:5001`) — environmental, documented in README |

## 4. Reviews

| Review | Verdict | Notes |
|--------|---------|-------|
| Security | **PASS** (conditional on push) | 0 secret matches in filtered history; live credentials rotated 2026-07-26 (t_4d1dcee8); no API keys/tokens/private keys in history; residual = force-push pending |
| Spec conformance | **PASS** | DoD coverage: filter-repo applied to all commits ✓, history audit clean ✓, .env rotated ✓, deterministic layer ✓; AGENTS.md compose-interpolation rule satisfied |
| Quality | **PASS** | ruff/mypy/bandit clean; unit tests pass; F401 regression fixed; no dead code introduced |

## 5. Backup & rollback

- Original remote mirror (pre-purge): `/tmp/sdlc-audit-20537.git`
- Original local backup (2026-07-27): `/tmp/sdlc-demo-backup-20260727_211631`
- Restore path: push the backup mirror back to origin.

## 6. Outstanding step (needs human approval)

The filtered history has **not** been force-pushed to origin. The remote
still contains the credentials (42 `sdlc_pass` + 64 `sdlc_user` matches
in `origin/main` history as of 2026-08-01). This is the single remaining
step to close the incident:

```bash
cd /tmp/sdlc-purge-v2.git && git remote add origin https://github.com/theRealMarkCastillo/sdlc-demo.git
git push --force --mirror origin
```

Post-push verification:

```bash
cd ~/git/sdlc-demo && git fetch origin && git reset --hard origin/main
git log --all -p | grep -c "sdlc_pass"   # must be 0
git log --all -p | grep -c "sdlc_user"   # must be 0
```

**Status update (2026-08-01):** the prerequisite merge is DONE —
`fix/rotate-staging-secrets` (compose interpolation + ruff fix + this
change record) was merged into main as `095c614`, so HEAD's compose
files use `${DB_USER}` interpolation and survive the purge intact.
The filtered artifact at `/tmp/sdlc-purge-final.git` is rebuilt from
that state: 0 secret matches (content + commit messages), 74 commits,
13 branches preserved. Only the force-push above remains.
