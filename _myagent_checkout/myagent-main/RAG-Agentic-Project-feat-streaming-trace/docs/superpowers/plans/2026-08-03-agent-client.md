# Agent Client (React UI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full MVP React client for the Support Triage Agent backend per `docs/superpowers/specs/2026-08-03-agent-client-design.md`, plus the small backend history endpoint it depends on.

**Architecture:** Vite + React + TypeScript app in `client/`. Two views gated by auth state (no router): a centered AuthPage, and an AppPage with AppBar + conversation Drawer + ChatView + right-hand TracePanel (Layout C: each assistant answer carries a trace chip that opens its run in the panel; the panel also hosts Approve/Reject for `needs_confirmation` runs and doubles as the past-run viewer). Server data via one typed fetch wrapper; auth via one context.

**Tech Stack:** React 18, TypeScript (strict), MUI 6 (+@emotion, @fontsource/roboto), Vite 5 (dev proxy `/api` → `http://localhost:5000`), Vitest + React Testing Library + user-event (jsdom, stubbed fetch).

## Global Constraints

- Work on branch `feature/agent-client`, created from `feature/agent-backend` (the client needs the backend code): `git checkout feature/agent-backend && git checkout -b feature/agent-client` before Task 1.
- Backend commands run from the repo root with `source .venv/bin/activate`. Client commands run from `client/`.
- Client runtime dependencies are ONLY: react, react-dom, @mui/material, @mui/icons-material, @emotion/react, @emotion/styled, @fontsource/roboto. No router, no react-query.
- Tests never call a live backend: client tests stub `fetch` via `vi.stubGlobal`; backend tests use in-memory SQLite.
- Backend run statuses (exact strings): `running`, `needs_confirmation`, `completed`, `declined`, `failed`. Step kinds: `llm_call`, `tool_call`.
- localStorage keys (exact): `agent_token`, `agent_email`.
- The composer allows one in-flight run at a time: disabled while a send/confirm is busy or any message is awaiting confirmation.
- Conventional Commit messages.

---

### Task 1: Backend history endpoint

**Files:**
- Modify: `server/routes.py` (add one endpoint)
- Test: `server/tests/test_routes.py` (add two tests)

**Interfaces:**
- Consumes: existing `require_auth`, models `Conversation`, `Message`, `Run`.
- Produces: `GET /api/conversations/<int:conv_id>/messages` (JWT, owner-only, 404 otherwise) returning `{"messages": [{id, role, content, created_at}], "runs": [{id, user_message_id, status}]}` — both ordered by id. The client (Task 8) pairs a run to the assistant message that follows the run's `user_message_id`.

- [ ] **Step 1: Write the failing tests** — append to `server/tests/test_routes.py`

```python
def test_get_conversation_messages_history(client, auth_headers, monkeypatch):
    monkeypatch.setattr("server.routes.run_agent", _fake_agent(answer="hello back"))
    conv_id = client.post("/api/conversations", json={}, headers=auth_headers).get_json()["id"]
    run_id = client.post(
        f"/api/conversations/{conv_id}/messages", json={"content": "hi"}, headers=auth_headers
    ).get_json()["run_id"]

    resp = client.get(f"/api/conversations/{conv_id}/messages", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "assistant"]
    assert body["messages"][0]["content"] == "hi"
    assert body["runs"] == [
        {"id": run_id, "user_message_id": body["messages"][0]["id"], "status": "running"}
    ]


def test_get_conversation_messages_isolated(client, auth_headers, other_headers):
    conv_id = client.post("/api/conversations", json={}, headers=auth_headers).get_json()["id"]
    resp = client.get(f"/api/conversations/{conv_id}/messages", headers=other_headers)
    assert resp.status_code == 404
```

Note: `_fake_agent` in this test file returns an outcome dict without touching run status, so the seeded run stays `running` — the first test asserts that literal value. `_fake_agent` currently ignores its `answer`; check its definition — if it doesn't accept an `answer` kwarg, extend it to `def _fake_agent(outcome_status="completed", answer="done")` (it already has this signature in the file) and note the fake does NOT create an assistant Message row — the real `run_agent` does. So for the history test the assistant message must exist: use a fake that mimics `_finish` by adding a Message row:

```python
def _fake_agent_with_message(answer="hello back"):
    def fake(run, goal):
        from server.models import Message, db

        db.session.add(
            Message(conversation_id=run.conversation_id, role="assistant", content=answer)
        )
        db.session.commit()
        return {"run_id": run.id, "status": "completed", "answer": answer}

    return fake
```

