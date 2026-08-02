# SDLC-INV-001 — Kanban Default Board Routing + CLI Body-Loss Investigation

**Status:** INVESTIGATED + FIXED 2026-08-01
**Card:** t_af0e77bf (sdlc board)
**Files touched:** `~/.hermes/.env` (one line removed), `~/.hermes/kanban/current` (pointer), skills (`cos-orchestration`, `hermes-kanban-dispatch`, `wiki-operations`)

---

## Executive summary

Two distinct bugs were reported, and the original investigation had misattributed
both. The real root causes, proven by reproduction:

1. **Board routing ("default board has no backing DB")** — the `default` board
   HAS a backing DB; the original diagnosis looked at the wrong file. The real
   routing bug is a stale `HERMES_KANBAN_BOARD=sdlc` pin in `~/.hermes/.env`,
   which the CLI loads with `override=True` at every startup — so it beat both
   the `current` pointer file AND shell-exported env vars. `boards switch`
   appeared dead because the env pin outranked the file it writes.

2. **Body loss (`length(body)=0`)** — NOT a Hermes/CLI bug at all. It is a
   shell expansion trap in the skill-documented batch pattern:
   `BODY="$(cat /tmp/card.md)" hermes kanban create ... --body "$BODY"` expands
   `$BODY` to EMPTY before the assignment applies, so the CLI receives
   `--body ""`. Every affected card (3 COS victims + 10 LI cards) was created
   with exactly this shape. The CLI and `create_task()` are both clean —
   proven by round-trip tests with tricky content.

Both fixed. The `.env` pin is removed; the `current` pointer now governs
routing (set to `sdlc`, the operational default), and `boards switch` works
again. Body round-trips through the CLI with the correct two-step shell
pattern.

---

## Symptom 1 — Default board routing

### Reported symptoms

- `~/.hermes/kanban/kanban.db` is 0 bytes (claimed: "legacy fossil")
- `~/.hermes/kanban/boards/default/` does not exist
- `hermes kanban boards list` shows `default (empty)` but "no actual DB"
- `hermes kanban boards switch default` says success but `boards list` still
  shows sdlc as current ("precedence bug")
- `hermes kanban create` without `--board` lands on sdlc even when `current`
  file points elsewhere

### What is actually true

The `default` board's DB path is **not** `~/.hermes/kanban/kanban.db`.
Per `kanban_db_path()` in `hermes_cli/kanban_db.py`:

```python
if slug == DEFAULT_BOARD:
    return kanban_home() / "kanban.db"   # = ~/.hermes/kanban.db  (NOT inside kanban/)
```

The REAL default board DB is `~/.hermes/kanban.db` (root of HERMES_HOME) —
114 KB, full schema, live. It exists and works (its only task is an archived
verification card `t_de5b026a` created during this investigation — proof the
round-trip works). The 0-byte files
`~/.hermes/kanban/kanban.db`, `~/.hermes/kanban/default.db`,
`~/.hermes/kanban/sdlc.db` are **stale artifacts from a pre-boards-era naming
scheme** (`kanban/<slug>.db`) that no current code reads. `boards/default/`
doesn't exist because `default` intentionally keeps its DB at the legacy root
path (back-compat, per `kanban_db.py` docstring lines 20-23).
`list_boards()` always synthesizes `default` first — that's why it shows `(empty)` (it truly
had 0 tasks at report time; everything was being routed to sdlc). Verified 2026-08-01:
`boards list` now shows real per-board counts, `default` included.

### Root cause — the `.env` pin

`~/.hermes/.env` line 496 contained:

```
HERMES_KANBAN_BOARD=sdlc
```

`hermes_cli/main.py:691` calls `load_hermes_dotenv()` at every CLI startup,
and `env_loader.py` loads `~/.hermes/.env` with `override=True` — meaning the
`.env` value **overrides stale shell-exported values**, including values a
user sets on the command line. Board resolution (`get_current_board()` in
`kanban_db.py`) checks, in order: env var → `current` file → default. So the
pin made `sdlc` win every resolution:

