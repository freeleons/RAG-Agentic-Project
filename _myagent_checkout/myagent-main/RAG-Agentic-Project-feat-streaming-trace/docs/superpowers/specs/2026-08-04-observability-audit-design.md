# Observability Audit Surface — Design

**Date:** 2026-08-04
**Scope:** Backend + frontend audit surface over the existing `run_steps` logging: browse/filter all runs, aggregate health metrics, charts, per-run drill-down and JSON export, token-usage capture. The home-grown LangSmith for MVP requirement 7's "simple way to view a run" — upgraded to a real explorer.
**Decisions made:** every user audits their own runs; admins (via `ADMIN_EMAILS` env) see all users · stats + charts included (recharts) · token usage captured into `run_steps`.

## What already exists (unchanged foundations)

- `record_step()` logs every LLM/tool call to `run_steps` (llm_messages, tool_name, arguments, result, latency_ms).
- `GET /api/runs/<id>` returns one run with full steps incl. `llm_messages` and `pending_action` — remains the drill-down/export payload.
- Per-user isolation via the `Run→Conversation.user_id` join.

## Backend

### Token capture

- `llm.py generate()` additionally returns `"usage": {"prompt_tokens": int|null, "completion_tokens": int|null}` parsed from the chat-completions response's `usage` object (absent/None-safe).
- `record_step()` pops `usage` off the result dict before storing and writes two new nullable Integer columns on `run_steps`: `prompt_tokens`, `completion_tokens` (Alembic migration). Tool-call steps leave them null. The popped `usage` does not appear inside `result` JSON (no duplication).

### Admin model

- Config: `ADMIN_EMAILS` — comma-separated emails, parsed to a lowercase set; documented in `.env.example` (empty default).
- `require_auth` sets `g.is_admin = (g.user.email in ADMIN_EMAILS)`.
- `POST /api/auth/login` response becomes `{token, email, is_admin}`.

### New endpoints (JWT; own-runs scope unless admin)

**`GET /api/runs`** — newest first, paginated.
Query params: `status`, `conversation_id`, `date_from`, `date_to` (ISO dates, inclusive), `page` (default 1), `per_page` (default 20, max 100); admin only: `user_email` (exact match, case-insensitive; ignored for non-admins).
Response:

```json
{
  "runs": [{
    "id": 17, "status": "completed",
    "goal": "first ~80 chars of the user message…",
    "conversation_id": 3, "conversation_title": "VPN ticket",
    "model": "llama3.1:8b", "step_count": 3,
    "total_latency_ms": 5210, "prompt_tokens": 1450, "completion_tokens": 220,
    "created_at": "2026-08-04T…",
    "user_email": "a@b.com"        // present only for admins
  }],
  "total": 42, "page": 1, "per_page": 20
}
```

`step_count` and per-run token sums computed via aggregate subqueries (portable SQL — must work on SQLite for tests and Postgres in dev).

**`GET /api/runs/stats`** — same filters, no pagination.

```json
{
  "total_runs": 42,
  "by_status": {"completed": 30, "failed": 5, "declined": 4, "needs_confirmation": 2, "running": 1},
  "success_rate": 0.77,            // completed / (completed+failed+declined); null if no terminal runs
  "avg_steps": 3.2, "avg_latency_ms": 4890,
  "total_prompt_tokens": 61000, "total_completion_tokens": 9400,
  "tool_usage": {"search_knowledge": 28, "escalate": 6, "create_draft": 5},
  "runs_per_day": [{"date": "2026-08-03", "completed": 12, "failed": 2, "declined": 1, "needs_confirmation": 0}],
  "latency_buckets": [{"label": "<2s", "count": 10}, {"label": "2–5s", "count": 18}, {"label": "5–15s", "count": 11}, {"label": "15s+", "count": 3}]
}
```

Aggregation in SQL where portable; day-grouping and latency bucketing in Python (SQLite-safe). `runs_per_day` covers only days having runs.

**No export endpoint:** the client downloads the existing `GET /api/runs/<id>` payload as a Blob.

## Frontend

### Navigation

`AppPage` AppBar gains MUI `Tabs`: **Chat | Audit** (component state; no router). Chat view is unchanged.

### New module `client/src/audit/`

- **`AuditPage.tsx`** — owns filter state `{status, conversationId, dateFrom, dateTo, userEmail, page}`; on change fetches `/api/runs` and `/api/runs/stats` (independently — one failing doesn't blank the other); passes data down.
- **`StatsCards.tsx`** — six MUI cards: total runs · success rate (%) · avg steps · avg latency · tokens (prompt/completion) · failed+declined count.
- **`ChartsRow.tsx`** — recharts (new dependency): stacked bar "runs per day by status" using the TracePanel status-chip color mapping, and latency histogram from `latency_buckets`. Both in `ResponsiveContainer`; empty data → friendly empty-state text, never blank axes.
- **`RunsTable.tsx`** — filter bar (status select, date pickers as plain `type="date"` inputs, conversation select populated from the user's own `api.listConversations()`; admins filter by user email — a free-text field matched server-side — rather than by conversation) + MUI Table (time, goal, status chip, steps, latency, tokens, conversation; `user_email` column when admin) + `TablePagination`.
- **`RunDrawer.tsx`** — opens on row click; fetches `GET /api/runs/<id>`; renders the existing `TracePanel` read-only (`onConfirm` no-op — confirmations happen only in Chat) plus a **Download JSON** button (client-side Blob, filename `run-<id>.json`).

### Auth context

`AuthContext` stores `is_admin` (+ localStorage key `agent_is_admin`) from the login response and exposes it via `useAuth()`. Admin-only UI renders from the flag; the backend enforces scoping regardless.

### API additions (`api.ts` / `types.ts`)

`api.listRuns(filters) -> RunsPage`, `api.getRunStats(filters) -> RunStats`; types `RunListItem`, `RunsPage`, `RunStats` mirroring the payloads above; `RunDetail` unchanged.

## Error handling

`ApiError` → Snackbar; 401 → logout (existing machinery). Empty list/stats → "No runs match these filters." Unknown statuses render as plain-text chips (existing convention).

## Testing

Backend (pytest, in-memory SQLite, model/tools stubbed):
- `generate()` parses `usage`; `record_step` writes token columns and strips `usage` from stored result.
- List: filters, pagination, ordering; isolation — non-admin sees only own runs and the `user_email` param is ignored; admin sees all runs with the `user_email` response field and can filter by it.
- Stats: success rate, by_status, tool_usage, latency buckets, runs_per_day against seeded runs; empty-DB shape (nulls/zeros, no division errors).

Frontend (Vitest/RTL, fetch stubbed):
- Stats cards render values; charts smoke-render SVG; empty states.
- Table: rows render; admin column only when `is_admin`; filter change refetches; pagination.
- Drawer: row click loads detail, steps render, Download JSON creates a Blob URL (`URL.createObjectURL` spied).
- AuthContext exposes `is_admin` from login.

CI unchanged (existing backend + client jobs cover the new tests).

## Out of scope

Cost-in-dollars estimates, live/streaming updates, eval-set scoring integration (docs/eval.md stays manual), admin management UI (env var only), retention/cleanup policies.