Use `monkeypatch.setattr("server.routes.run_agent", _fake_agent_with_message())` in the first test instead of `_fake_agent`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest server/tests/test_routes.py -v`
Expected: the two new tests FAIL with 404/405 (endpoint missing); existing tests pass.

- [ ] **Step 3: Add the endpoint** — in `server/routes.py`, after `create_conversation`:

```python
@api_bp.get("/conversations/<int:conv_id>/messages")
@require_auth
def get_conversation_messages(conv_id):
    conv = Conversation.query.filter_by(id=conv_id, user_id=g.user.id).first()
    if conv is None:
        return jsonify({"error": "conversation not found"}), 404
    messages = Message.query.filter_by(conversation_id=conv.id).order_by(Message.id).all()
    runs = Run.query.filter_by(conversation_id=conv.id).order_by(Run.id).all()
    return jsonify(
        {
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
            "runs": [
                {"id": r.id, "user_message_id": r.user_message_id, "status": r.status}
                for r in runs
            ],
        }
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest server/tests -v`
Expected: all PASS (37).

- [ ] **Step 5: Commit**

```bash
git add server/routes.py server/tests/test_routes.py
git commit -m "feat: add conversation message-history endpoint for the client"
```

---

### Task 2: Client scaffold (Vite + TS + MUI + Vitest)

**Files:**
- Create: `client/package.json`, `client/vite.config.ts`, `client/tsconfig.json`, `client/index.html`, `client/.gitignore`, `client/src/main.tsx`, `client/src/App.tsx`, `client/src/setupTests.ts`, `client/src/tests/App.test.tsx`

**Interfaces:**
- Produces: a runnable Vite app (`npm run dev`) and test harness (`npm test -- --run`). `App.tsx` renders a placeholder that later tasks replace. Vite dev proxy `/api` → `http://localhost:5000`.

- [ ] **Step 1: Create `client/package.json`**

```json
{
  "name": "client",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "@emotion/react": "^11.13.0",
    "@emotion/styled": "^11.13.0",
    "@fontsource/roboto": "^5.1.0",
    "@mui/icons-material": "^6.1.0",
    "@mui/material": "^6.1.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^25.0.0",
    "typescript": "^5.6.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0"
  }
}
```

- [ ] **Step 2: Create `client/vite.config.ts`**

```typescript
/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://localhost:5000" },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.ts",
  },
});
```

- [ ] **Step 3: Create `client/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noEmit": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "isolatedModules": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "vite.config.ts"]
}
```

- [ ] **Step 4: Create `client/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Triage Agent</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `client/.gitignore`**

```
node_modules/
dist/
```

- [ ] **Step 6: Create `client/src/main.tsx`**

```tsx
import CssBaseline from "@mui/material/CssBaseline";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource/roboto/300.css";
import "@fontsource/roboto/400.css";
import "@fontsource/roboto/500.css";
import "@fontsource/roboto/700.css";
import App from "./App";

const theme = createTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
```

- [ ] **Step 7: Create `client/src/App.tsx`** (placeholder — Task 4 replaces it)

```tsx
import Typography from "@mui/material/Typography";

export default function App() {
  return <Typography variant="h5">Triage Agent</Typography>;
}
```

- [ ] **Step 8: Create `client/src/setupTests.ts`**

```typescript
import "@testing-library/jest-dom";
```

- [ ] **Step 9: Create the smoke test** — `client/src/tests/App.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import App from "../App";

test("renders the app title", () => {
  render(<App />);
  expect(screen.getByText(/triage agent/i)).toBeInTheDocument();
});
```

- [ ] **Step 10: Install and run tests**

Run: `cd client && npm install && npm test -- --run`
Expected: 1 test passes. Also verify the build: `npm run build` — succeeds.

- [ ] **Step 11: Commit**

```bash
git add client/
git commit -m "feat: scaffold Vite + TypeScript + MUI client with Vitest harness"
```

---

### Task 3: types.ts + api.ts

**Files:**
- Create: `client/src/types.ts`, `client/src/api.ts`, `client/src/tests/helpers.ts`, `client/src/tests/api.test.ts`

**Interfaces:**
- Produces (used by every later task):
  - `types.ts`: `Conversation {id, title, created_at}`, `ChatMessage {id, role, content, created_at}`, `TraceStep {seq, kind, tool_name, arguments, result, latency_ms, llm_messages?}`, `PendingAction {id, tool, arguments}`, `RunOutcome {run_id, status, answer?, pending_action?, trace}`, `RunDetail {id, status, model, total_latency_ms, created_at, steps}`, `RunSummary {id, user_message_id, status}`, `ConversationHistory {messages, runs}`, `UiMessage {role, content, runId?, stepCount?, totalLatencyMs?, awaitingConfirmation?}`, `PanelState {runId, status, steps, pendingAction?, totalLatencyMs?}`.
  - `api.ts`: `class ApiError extends Error {status}`; `setToken(t: string | null)`; `setOnUnauthorized(handler: () => void)`; `api.register/login/listConversations/createConversation/sendMessage(convId, content)/getHistory(convId)/confirmRun(runId, approved)/getRun(runId)`.
  - `tests/helpers.ts`: `jsonResponse(body, status?)` and `stubFetch(routes)` where routes maps `"METHOD url"` → handler.

- [ ] **Step 1: Create `client/src/types.ts`**

```typescript
export interface Conversation {
  id: number;
  title: string;
  created_at: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface TraceStep {
  seq: number;
  kind: "llm_call" | "tool_call" | string;
  tool_name: string | null;
  arguments: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  latency_ms: number | null;
  llm_messages?: unknown[] | null;
}

export interface PendingAction {
  id: number;
  tool: string;
  arguments: Record<string, unknown>;
}

export interface RunOutcome {
  run_id: number;
  status: "completed" | "failed" | "declined" | "needs_confirmation" | string;
  answer?: string;
  pending_action?: PendingAction;
  trace: TraceStep[];
}

export interface RunDetail {
  id: number;
  status: string;
  model: string | null;
  total_latency_ms: number | null;
  created_at: string;
  steps: TraceStep[];
}

export interface RunSummary {
  id: number;
  user_message_id: number;
  status: string;
}

export interface ConversationHistory {
  messages: ChatMessage[];
  runs: RunSummary[];
}

export interface UiMessage {
  role: "user" | "assistant";
  content: string;
  runId?: number;
  stepCount?: number;
  totalLatencyMs?: number | null;
  awaitingConfirmation?: boolean;
}

export interface PanelState {
  runId: number;
  status: string;
  steps: TraceStep[];
  pendingAction?: PendingAction;
  totalLatencyMs?: number | null;
}
```

- [ ] **Step 2: Create `client/src/api.ts`**

```typescript
import type {
  Conversation,
  ConversationHistory,
  RunDetail,
  RunOutcome,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setToken(t: string | null) {
  token = t;
}

export function setOnUnauthorized(handler: (() => void) | null) {
  onUnauthorized = handler;
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(path, { ...options, headers });
  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    body = null;
  }
  if (!resp.ok) {
    if (resp.status === 401 && onUnauthorized) onUnauthorized();
    const message =
      body && typeof body === "object" && "error" in body
        ? String((body as { error: unknown }).error)
        : `HTTP ${resp.status}`;
    throw new ApiError(resp.status, message);
  }
  return body as T;
}

export const api = {
  register: (email: string, password: string) =>
    apiFetch<{ id: number; email: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  login: (email: string, password: string) =>
    apiFetch<{ token: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  listConversations: () => apiFetch<Conversation[]>("/api/conversations"),
  createConversation: (title?: string) =>
    apiFetch<{ id: number; title: string }>("/api/conversations", {
      method: "POST",
      body: JSON.stringify(title ? { title } : {}),
    }),
  sendMessage: (convId: number, content: string) =>
    apiFetch<RunOutcome>(`/api/conversations/${convId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  getHistory: (convId: number) =>
    apiFetch<ConversationHistory>(`/api/conversations/${convId}/messages`),
  confirmRun: (runId: number, approved: boolean) =>
    apiFetch<RunOutcome>(`/api/runs/${runId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    }),
  getRun: (runId: number) => apiFetch<RunDetail>(`/api/runs/${runId}`),
};
```

- [ ] **Step 3: Create `client/src/tests/helpers.ts`**

```typescript
import { vi } from "vitest";

export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status < 400,
    status,
    json: async () => body,
  } as unknown as Response;
}

type Handler = (init?: RequestInit) => Response | Promise<Response>;

export function stubFetch(routes: Record<string, Handler>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${String(input)}`;
    const handler = routes[key];
    if (!handler) throw new Error(`Unexpected fetch: ${key}`);
    return handler(init);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
```

- [ ] **Step 4: Write the failing tests** — `client/src/tests/api.test.ts`

```typescript
import { afterEach, expect, test, vi } from "vitest";
import { ApiError, api, setOnUnauthorized, setToken } from "../api";
import { jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  setToken(null);
  setOnUnauthorized(null);
});

test("login posts credentials and returns the token", async () => {
  const fetchMock = stubFetch({
    "POST /api/auth/login": () => jsonResponse({ token: "jwt-123" }),
  });
  const result = await api.login("a@b.com", "password123");
  expect(result).toEqual({ token: "jwt-123" });
  const init = fetchMock.mock.calls[0][1]!;
  expect(JSON.parse(init.body as string)).toEqual({
    email: "a@b.com",
    password: "password123",
  });
});

test("requests carry the bearer token once set", async () => {
  const fetchMock = stubFetch({
    "GET /api/conversations": () => jsonResponse([]),
  });
  setToken("jwt-123");
  await api.listConversations();
  const headers = fetchMock.mock.calls[0][1]!.headers as Record<string, string>;
  expect(headers["Authorization"]).toBe("Bearer jwt-123");
});

test("error responses throw ApiError with the server message", async () => {
  stubFetch({
    "POST /api/auth/login": () => jsonResponse({ error: "invalid email or password" }, 401),
  });
  await expect(api.login("a@b.com", "wrong")).rejects.toThrowError(
    "invalid email or password"
  );
  await api.login("a@b.com", "wrong").catch((e: ApiError) => {
    expect(e.status).toBe(401);
  });
});

test("401 triggers the onUnauthorized handler", async () => {
  stubFetch({
    "GET /api/conversations": () => jsonResponse({ error: "invalid or expired token" }, 401),
  });
  const handler = vi.fn();
  setOnUnauthorized(handler);
  await expect(api.listConversations()).rejects.toThrow();
  expect(handler).toHaveBeenCalledOnce();
});

test("confirmRun posts the approved boolean", async () => {
  const fetchMock = stubFetch({
    "POST /api/runs/7/confirm": () =>
      jsonResponse({ run_id: 7, status: "completed", answer: "done", trace: [] }),
  });
  await api.confirmRun(7, false);
  expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toEqual({
    approved: false,
  });
});
```

- [ ] **Step 5: Run tests to verify they fail, then pass**

Run: `cd client && npm test -- --run`
Expected: FAIL first if files created out of order (imports missing); with all four files in place all 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add client/src/types.ts client/src/api.ts client/src/tests/
git commit -m "feat: add typed API client and shared test helpers"
```

---

### Task 4: Auth — AuthContext, AuthPage, App wiring

**Files:**
- Create: `client/src/auth/AuthContext.tsx`, `client/src/auth/AuthPage.tsx`, `client/src/tests/auth.test.tsx`
- Modify: `client/src/App.tsx` (auth-gated views), `client/src/main.tsx` (wrap in AuthProvider)

**Interfaces:**
- Consumes: `api`, `setToken`, `setOnUnauthorized` from Task 3.
- Produces: `AuthProvider`, `useAuth() -> {email, authed, login(email, pw), register(email, pw), logout()}`. `App` renders `AppPage` when `authed`, else `AuthPage`. Task 5 creates `chat/AppPage.tsx`; until then App uses a placeholder `<Typography>Signed in</Typography>` where AppPage will go (Task 5 swaps it).

- [ ] **Step 1: Create `client/src/auth/AuthContext.tsx`**

```tsx
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, setOnUnauthorized, setToken } from "../api";

interface AuthValue {
  email: string | null;
  authed: boolean;
  login(email: string, password: string): Promise<void>;
  register(email: string, password: string): Promise<void>;
  logout(): void;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [email, setEmail] = useState<string | null>(() =>
    localStorage.getItem("agent_email")
  );
  const [token, setTokenState] = useState<string | null>(() => {
    const t = localStorage.getItem("agent_token");
    setToken(t);
    return t;
  });

  useEffect(() => {
    const logoutHandler = () => {
      localStorage.removeItem("agent_token");
      localStorage.removeItem("agent_email");
      setToken(null);
      setTokenState(null);
      setEmail(null);
    };
    setOnUnauthorized(logoutHandler);
    return () => setOnUnauthorized(null);
  }, []);

  const value = useMemo<AuthValue>(() => {
    const login = async (em: string, pw: string) => {
      const { token: t } = await api.login(em, pw);
      localStorage.setItem("agent_token", t);
      localStorage.setItem("agent_email", em);
      setToken(t);
      setTokenState(t);
      setEmail(em);
    };
    return {
      email,
      authed: token !== null,
      login,
      register: async (em: string, pw: string) => {
        await api.register(em, pw);
        await login(em, pw);
      },
      logout: () => {
        localStorage.removeItem("agent_token");
        localStorage.removeItem("agent_email");
        setToken(null);
        setTokenState(null);
        setEmail(null);
      },
    };
  }, [email, token]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
```

- [ ] **Step 2: Create `client/src/auth/AuthPage.tsx`**

```tsx
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import { useState } from "react";
import { useAuth } from "./AuthContext";

export default function AuthPage() {
  const { login, register } = useAuth();
  const [tab, setTab] = useState(0);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (tab === 0) await login(email, password);
      else await register(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
      }}
    >
      <Card sx={{ width: 380 }}>
        <CardContent>
          <Typography variant="h5" gutterBottom>
            Triage Agent
          </Typography>
          <Tabs value={tab} onChange={(_, v: number) => setTab(v)} sx={{ mb: 1 }}>
            <Tab label="Log in" />
            <Tab label="Register" />
          </Tabs>
          <form onSubmit={submit}>
            <TextField
              label="Email"
              type="email"
              fullWidth
              margin="normal"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <TextField
              label="Password"
              type="password"
              fullWidth
              margin="normal"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              helperText={tab === 1 ? "At least 8 characters" : undefined}
            />
            {error && (
              <Alert severity="error" sx={{ mt: 1 }}>
                {error}
              </Alert>
            )}
            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={busy}
              sx={{ mt: 2 }}
            >
              {tab === 0 ? "Log in" : "Create account"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}
```

- [ ] **Step 3: Replace `client/src/App.tsx`**

```tsx
import Typography from "@mui/material/Typography";
import AuthPage from "./auth/AuthPage";
import { useAuth } from "./auth/AuthContext";

export default function App() {
  const { authed } = useAuth();
  return authed ? <Typography>Signed in</Typography> : <AuthPage />;
}
```

- [ ] **Step 4: Wrap the app in `AuthProvider`** — in `client/src/main.tsx`, add `import { AuthProvider } from "./auth/AuthContext";` and change the render body to:

```tsx
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <App />
      </AuthProvider>
    </ThemeProvider>
```

- [ ] **Step 5: Update the smoke test** — `client/src/tests/App.test.tsx` must now wrap App and clear storage:

```tsx
import { render, screen } from "@testing-library/react";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";

test("renders the auth screen when logged out", () => {
  localStorage.clear();
  render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
  expect(screen.getByText(/triage agent/i)).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /log in/i })).toBeInTheDocument();
});
```

- [ ] **Step 6: Write the auth tests** — `client/src/tests/auth.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function renderApp() {
  return render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

test("logging in stores the token and shows the app", async () => {
  localStorage.clear();
  stubFetch({
    "POST /api/auth/login": () => jsonResponse({ token: "jwt-123" }),
  });
  renderApp();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "password123");
  await userEvent.click(screen.getByRole("button", { name: /log in/i }));
  expect(await screen.findByText(/signed in/i)).toBeInTheDocument();
  expect(localStorage.getItem("agent_token")).toBe("jwt-123");
  expect(localStorage.getItem("agent_email")).toBe("a@b.com");
});

test("register auto-logs-in", async () => {
  localStorage.clear();
  stubFetch({
    "POST /api/auth/register": () => jsonResponse({ id: 1, email: "a@b.com" }, 201),
    "POST /api/auth/login": () => jsonResponse({ token: "jwt-456" }),
  });
  renderApp();
  await userEvent.click(screen.getByRole("tab", { name: /register/i }));
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "password123");
  await userEvent.click(screen.getByRole("button", { name: /create account/i }));
  expect(await screen.findByText(/signed in/i)).toBeInTheDocument();
  expect(localStorage.getItem("agent_token")).toBe("jwt-456");
});

