# Agent Client (React UI) — Design

**Date:** 2026-08-03
**Scope:** Full MVP React client for the Support Triage Agent backend, plus one small backend addition (message-history endpoint).
**Decisions made:** TypeScript · MUI (Material UI) · plain fetch + AuthContext (no react-query) · no router (auth state gates two views) · Layout C: trace chip per answer + right-hand trace panel that doubles as confirmation UI and run viewer.

## Goal

A Vite + React + TypeScript client in `client/` covering the README's UI requirements: login/register, per-user conversations, chat with the agent, a visible per-step agent trace, confirmation before consequential actions, and inspection of past runs. Satisfies MVP requirements 5 (visible trace), 8 (auth UI), and the UI half of 3/6/7 in README §6.

## Backend addition (prerequisite task)

`GET /api/conversations/<id>/messages` (JWT, owner-only, 404 otherwise) so chat history survives reload:

```json
{
  "messages": [{"id": 1, "role": "user|assistant", "content": "...", "created_at": "..."}],
  "runs": [{"id": 17, "user_message_id": 1, "status": "completed"}]
}
```

No schema change: assistant messages aren't linked to runs in the DB, so the client pairs them — a run's `user_message_id` identifies the user message; the chip attaches to the assistant message that follows it.

## Architecture

```
client/
├── package.json, vite.config.ts, tsconfig.json, index.html
└── src/
    ├── main.tsx              ← App in MUI ThemeProvider + CssBaseline + AuthProvider
    ├── App.tsx               ← AuthPage or AppPage based on auth state
    ├── types.ts              ← TS types mirroring backend JSON: Conversation, ChatMessage,
    │                           RunOutcome, TraceStep, PendingAction, RunDetail, RunSummary
    ├── api.ts                ← typed fetch wrapper (JWT header, ApiError with status) +
    │                           one function per endpoint; register/login/conversations/
    │                           messages/history/confirm/getRun
    ├── auth/
    │   ├── AuthContext.tsx   ← token + email in state and localStorage; login/register/
    │   │                       logout; any ApiError 401 → logout
    │   └── AuthPage.tsx      ← centered MUI Card with Login/Register tabs
    ├── chat/
    │   ├── AppPage.tsx       ← AppBar (email, logout) + conversation Drawer +
    │   │                       ChatView (left) + TracePanel (right); owns selectedRunId
    │   ├── ConversationList.tsx ← list + "New conversation"
    │   ├── ChatView.tsx      ← history load on select, composer, send flow
    │   └── MessageBubble.tsx ← user/assistant bubbles; assistant bubble carries the
    │                           "🔍 N steps · X.Xs" TraceChip → sets selectedRunId
    └── trace/
        ├── TracePanel.tsx    ← trace for selectedRunId (from fresh response or
        │                       GET /api/runs/:id); Approve/Reject when needs_confirmation
        └── StepItem.tsx      ← seq, kind icon, tool name, latency; args/result as
                                collapsible JSON
```

Dev: Vite proxies `/api` → `http://localhost:5000`. Runtime deps: react, react-dom, @mui/material, @mui/icons-material, @emotion/react, @emotion/styled, @fontsource/roboto only.

## Data flow

**Send:** composer submits → optimistic user bubble, composer disabled, "thinking" indicator → `POST /api/conversations/:id/messages`:
- `completed`/`failed`/`declined` → assistant bubble with `answer`, chip with `run_id` + step count + total latency, run auto-selected in panel.
- `needs_confirmation` → "⏸ waiting for your confirmation" bubble; panel auto-opens with the pending action (tool + arguments rendered readably) and Approve/Reject. `POST /api/runs/:id/confirm {approved: bool}` → placeholder bubble replaced by final answer, trace updated. Composer stays disabled until the pending run resolves (one in-flight run at a time, matching the backend).

**Conversation select / reload:** `GET /api/conversations/:id/messages` restores history; runs paired to assistant bubbles via `user_message_id`. Older run chips fetch `GET /api/runs/:id` (includes `llm_messages` — the panel shows them under a collapsed "model input" section per llm_call step).

## Error handling

- `api.ts` throws `ApiError {status, message}`; 401 anywhere → logout.
- Network/server errors → MUI Snackbar; composer re-enabled with draft preserved.
- Unknown statuses/step kinds render as plain text — never crash the panel.

## Testing

Vitest + React Testing Library, global `fetch` stubbed (no live backend; CI-safe):
- AuthPage: login stores token and shows the app; register → auto-login.
- ChatView: send renders answer bubble + trace chip; API error shows snackbar and preserves draft.
- Confirmation: needs_confirmation renders Approve/Reject; Approve posts `{approved: true}`; resolved answer replaces placeholder.
- TracePanel: renders steps with tool names, args, latency.
- AuthContext: 401 from any call logs out.

CI: extend `.github/workflows/ci.yml` with a client job (`npm ci`, `npm test -- --run`, `npm run build` in `client/`).

## Out of scope

Streaming/token-by-token trace, conversation deletion/rename, dark-mode toggle, mobile-specific layout (MUI defaults are passably responsive), react-router.