- `boards switch default` writes the `current` file → but env pin outranks it
- `HERMES_KANBAN_BOARD=default hermes kanban ...` → .env override=True
  clobbers the shell export back to sdlc
- `env -u HERMES_KANBAN_BOARD ...` → .env re-sets it inside the process

The skill documentation ("the three documented escape hatches all failed")
was accurate — all three failed because of the `.env` override, not because
of missing infrastructure.

### Fix (applied + verified)

1. Removed `HERMES_KANBAN_BOARD=sdlc` from `~/.hermes/.env`.
2. Set `~/.hermes/kanban/current` to `sdlc` — preserving the operational
   default (bare `hermes kanban` calls hit sdlc) but through the mechanism
   `boards switch` can actually override.
3. Verified:
   - `boards list` in a clean env shows sdlc as current ✓
   - `boards switch research` → `boards show` reports research ✓
   - `boards switch sdlc` → back to sdlc ✓
   - bare `create` (no `--board`) lands in `boards/sdlc/kanban.db` with body ✓
   - `HERMES_KANBAN_BOARD=default hermes kanban create ...` now routes to
     `~/.hermes/kanban.db` (the real default DB) with body preserved ✓

### Note on the cron jobs

The three SDLC cron prompts (`sdlc-secrets-scan`, `sdlc-dep-audit`,
`sdlc-governance`) reference `HERMES_KANBAN_BOARD=sdlc` inline in their
prompts — that is the correct, explicit form (a shell export that now takes
effect since .env no longer overrides). They do not depend on the .env pin.
All three are currently disabled (enabled=False) anyway.

### Worker-context wrinkle: `HERMES_KANBAN_DB` pin beats `--board` (found 2026-08-01)