test("failed login shows the server error", async () => {
  localStorage.clear();
  stubFetch({
    "POST /api/auth/login": () =>
      jsonResponse({ error: "invalid email or password" }, 401),
  });
  renderApp();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "wrongwrong");
  await userEvent.click(screen.getByRole("button", { name: /log in/i }));
  expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
});

test("a stored token skips the auth screen", () => {
  localStorage.setItem("agent_token", "jwt-789");
  localStorage.setItem("agent_email", "a@b.com");
  renderApp();
  expect(screen.getByText(/signed in/i)).toBeInTheDocument();
});
```

- [ ] **Step 7: Run tests**

Run: `cd client && npm test -- --run`
Expected: all PASS (11). Then `npm run build` — succeeds.

- [ ] **Step 8: Commit**

```bash
git add client/src
git commit -m "feat: add JWT auth context and login/register page"
```

---

### Task 5: AppPage shell + ConversationList

**Files:**
- Create: `client/src/chat/AppPage.tsx`, `client/src/chat/ConversationList.tsx`, `client/src/tests/conversations.test.tsx`
- Modify: `client/src/App.tsx` (render AppPage when authed)

**Interfaces:**
- Consumes: `useAuth`, `api`, types.
- Produces: `AppPage` (default export) — AppBar with app name, user email, Logout button; permanent left Drawer with `ConversationList`; main area placeholder `Select or create a conversation` (Task 7 replaces the main area). `ConversationList` props: `{conversations: Conversation[]; selectedId: number | null; onSelect: (id: number) => void; onNew: () => void}`. AppPage state produced here and extended by Task 7: `conversations`, `selectedId`, `snack`.

- [ ] **Step 1: Create `client/src/chat/ConversationList.tsx`**

```tsx
import AddIcon from "@mui/icons-material/Add";
import {
  Button,
  List,
  ListItemButton,
  ListItemText,
  Box,
} from "@mui/material";
import type { Conversation } from "../types";

interface Props {
  conversations: Conversation[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onNew: () => void;
}

export default function ConversationList({
  conversations,
  selectedId,
  onSelect,
  onNew,
}: Props) {
  return (
    <Box sx={{ p: 1 }}>
      <Button startIcon={<AddIcon />} fullWidth variant="outlined" onClick={onNew}>
        New conversation
      </Button>
      <List dense>
        {conversations.map((c) => (
          <ListItemButton
            key={c.id}
            selected={c.id === selectedId}
            onClick={() => onSelect(c.id)}
          >
            <ListItemText primary={c.title} />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
}
```

- [ ] **Step 2: Create `client/src/chat/AppPage.tsx`**

```tsx
import {
  AppBar,
  Box,
  Button,
  Drawer,
  Snackbar,
  Toolbar,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { ApiError, api } from "../api";
import { useAuth } from "../auth/AuthContext";
import type { Conversation } from "../types";
import ConversationList from "./ConversationList";

const DRAWER_WIDTH = 260;

export function errMsg(err: unknown): string {
  return err instanceof ApiError ? err.message : "Network error — is the backend running?";
}

export default function AppPage() {
  const { email, logout } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [snack, setSnack] = useState<string | null>(null);

  useEffect(() => {
    api
      .listConversations()
      .then(setConversations)
      .catch((err) => setSnack(errMsg(err)));
  }, []);

  const newConversation = async () => {
    try {
      const created = await api.createConversation();
      setConversations((cs) => [...cs, { ...created, created_at: "" }]);
      setSelectedId(created.id);
    } catch (err) {
      setSnack(errMsg(err));
    }
  };

  return (
    <Box sx={{ display: "flex", height: "100vh" }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Triage Agent
          </Typography>
          <Typography variant="body2" sx={{ mr: 2 }}>
            {email}
          </Typography>
          <Button color="inherit" onClick={logout}>
            Logout
          </Button>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box" },
        }}
      >
        <Toolbar />
        <ConversationList
          conversations={conversations}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onNew={newConversation}
        />
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, display: "flex", flexDirection: "column" }}>
        <Toolbar />
        <Box sx={{ p: 3 }}>
          <Typography color="text.secondary">
            {selectedId === null
              ? "Select or create a conversation to start."
              : `Conversation #${selectedId}`}
          </Typography>
        </Box>
      </Box>
      <Snackbar
        open={snack !== null}
        autoHideDuration={5000}
        onClose={() => setSnack(null)}
        message={snack ?? ""}
      />
    </Box>
  );
}
```

- [ ] **Step 3: Update `client/src/App.tsx`**

```tsx
import AuthPage from "./auth/AuthPage";
import { useAuth } from "./auth/AuthContext";
import AppPage from "./chat/AppPage";

export default function App() {
  const { authed } = useAuth();
  return authed ? <AppPage /> : <AuthPage />;
}
```

Also update the two tests that asserted the "Signed in" placeholder: in `client/src/tests/auth.test.tsx`, tests that land in the app after login must now stub `"GET /api/conversations": () => jsonResponse([])` in their `stubFetch` routes and assert `await screen.findByRole("button", { name: /logout/i })` instead of `findByText(/signed in/i)`. The `a stored token skips the auth screen` test likewise stubs the conversations call and asserts the logout button via `findByRole`.

- [ ] **Step 4: Write the conversation tests** — `client/src/tests/conversations.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function renderAuthed() {
  localStorage.setItem("agent_token", "jwt-123");
  localStorage.setItem("agent_email", "me@test.com");
  return render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

test("lists the user's conversations", async () => {
  stubFetch({
    "GET /api/conversations": () =>
      jsonResponse([
        { id: 1, title: "VPN ticket", created_at: "2026-08-03T00:00:00" },
        { id: 2, title: "Refund question", created_at: "2026-08-03T00:00:00" },
      ]),
  });
  renderAuthed();
  expect(await screen.findByText("VPN ticket")).toBeInTheDocument();
  expect(screen.getByText("Refund question")).toBeInTheDocument();
});

test("new conversation creates and selects it", async () => {
  stubFetch({
    "GET /api/conversations": () => jsonResponse([]),
    "POST /api/conversations": () => jsonResponse({ id: 5, title: "New conversation" }, 201),
  });
  renderAuthed();
  await userEvent.click(
    await screen.findByRole("button", { name: /new conversation/i })
  );
  expect(await screen.findByText("New conversation")).toBeInTheDocument();
});

test("logout returns to the auth screen", async () => {
  stubFetch({ "GET /api/conversations": () => jsonResponse([]) });
  renderAuthed();
  await userEvent.click(await screen.findByRole("button", { name: /logout/i }));
  expect(await screen.findByRole("tab", { name: /log in/i })).toBeInTheDocument();
  expect(localStorage.getItem("agent_token")).toBeNull();
});
```

- [ ] **Step 5: Run tests**

Run: `cd client && npm test -- --run`
Expected: all PASS. Then `npm run build` — succeeds.

- [ ] **Step 6: Commit**

```bash
git add client/src
git commit -m "feat: add app shell with conversation list and logout"
```

---

### Task 6: TracePanel + StepItem

**Files:**
- Create: `client/src/trace/TracePanel.tsx`, `client/src/trace/StepItem.tsx`, `client/src/tests/trace.test.tsx`

**Interfaces:**
- Consumes: types only — these are pure presentational components.
- Produces: `TracePanel` props `{panel: PanelState | null; busy: boolean; onConfirm: (approved: boolean) => void}`; `StepItem` props `{step: TraceStep}`. Task 7 mounts TracePanel in AppPage.

- [ ] **Step 1: Create `client/src/trace/StepItem.tsx`**

```tsx
import BuildIcon from "@mui/icons-material/Build";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import PsychologyIcon from "@mui/icons-material/Psychology";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Stack,
  Typography,
} from "@mui/material";
import type { TraceStep } from "../types";

function Section({ label, value }: { label: string; value: unknown }) {
  return (
    <Box sx={{ mb: 1 }}>
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ textTransform: "uppercase" }}
      >
        {label}
      </Typography>
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 1,
          fontSize: 12,
          overflowX: "auto",
          bgcolor: "action.hover",
          borderRadius: 1,
        }}
      >
        {JSON.stringify(value, null, 2)}
      </Box>
    </Box>
  );
}