Reproducing the fix from inside a **dispatcher-spawned worker** (this card's own run)
exposed a second, quieter routing layer: the dispatcher injects
`HERMES_KANBAN_DB=<task-board>/kanban.db` into every worker's env. `kanban_db_path()`
honours that env var **first** — before the `board=` argument, the `--board` ContextVar,
and `HERMES_KANBAN_BOARD`. Consequences inside a pinned worker:

- `hermes kanban boards create <slug>` creates the board dir + metadata but the CLI's
  printed "DB path" resolves to the **pinned** board's DB (misleading), and
  `init_db(board=<slug>)` initializes the pinned DB (no-op), leaving the new board with
  an empty zombie `kanban.db` (no tables).
- `hermes kanban --board <slug> create ...` passes the `--board` existence check but
  still writes rows into the **pinned** DB. Verified live: two `INV-TEST` cards created
  with `--board invtest-*` landed in `boards/sdlc/kanban.db` (bodies intact — the body
  fix holds regardless of routing).
- The documented Python helper (`HERMES_KANBAN_BOARD=<slug>` + `connect_closing(board=)`)
  is likewise overridden — `HERMES_KANBAN_DB` wins at the path level.

This is **by design** for workers (they must stay on their task's board — "defense in
depth" per `kanban_db_path()` docstring), but the CLI does not warn about it, so any
worker/delegate session that tries to create a card on another board hits silent
misrouting. **Escape hatch (verified):** strip both pins for cross-board CLI work from a
worker — `env -u HERMES_KANBAN_BOARD -u HERMES_KANBAN_DB hermes kanban ...`. In a normal
interactive shell neither pin is present, which is why the earlier verification passed.

---

## Symptom 2 — Body loss via CLI

### Reported symptom

`hermes kanban create "TITLE" --body "$BODY"` (shell-interpolated) lands with
`length(body)=0` in the SQLite row. Verified for cards `t_ccd8eea2`,
`t_3fead753`, `t_b957eca6` (archived on sdlc), and retroactively for all ten
LI cards (`t_76efb987` … `t_31d68ff5`) created 2026-07-31 with the same shape.

### Root cause — shell expansion order, NOT a Hermes bug

The skill-documented "working batch-create pattern" was:

```bash
BODY="$(cat /tmp/card1.md)" hermes kanban create "LI-001: ..." --body "$BODY" ...
```

In POSIX shells, `VAR="$(...)" cmd --body "$VAR"` — the `$VAR` in the
argument list is expanded by the shell **before** the assignment applies.
`VAR=...` only affects the environment of the child process; it does NOT make
`$VAR` expand to the new value in the same command line. So `--body "$BODY"`
receives the **old (empty)** value. This is a well-known shell footgun.

Proven with a 5-shape test script (`/tmp/shell_semantics_test2.sh`):

| Shape | Result |
|---|---|
| `env -u X BODY="$(cat f)" cmd --body "$BODY"` (documented pattern) | `--body ` — EMPTY |
| `BODY="$(cat f)" cmd --body "$BODY"` (one-liner prefix) | `--body ` — EMPTY |
| `BODY="$(cat f)"` (own line), then `cmd --body "$BODY"` | full content ✓ |
| `cmd --body "$(cat f)"` (inline substitution) | full content ✓ |
| Python helper (`kb.create_task(conn, body=...)`) | full content ✓ |

The CLI itself is clean: `_cmd_create` passes `args.body` straight into
`create_task(conn, body=...)`, which INSERTs it directly (verified in source
and by round-trip). The `--json` output drops the body field entirely, which
compounded the confusion — the two cases (body landed vs. body dropped) were
indistinguishable from JSON output alone, and the original investigator had
to probe SQLite to see `length=0`.

### Fix (documented + verified)

The correct shell patterns, all verified 2026-08-01:

```bash
# Pattern A — two-step (assign on own line, then use):
BODY="$(cat /tmp/card.md)"
hermes kanban --board <slug> create "TITLE" --body "$BODY"

# Pattern B — inline substitution (no variable at all):
hermes kanban --board <slug> create "TITLE" --body "$(cat /tmp/card.md)"

# Pattern C — Python helper (always safe, no shell involved):
python3 - <<'PY'
import os
os.environ["HERMES_KANBAN_BOARD"] = "<slug>"
from hermes_cli import kanban_db as kb
with kb.connect_closing(board="<slug>") as conn:
    tid = kb.create_task(conn, title="TITLE", body=open("/tmp/card.md").read(), created_by="arx")
    print(tid, len(kb.get_task(conn, tid).body or ""))
PY
```

Never write `VAR="$(...)" cmd --body "$VAR"` as a one-liner — it silently
drops the body. Always verify with `SELECT id, length(body) FROM tasks`
after create (the JSON output cannot confirm body content).

---

## Files changed

| Path | Change |
|---|---|
| `~/.hermes/.env` | removed `HERMES_KANBAN_BOARD=sdlc` (line 496) — root-cause fix |
| `~/.hermes/kanban/current` | set to `sdlc` (was `research`, originally pinned by .env) |
| `~/.hermes/skills/workers/cos-orchestration/SKILL.md` | card-creation pattern corrected |
| `~/.hermes/skills/autonomous-ai-agents/hermes-kanban-dispatch/SKILL.md` | routing/body pitfalls corrected |
| `~/.hermes/skills/devops/wiki-operations/SKILL.md` | env-precedence + phantom-board pitfalls corrected |

## Residual notes

- The `default` board is fully functional (0 active tasks; its only task is an
  archived verification card). CoS may legitimately use it now — the "phantom
  stub" theory is retired.
- `companion-reef` board carries a `kanban.db.corrupt.*.bak` cluster from a
  May 2026 corruption incident — unrelated to this investigation, documented
  in `wiki-operations` skill.
- The `.env` pin was added ~2026-07-29 (mtime). It was almost certainly added
  to make bare CLI calls default to sdlc during early SDLC setup — the
  correct way to express that is the `current` file, which is now set.