export default function StepItem({ step }: { step: TraceStep }) {
  const isLlm = step.kind === "llm_call";
  const title = isLlm ? "model call" : (step.tool_name ?? step.kind);
  return (
    <Accordion disableGutters>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Stack direction="row" spacing={1} alignItems="center">
          {isLlm ? (
            <PsychologyIcon fontSize="small" color="secondary" />
          ) : (
            <BuildIcon fontSize="small" color="primary" />
          )}
          <Typography variant="body2">
            #{step.seq} · {title}
          </Typography>
          {step.latency_ms != null && (
            <Typography variant="caption" color="text.secondary">
              {step.latency_ms} ms
            </Typography>
          )}
        </Stack>
      </AccordionSummary>
      <AccordionDetails>
        {step.arguments != null && <Section label="arguments" value={step.arguments} />}
        {step.result != null && <Section label="result" value={step.result} />}
        {step.llm_messages != null && (
          <Section label="model input" value={step.llm_messages} />
        )}
      </AccordionDetails>
    </Accordion>
  );
}
```

- [ ] **Step 2: Create `client/src/trace/TracePanel.tsx`**

```tsx
import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import type { PanelState } from "../types";
import StepItem from "./StepItem";

const STATUS_COLOR: Record<
  string,
  "success" | "warning" | "error" | "default"
> = {
  completed: "success",
  needs_confirmation: "warning",
  failed: "error",
  declined: "default",
};

interface Props {
  panel: PanelState | null;
  busy: boolean;
  onConfirm: (approved: boolean) => void;
}

export default function TracePanel({ panel, busy, onConfirm }: Props) {
  if (!panel) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="text.secondary">
          Send a goal or click a trace chip to inspect a run.
        </Typography>
      </Box>
    );
  }
  return (
    <Box sx={{ p: 2, overflowY: "auto", height: "100%" }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="h6">Run #{panel.runId}</Typography>
        <Chip
          size="small"
          label={panel.status}
          color={STATUS_COLOR[panel.status] ?? "default"}
        />
        {panel.totalLatencyMs != null && (
          <Typography variant="caption" color="text.secondary">
            {(panel.totalLatencyMs / 1000).toFixed(1)}s total
          </Typography>
        )}
      </Stack>
      {panel.steps.map((s) => (
        <StepItem key={s.seq} step={s} />
      ))}
      {panel.status === "needs_confirmation" && panel.pendingAction && (
        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
          <Alert severity="warning" sx={{ mb: 1 }}>
            The agent wants to run <b>{panel.pendingAction.tool}</b>
          </Alert>
          <Box
            component="pre"
            sx={{ fontSize: 12, overflowX: "auto", mb: 1 }}
          >
            {JSON.stringify(panel.pendingAction.arguments, null, 2)}
          </Box>
          <Stack direction="row" spacing={1}>
            <Button
              variant="contained"
              color="success"
              disabled={busy}
              onClick={() => onConfirm(true)}
            >
              Approve
            </Button>
            <Button
              variant="outlined"
              color="error"
              disabled={busy}
              onClick={() => onConfirm(false)}
            >
              Reject
            </Button>
          </Stack>
        </Paper>
      )}
    </Box>
  );
}
```

- [ ] **Step 3: Write the trace tests** — `client/src/tests/trace.test.tsx`

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import TracePanel from "../trace/TracePanel";
import type { PanelState } from "../types";

const STEPS: PanelState["steps"] = [
  {
    seq: 1,
    kind: "llm_call",
    tool_name: null,
    arguments: null,
    result: { type: "tool_call", name: "search_knowledge" },
    latency_ms: 900,
  },
  {
    seq: 2,
    kind: "tool_call",
    tool_name: "search_knowledge",
    arguments: { query: "SLA policy" },
    result: { answer: "24h response", sources: ["policy.md"] },
    latency_ms: 230,
  },
];

test("renders empty state without a panel", () => {
  render(<TracePanel panel={null} busy={false} onConfirm={() => {}} />);
  expect(screen.getByText(/send a goal or click a trace chip/i)).toBeInTheDocument();
});

test("renders steps with tool names and latencies", () => {
  const panel: PanelState = { runId: 17, status: "completed", steps: STEPS };
  render(<TracePanel panel={panel} busy={false} onConfirm={() => {}} />);
  expect(screen.getByText(/run #17/i)).toBeInTheDocument();
  expect(screen.getByText(/#1 · model call/i)).toBeInTheDocument();
  expect(screen.getByText(/#2 · search_knowledge/i)).toBeInTheDocument();
  expect(screen.getByText("230 ms")).toBeInTheDocument();
});

test("needs_confirmation shows the pending action and fires onConfirm", async () => {
  const onConfirm = vi.fn();
  const panel: PanelState = {
    runId: 18,
    status: "needs_confirmation",
    steps: STEPS,
    pendingAction: {
      id: 3,
      tool: "escalate",
      arguments: { ticket_id: "T-1", priority: "high", reason: "outage" },
    },
  };
  render(<TracePanel panel={panel} busy={false} onConfirm={onConfirm} />);
  expect(screen.getByText(/the agent wants to run/i)).toBeInTheDocument();
  expect(screen.getByText("escalate")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /approve/i }));
  expect(onConfirm).toHaveBeenCalledWith(true);
  await userEvent.click(screen.getByRole("button", { name: /reject/i }));
  expect(onConfirm).toHaveBeenCalledWith(false);
});

test("buttons are disabled while busy", () => {
  const panel: PanelState = {
    runId: 18,
    status: "needs_confirmation",
    steps: [],
    pendingAction: { id: 3, tool: "escalate", arguments: {} },
  };
  render(<TracePanel panel={panel} busy={true} onConfirm={() => {}} />);
  expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
});
```

- [ ] **Step 4: Run tests**

Run: `cd client && npm test -- --run`
Expected: all PASS. Then `npm run build` — succeeds.

- [ ] **Step 5: Commit**

```bash
git add client/src/trace client/src/tests/trace.test.tsx
git commit -m "feat: add trace panel with step details and confirmation actions"
```

---

### Task 7: Chat flow — ChatView, MessageBubble, full AppPage

**Files:**
- Create: `client/src/chat/ChatView.tsx`, `client/src/chat/MessageBubble.tsx`, `client/src/tests/chat.test.tsx`
- Modify: `client/src/chat/AppPage.tsx` (replace whole file with the version below)

**Interfaces:**
- Consumes: `TracePanel` (Task 6), `ConversationList` (Task 5), `api`, types.
- Produces: `ChatView` props `{messages: UiMessage[]; busy: boolean; disabled: boolean; draft: string; onDraftChange: (v: string) => void; onSend: () => void; onOpenRun: (runId: number) => void}`. `MessageBubble` props `{message: UiMessage; onOpenRun: (runId: number) => void}` — assistant bubbles show a clickable trace chip (`data-testid="trace-chip-<runId>"`) unless awaiting confirmation. AppPage handlers `send`, `confirm`, `openRun` as below; Task 8 adds history loading to `selectConversation`.

- [ ] **Step 1: Create `client/src/chat/MessageBubble.tsx`**

```tsx
import HourglassTopIcon from "@mui/icons-material/HourglassTop";
import SearchIcon from "@mui/icons-material/Search";
import { Box, Chip, Paper, Typography } from "@mui/material";
import type { UiMessage } from "../types";

interface Props {
  message: UiMessage;
  onOpenRun: (runId: number) => void;
}

export default function MessageBubble({ message, onOpenRun }: Props) {
  const isUser = message.role === "user";
  return (
    <Box sx={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start" }}>
      <Paper
        elevation={1}
        sx={{
          p: 1.5,
          maxWidth: "75%",
          bgcolor: isUser ? "primary.main" : "background.paper",
          color: isUser ? "primary.contrastText" : "text.primary",
        }}
      >
        <Typography variant="body1" sx={{ whiteSpace: "pre-wrap" }}>
          {message.content}
        </Typography>
        {!isUser && message.awaitingConfirmation && (
          <Chip
            size="small"
            icon={<HourglassTopIcon />}
            label="waiting for your confirmation"
            sx={{ mt: 1 }}
          />
        )}
        {!isUser && !message.awaitingConfirmation && message.runId !== undefined && (
          <Chip
            size="small"
            icon={<SearchIcon />}
            data-testid={`trace-chip-${message.runId}`}
            onClick={() => onOpenRun(message.runId!)}
            label={`${message.stepCount ?? "?"} steps${
              message.totalLatencyMs != null
                ? ` · ${(message.totalLatencyMs / 1000).toFixed(1)}s`
                : ""
            }`}
            sx={{ mt: 1 }}
          />
        )}
      </Paper>
    </Box>
  );
}
```

- [ ] **Step 2: Create `client/src/chat/ChatView.tsx`**

```tsx
import SendIcon from "@mui/icons-material/Send";
import {
  Box,
  IconButton,
  LinearProgress,
  Stack,
  TextField,
} from "@mui/material";
import type { UiMessage } from "../types";
import MessageBubble from "./MessageBubble";

interface Props {
  messages: UiMessage[];
  busy: boolean;
  disabled: boolean;
  draft: string;
  onDraftChange: (v: string) => void;
  onSend: () => void;
  onOpenRun: (runId: number) => void;
}

export default function ChatView({
  messages,
  busy,
  disabled,
  draft,
  onDraftChange,
  onSend,
  onOpenRun,
}: Props) {
  return (
    <Box sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <Stack spacing={1.5} sx={{ flex: 1, overflowY: "auto", p: 2 }}>
        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} onOpenRun={onOpenRun} />
        ))}
      </Stack>
      {busy && <LinearProgress />}
      <Box
        component="form"
        onSubmit={(e) => {
          e.preventDefault();
          onSend();
        }}
        sx={{ display: "flex", gap: 1, p: 1.5, borderTop: 1, borderColor: "divider" }}
      >
        <TextField
          fullWidth
          size="small"
          placeholder="Give the agent a goal…"
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          disabled={disabled}
        />
        <IconButton
          type="submit"
          color="primary"
          disabled={disabled || !draft.trim()}
          aria-label="send"
        >
          <SendIcon />
        </IconButton>
      </Box>
    </Box>
  );
}
```

- [ ] **Step 3: Replace `client/src/chat/AppPage.tsx` in full**

```tsx
import {
  AppBar,
  Box,
  Button,
  Divider,
  Drawer,
  Snackbar,
  Toolbar,
  Typography,
} from "@mui/material";
import { useEffect, useState } from "react";
import { ApiError, api } from "../api";
import { useAuth } from "../auth/AuthContext";
import TracePanel from "../trace/TracePanel";
import type { Conversation, PanelState, RunOutcome, UiMessage } from "../types";
import ChatView from "./ChatView";
import ConversationList from "./ConversationList";

const DRAWER_WIDTH = 260;
const PANEL_WIDTH = 380;

export function errMsg(err: unknown): string {
  return err instanceof ApiError ? err.message : "Network error — is the backend running?";
}

export default function AppPage() {
  const { email, logout } = useAuth();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [panel, setPanel] = useState<PanelState | null>(null);
  const [snack, setSnack] = useState<string | null>(null);

  useEffect(() => {
    api
      .listConversations()
      .then(setConversations)
      .catch((err) => setSnack(errMsg(err)));
  }, []);

  const awaiting = messages.some((m) => m.awaitingConfirmation);

  const selectConversation = (id: number) => {
    setSelectedId(id);
    setMessages([]);
    setPanel(null);
  };

  const newConversation = async () => {
    try {
      const created = await api.createConversation();
      setConversations((cs) => [...cs, { ...created, created_at: "" }]);
      selectConversation(created.id);
    } catch (err) {
      setSnack(errMsg(err));
    }
  };

  const applyOutcome = (outcome: RunOutcome) => {
    if (outcome.status === "needs_confirmation") {
      setMessages((ms) => [
        ...ms,
        {
          role: "assistant",
          content: "The agent wants to take an action — review it in the trace panel.",
          runId: outcome.run_id,
          awaitingConfirmation: true,
        },
      ]);
    } else {
      setMessages((ms) => [
        ...ms,
        {
          role: "assistant",
          content: outcome.answer ?? "",
          runId: outcome.run_id,
          stepCount: outcome.trace.length,
        },
      ]);
    }
    setPanel({
      runId: outcome.run_id,
      status: outcome.status,
      steps: outcome.trace,
      pendingAction: outcome.pending_action,
    });
  };

  const send = async () => {
    const goal = draft.trim();
    if (!selectedId || !goal) return;
    setMessages((ms) => [...ms, { role: "user", content: goal }]);
    setDraft("");
    setBusy(true);
    try {
      applyOutcome(await api.sendMessage(selectedId, goal));
    } catch (err) {
      setSnack(errMsg(err));
      setDraft(goal);
      setMessages((ms) => ms.slice(0, -1));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async (approved: boolean) => {
    if (!panel) return;
    setBusy(true);
    try {
      const outcome = await api.confirmRun(panel.runId, approved);
      if (outcome.status === "needs_confirmation") {
        setPanel({
          runId: outcome.run_id,
          status: outcome.status,
          steps: outcome.trace,
          pendingAction: outcome.pending_action,
        });
      } else {
        setMessages((ms) =>
          ms.map((m) =>
            m.runId === outcome.run_id && m.awaitingConfirmation
              ? {
                  role: "assistant" as const,
                  content: outcome.answer ?? "",
                  runId: outcome.run_id,
                  stepCount: outcome.trace.length,
                }
              : m
          )
        );
        setPanel({
          runId: outcome.run_id,
          status: outcome.status,
          steps: outcome.trace,
        });
      }
    } catch (err) {
      setSnack(errMsg(err));
    } finally {
      setBusy(false);
    }
  };

  const openRun = async (runId: number) => {
    try {
      const run = await api.getRun(runId);
      setPanel({
        runId: run.id,
        status: run.status,
        steps: run.steps,
        totalLatencyMs: run.total_latency_ms,
      });
    } catch (err) {
      setSnack(errMsg(err));
    }
  };

  return (
    <Box sx={{ display: "flex", height: "100vh" }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Triage Agent
          </Typography>
          <Typography variant="body2" sx={{ mr: 2 }}>
            {email}
          </Typography>
          <Button color="inherit" onClick={logout}>
            Logout
          </Button>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          "& .MuiDrawer-paper": { width: DRAWER_WIDTH, boxSizing: "border-box" },
        }}
      >
        <Toolbar />
        <ConversationList
          conversations={conversations}
          selectedId={selectedId}
          onSelect={selectConversation}
          onNew={newConversation}
        />
      </Drawer>
      <Box
        component="main"
        sx={{ flexGrow: 1, display: "flex", flexDirection: "column", minWidth: 0 }}
      >
        <Toolbar />
        {selectedId === null ? (
          <Box sx={{ p: 3 }}>
            <Typography color="text.secondary">
              Select or create a conversation to start.
            </Typography>
          </Box>
        ) : (
          <ChatView
            messages={messages}
            busy={busy}
            disabled={busy || awaiting}
            draft={draft}
            onDraftChange={setDraft}
            onSend={send}
            onOpenRun={openRun}
          />
        )}
      </Box>
      <Divider orientation="vertical" flexItem />
      <Box sx={{ width: PANEL_WIDTH, flexShrink: 0, display: "flex", flexDirection: "column" }}>
        <Toolbar />
        <TracePanel panel={panel} busy={busy} onConfirm={confirm} />
      </Box>
      <Snackbar
        open={snack !== null}
        autoHideDuration={5000}
        onClose={() => setSnack(null)}
        message={snack ?? ""}
      />
    </Box>
  );
}
```

- [ ] **Step 4: Write the chat-flow tests** — `client/src/tests/chat.test.tsx`

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const CONV = [{ id: 1, title: "VPN ticket", created_at: "2026-08-03T00:00:00" }];
const TRACE = [
  {
    seq: 1,
    kind: "llm_call",
    tool_name: null,
    arguments: null,
    result: {},
    latency_ms: 900,
  },
  {
    seq: 2,
    kind: "tool_call",
    tool_name: "search_knowledge",
    arguments: { query: "vpn" },
    result: { answer: "reset it", sources: [] },
    latency_ms: 230,
  },
];

async function renderAndOpenConversation(extraRoutes: Parameters<typeof stubFetch>[0]) {
  localStorage.setItem("agent_token", "jwt-123");
  localStorage.setItem("agent_email", "me@test.com");
  stubFetch({
    "GET /api/conversations": () => jsonResponse(CONV),
    "GET /api/conversations/1/messages": () =>
      jsonResponse({ messages: [], runs: [] }),
    ...extraRoutes,
  });
  render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
  await userEvent.click(await screen.findByText("VPN ticket"));
}

test("sending a goal renders the answer with a trace chip and fills the panel", async () => {
  await renderAndOpenConversation({
    "POST /api/conversations/1/messages": () =>
      jsonResponse({
        run_id: 17,
        status: "completed",
        answer: "Reset it in Settings.",
        trace: TRACE,
      }),
  });
  await userEvent.type(
    screen.getByPlaceholderText(/give the agent a goal/i),
    "How do I reset my VPN?"
  );
  await userEvent.click(screen.getByRole("button", { name: /send/i }));

  expect(await screen.findByText("Reset it in Settings.")).toBeInTheDocument();
  expect(screen.getByTestId("trace-chip-17")).toHaveTextContent("2 steps");
  expect(screen.getByText(/run #17/i)).toBeInTheDocument();
  expect(screen.getByText(/#2 · search_knowledge/i)).toBeInTheDocument();
});

test("needs_confirmation pauses: approve resolves the placeholder", async () => {
  await renderAndOpenConversation({
    "POST /api/conversations/1/messages": () =>
      jsonResponse({
        run_id: 18,
        status: "needs_confirmation",
        pending_action: {
          id: 3,
          tool: "escalate",
          arguments: { ticket_id: "T-1", priority: "high", reason: "outage" },
        },
        trace: TRACE.slice(0, 1),
      }),
    "POST /api/runs/18/confirm": () =>
      jsonResponse({
        run_id: 18,
        status: "completed",
        answer: "Escalated to on-call.",
        trace: TRACE,
      }),
  });
  await userEvent.type(
    screen.getByPlaceholderText(/give the agent a goal/i),
    "Escalate ticket T-1"
  );
  await userEvent.click(screen.getByRole("button", { name: /send/i }));

  expect(
    await screen.findByText(/waiting for your confirmation/i)
  ).toBeInTheDocument();
  expect(screen.getByPlaceholderText(/give the agent a goal/i)).toBeDisabled();
  expect(screen.getByText(/the agent wants to run/i)).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: /approve/i }));
  expect(await screen.findByText("Escalated to on-call.")).toBeInTheDocument();
  expect(screen.queryByText(/waiting for your confirmation/i)).not.toBeInTheDocument();
  expect(screen.getByPlaceholderText(/give the agent a goal/i)).toBeEnabled();
});

test("send failure shows a snackbar and preserves the draft", async () => {
  await renderAndOpenConversation({
    "POST /api/conversations/1/messages": () =>
      jsonResponse({ error: "boom" }, 500),
  });
  const input = screen.getByPlaceholderText(/give the agent a goal/i);
  await userEvent.type(input, "hello agent");
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  expect(await screen.findByText("boom")).toBeInTheDocument();
  expect(input).toHaveValue("hello agent");
});

test("clicking a trace chip loads the run into the panel", async () => {
  await renderAndOpenConversation({
    "POST /api/conversations/1/messages": () =>
      jsonResponse({ run_id: 17, status: "completed", answer: "Done.", trace: TRACE }),
    "GET /api/runs/17": () =>
      jsonResponse({
        id: 17,
        status: "completed",
        model: "llama3.1:8b",
        total_latency_ms: 1130,
        created_at: "2026-08-03T00:00:00",
        steps: TRACE,
      }),
  });
  await userEvent.type(
    screen.getByPlaceholderText(/give the agent a goal/i),
    "do it"
  );
  await userEvent.click(screen.getByRole("button", { name: /send/i }));
  await screen.findByText("Done.");
  await userEvent.click(screen.getByTestId("trace-chip-17"));
  expect(await screen.findByText(/1\.1s total/i)).toBeInTheDocument();
});
```

Note: `renderAndOpenConversation` stubs `GET /api/conversations/1/messages` from the start — Task 8 makes selectConversation actually call it; until then the stub is simply unused. This keeps these tests stable across Task 8.

- [ ] **Step 5: Run tests**

Run: `cd client && npm test -- --run`
Expected: all PASS. Then `npm run build` — succeeds.

- [ ] **Step 6: Commit**

```bash
git add client/src
git commit -m "feat: add chat flow with trace chips and confirmation handling"
```

---

### Task 8: History restore on conversation select

**Files:**
- Create: `client/src/chat/history.ts`, `client/src/tests/history.test.ts`
- Modify: `client/src/chat/AppPage.tsx` (selectConversation loads history)

**Interfaces:**
- Consumes: `api.getHistory`, `ConversationHistory`, `UiMessage`.
- Produces: `pairHistory(history: ConversationHistory): UiMessage[]` — user messages pass through; each assistant message gets the `runId` of the run whose `user_message_id` matches the most recent preceding user message (consumed after use, so a second assistant message without its own run gets none). Assistant messages restored from history get `stepCount: undefined` (chip shows `? steps`) — the full trace loads on chip click via `getRun`.

- [ ] **Step 1: Write the failing pairing tests** — `client/src/tests/history.test.ts`

```typescript
import { expect, test } from "vitest";
import { pairHistory } from "../chat/history";
import type { ConversationHistory } from "../types";

const HISTORY: ConversationHistory = {
  messages: [
    { id: 1, role: "user", content: "reset vpn?", created_at: "t1" },
    { id: 2, role: "assistant", content: "In Settings.", created_at: "t2" },
    { id: 3, role: "user", content: "escalate T-1", created_at: "t3" },
    { id: 4, role: "assistant", content: "Escalated.", created_at: "t4" },
  ],
  runs: [
    { id: 10, user_message_id: 1, status: "completed" },
    { id: 11, user_message_id: 3, status: "completed" },
  ],
};

test("pairs each assistant message with the run of the preceding user message", () => {
  const ui = pairHistory(HISTORY);
  expect(ui).toHaveLength(4);
  expect(ui[0]).toMatchObject({ role: "user", content: "reset vpn?" });
  expect(ui[1]).toMatchObject({ role: "assistant", content: "In Settings.", runId: 10 });
  expect(ui[3]).toMatchObject({ role: "assistant", content: "Escalated.", runId: 11 });
});

test("assistant message without a matching run gets no runId", () => {
  const ui = pairHistory({
    messages: [{ id: 2, role: "assistant", content: "orphan", created_at: "t" }],
    runs: [],
  });
  expect(ui[0].runId).toBeUndefined();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd client && npm test -- --run src/tests/history.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Create `client/src/chat/history.ts`**

```typescript
import type { ConversationHistory, RunSummary, UiMessage } from "../types";

export function pairHistory(history: ConversationHistory): UiMessage[] {
  const runByUserMessage = new Map<number, RunSummary>(
    history.runs.map((r) => [r.user_message_id, r])
  );
  const out: UiMessage[] = [];
  let pendingRun: RunSummary | undefined;
  for (const m of history.messages) {
    if (m.role === "user") {
      pendingRun = runByUserMessage.get(m.id);
      out.push({ role: "user", content: m.content });
    } else {
      out.push({ role: "assistant", content: m.content, runId: pendingRun?.id });
      pendingRun = undefined;
    }
  }
  return out;
}
```

- [ ] **Step 4: Wire into AppPage** — in `client/src/chat/AppPage.tsx`, add `import { pairHistory } from "./history";` and replace `selectConversation` with:

```tsx
  const selectConversation = (id: number) => {
    setSelectedId(id);
    setMessages([]);
    setPanel(null);
    api
      .getHistory(id)
      .then((h) => setMessages(pairHistory(h)))
      .catch((err) => setSnack(errMsg(err)));
  };
```

Note: `newConversation` calls `selectConversation(created.id)`, which now fetches history for the new (empty) conversation — the conversations tests from Task 5 must add a `"GET /api/conversations/5/messages": () => jsonResponse({ messages: [], runs: [] })` route to the `new conversation creates and selects it` test.

- [ ] **Step 5: Add a restore test** — append to `client/src/tests/history.test.ts` a component test (rename file stays `.ts`? No — component tests need TSX. Add it to `client/src/tests/chat.test.tsx` instead):

```tsx
test("selecting a conversation restores its history with trace chips", async () => {
  await renderAndOpenConversation({
    "GET /api/conversations/1/messages": () =>
      jsonResponse({
        messages: [
          { id: 1, role: "user", content: "reset vpn?", created_at: "t1" },
          { id: 2, role: "assistant", content: "In Settings.", created_at: "t2" },
        ],
        runs: [{ id: 10, user_message_id: 1, status: "completed" }],
      }),
  });
  expect(await screen.findByText("In Settings.")).toBeInTheDocument();
  expect(screen.getByTestId("trace-chip-10")).toBeInTheDocument();
});
```

(The `...extraRoutes` spread in `renderAndOpenConversation` overrides the default empty-history route because it comes last.)

- [ ] **Step 6: Run all client tests**

Run: `cd client && npm test -- --run`
Expected: all PASS. Then `npm run build` — succeeds.

- [ ] **Step 7: Commit**

```bash
git add client/src
git commit -m "feat: restore conversation history with paired run chips"
```

---

### Task 9: CI client job + docs

**Files:**
- Modify: `.github/workflows/ci.yml` (add client job), `CLAUDE.md` (client commands current), `README.md` (only if its client step is inaccurate — it already says `cd client && npm install && npm run dev`, which now works; verify, don't rewrite)

**Interfaces:**
- Consumes: green client suite from Tasks 2–8.

- [ ] **Step 1: Add the client job** — append to `.github/workflows/ci.yml` under `jobs:`

```yaml
  client:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: client
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: client/package-lock.json
      - run: npm ci
      - run: npm test -- --run
      - run: npm run build
```

- [ ] **Step 2: Update `CLAUDE.md`** — in the Commands section: under `# Frontend (client/)` keep `npm install` / `npm run dev`, and in the Tests block replace `npm test                      # frontend` with:

```bash
cd client && npm test -- --run                    # frontend tests (single run)
cd client && npm test -- --run src/tests/chat.test.tsx  # single frontend test file
```

Also update the "What this repo is" paragraph: the client now exists under `client/` (remove "still to be built by the team" phrasing).

- [ ] **Step 3: Verify README quick start** — confirm `client/` steps in README §4 work as written (`npm install`, `npm run dev` at http://localhost:5173, proxying to Flask on 5000). Fix only if wrong.

- [ ] **Step 4: Full verification**

Run from repo root:
```bash
source .venv/bin/activate && python -m pytest server/tests -v   # 37 passed
cd client && npm test -- --run && npm run build                  # all pass, build ok
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml CLAUDE.md README.md
git commit -m "chore: add client CI job and update docs for the React client"
```

---

## Self-Review Notes

- **Spec coverage:** backend history endpoint (T1); scaffold + proxy (T2); types/api/ApiError/401-handler (T3); AuthContext + AuthPage + auto-login-after-register + stored-token restore + logout-on-401 (T4, wired via `setOnUnauthorized`); conversation list/create/select + logout (T5); TracePanel with steps, statuses, pending-action Approve/Reject, `llm_messages` section (T6); Layout-C chat flow — chip → panel, needs_confirmation placeholder bubble, composer lock (`busy || awaiting`), draft preserved on error, snackbar (T7); reload-surviving history with run pairing (T8); CI + docs (T9).
- **Type consistency checked:** `UiMessage`/`PanelState` defined once in types.ts (T3) and used identically in T6–T8; `stubFetch` route-key format `"METHOD url"` consistent across all test files; `data-testid="trace-chip-<runId>"` used in T7 and asserted in T7/T8.
- **Known cross-task test edits are explicit:** T5 Step 3 updates two auth tests; T8 Step 4 updates one conversations test. Implementers of those tasks must apply them — they are in-task steps, not afterthoughts.
- **Deliberate simplifications:** restored assistant bubbles show `? steps` until the chip is clicked (full trace via `getRun`); `created_at: ""` on locally-created conversations (never rendered); no auto-scroll-to-bottom (acceptable at MVP scale).
