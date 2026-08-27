# Observability Audit Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the audit surface from `docs/superpowers/specs/2026-08-04-observability-audit-design.md`: token capture into `run_steps`, admin model via `ADMIN_EMAILS`, `GET /api/runs` + `GET /api/runs/stats`, and a client Audit tab with stat cards, recharts charts, filterable runs table, and a drill-down drawer with JSON export.

**Architecture:** Backend extends the existing logging pipeline (no new tables — two new columns on `run_steps`) and adds two read-only aggregate endpoints scoped own-vs-admin. Frontend adds an `audit/` module behind a Chat|Audit tab toggle in AppPage, reusing TracePanel read-only for drill-down.

**Tech Stack:** Existing Flask/SQLAlchemy backend (portable SQL — SQLite in tests, Postgres in dev) and React/TS/MUI client; one new client dependency: `recharts`.

## Global Constraints

- Work on branch `feature/observability-audit`, created from `main`: `git checkout main && git checkout -b feature/observability-audit` before Task 1.
- Backend commands from repo root with `source .venv/bin/activate`; client commands from `client/`.
- Backend tests: in-memory SQLite, no live services; all SQL must run on both SQLite and Postgres (use `func.date(...)` for date filters, no PG-only syntax).
- Client: `recharts` is the ONLY new dependency.
- Admin filter param and response field are both `user_email` (exact match, case-insensitive). Non-admins: the `user_email` param is silently ignored and results are always scoped to their own runs.
- localStorage key for the admin flag: `agent_is_admin` (values `"1"`/`"0"`).
- Statuses (exact strings): `running`, `needs_confirmation`, `completed`, `declined`, `failed`. `success_rate = completed / (completed + failed + declined)`, `null` when no terminal runs.
- Latency buckets (exact labels): `<2s` (0–1999ms), `2–5s` (2000–4999), `5–15s` (5000–14999), `15s+` (≥15000).
- Conventional Commit messages.

---

### Task 1: Token capture — usage in generate(), token columns on run_steps

**Files:**
- Modify: `server/llm.py` (return `usage`), `server/models.py` (two columns), `server/observability.py` (pop usage into columns), `server/tests/test_llm.py` (update equality assertions + new test), `server/tests/test_observability.py` (new test)
- Create: migration via `flask db migrate` (requires the `agentdb` Postgres container running and `.env` pointing at it)

**Interfaces:**
- Consumes: existing `generate()` return shapes and `record_step(run_id, seq, kind, fn, *, tool_name=None, arguments=None, llm_messages=None)`.
- Produces: `generate()` returns additionally `"usage": {"prompt_tokens": int|None, "completion_tokens": int|None}` on BOTH shapes. `RunStep.prompt_tokens`/`RunStep.completion_tokens` (nullable Integer). `record_step` pops `"usage"` from a dict result into those columns; the stored `result` JSON does NOT contain `usage`.

- [ ] **Step 1: Update existing test expectations and add new tests**

In `server/tests/test_llm.py`, the two full-equality assertions must now include the usage key. Update `test_generate_final_answer`:

```python
    assert result == {
        "type": "final",
        "content": "hi there",
        "usage": {"prompt_tokens": None, "completion_tokens": None},
    }
```

Update `test_generate_parses_tool_call` the same way (append `"usage": {"prompt_tokens": None, "completion_tokens": None}` to the expected dict).

Append a new test:

```python
def test_generate_parses_usage(app, monkeypatch):
    payload = {
        "choices": [{"message": {"content": "hi"}}],
        "usage": {"prompt_tokens": 150, "completion_tokens": 20},
    }
    monkeypatch.setattr("server.llm.requests.post", lambda *a, **k: FakeResponse(payload))
    from server.llm import generate

    result = generate([], [])
    assert result["usage"] == {"prompt_tokens": 150, "completion_tokens": 20}
```

Append to `server/tests/test_observability.py`:

```python
def test_record_step_stores_tokens_and_strips_usage(app, run):
    from server.models import RunStep
    from server.observability import record_step

    result = record_step(
        run.id,
        1,
        "llm_call",
        lambda: {
            "type": "final",
            "content": "hi",
            "usage": {"prompt_tokens": 150, "completion_tokens": 20},
        },
    )
    assert "usage" not in result
    step = RunStep.query.filter_by(run_id=run.id).one()
    assert step.prompt_tokens == 150
    assert step.completion_tokens == 20
    assert "usage" not in step.result
```

- [ ] **Step 2: Run tests to verify failures**

Run: `source .venv/bin/activate && python -m pytest server/tests/test_llm.py server/tests/test_observability.py -v`
Expected: the two updated equality tests and both new tests FAIL; others pass.

- [ ] **Step 3: Implement**

In `server/llm.py`, inside `generate()` replace `message = resp.json()["choices"][0]["message"]` with:

```python
    data = resp.json()
    message = data["choices"][0]["message"]
    usage_raw = data.get("usage") or {}
    usage = {
        "prompt_tokens": usage_raw.get("prompt_tokens"),
        "completion_tokens": usage_raw.get("completion_tokens"),
    }
```

and add `"usage": usage,` to BOTH returned dicts (the tool_call return and the final return).

In `server/models.py`, add to `RunStep` after `latency_ms`:

```python
    prompt_tokens = db.Column(db.Integer)
    completion_tokens = db.Column(db.Integer)
```

In `server/observability.py`, replace the body after the latency computation with:

```python
    latency_ms = int((time.perf_counter() - start) * 1000)
    usage = {}
    if isinstance(result, dict) and "usage" in result:
        usage = result.pop("usage") or {}
    stored = result if isinstance(result, dict) else {"value": result}
    step = RunStep(
        run_id=run_id,
        seq=seq,
        kind=kind,
        tool_name=tool_name,
        arguments=arguments,
        result=stored,
        llm_messages=llm_messages,
        latency_ms=latency_ms,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
    )
    db.session.add(step)
    db.session.commit()
    return result
```

- [ ] **Step 4: Run the backend suite**

Run: `python -m pytest server/tests -v`
Expected: all PASS (agent tests are unaffected — their stubbed `generate` returns no `usage`, which `record_step` tolerates).

- [ ] **Step 5: Generate and apply the migration** (Postgres `agentdb` container must be running; `.env` DATABASE_URL points at it)

Run:
```bash
flask --app server.app db migrate -m "add token columns to run_steps"
flask --app server.app db upgrade
```
Expected: a new file in `migrations/versions/` adding the two columns; upgrade succeeds.

- [ ] **Step 6: Commit**

```bash
git add server/ migrations/versions/
git commit -m "feat: capture prompt/completion token usage per LLM call"
```

---

### Task 2: Admin model — ADMIN_EMAILS, g.is_admin, login response

**Files:**
- Modify: `server/config.py`, `server/auth.py`, `server/tests/test_auth.py`, `server/tests/conftest.py` (admin fixture), `.env.example`

**Interfaces:**
- Produces: `Config.ADMIN_EMAILS: set[str]` (lowercased, from comma-separated env, empty default). `require_auth` sets `g.is_admin: bool`. `POST /api/auth/login` → `{token, email, is_admin}`. Conftest fixture `admin_headers` (admin user `admin@test.com` with `ADMIN_EMAILS` config override).

- [ ] **Step 1: Write the failing tests** — append to `server/tests/test_auth.py`:

```python
def test_login_reports_admin_flag(app, client):
    app.config["ADMIN_EMAILS"] = {"boss@test.com"}
    for email in ("boss@test.com", "pleb@test.com"):
        client.post("/api/auth/register", json={"email": email, "password": "password123"})
    boss = client.post(
        "/api/auth/login", json={"email": "boss@test.com", "password": "password123"}
    ).get_json()
    pleb = client.post(
        "/api/auth/login", json={"email": "pleb@test.com", "password": "password123"}
    ).get_json()
    assert boss["is_admin"] is True and boss["email"] == "boss@test.com"
    assert pleb["is_admin"] is False
```

And add to `server/tests/conftest.py`:

```python
@pytest.fixture
def admin_headers(client, app):
    app.config["ADMIN_EMAILS"] = {"admin@test.com"}
    client.post("/api/auth/register", json={"email": "admin@test.com", "password": "password123"})
    token = client.post(
        "/api/auth/login", json={"email": "admin@test.com", "password": "password123"}
    ).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_auth.py -v`
Expected: `test_login_reports_admin_flag` FAILS (KeyError `is_admin`).

- [ ] **Step 3: Implement**

`server/config.py` — add to `Config`:

```python
    ADMIN_EMAILS = {
        e.strip().lower()
        for e in os.environ.get("ADMIN_EMAILS", "").split(",")
        if e.strip()
    }
```

`server/auth.py` — in `login()`, replace the return with:

```python
    return jsonify(
        {
            "token": token,
            "email": user.email,
            "is_admin": user.email in current_app.config["ADMIN_EMAILS"],
        }
    )
```

In `require_auth`'s wrapper, after `g.user = user` add:

```python
        g.is_admin = user.email in current_app.config["ADMIN_EMAILS"]
```

`.env.example` — add under the Flask section:

```
# Comma-separated emails that get the admin audit view (see all users' runs)
ADMIN_EMAILS=
```

- [ ] **Step 4: Run the backend suite**

Run: `python -m pytest server/tests -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add server/ .env.example
git commit -m "feat: add ADMIN_EMAILS admin flag to auth"
```

---

### Task 3: GET /api/runs — filtered, paginated list

**Files:**
- Modify: `server/routes.py`
- Create: `server/tests/test_audit.py`

**Interfaces:**
- Consumes: `g.is_admin` (Task 2), token columns (Task 1), models.
- Produces: module-level helper `_filtered_runs_query()` in `server/routes.py` returning a query of `(Run, Conversation, User)` tuples with all filters applied (reused by Task 4), and `GET /api/runs` per the spec: params `status`, `conversation_id`, `date_from`, `date_to`, `page` (default 1), `per_page` (default 20, max 100), admin-only `user_email`; response `{runs: [RunListItem…], total, page, per_page}` with `user_email` per row only for admins; rows newest-first.

- [ ] **Step 1: Write the failing tests** — create `server/tests/test_audit.py`:

```python
from datetime import datetime, timezone

import pytest

from server.auth import bcrypt
from server.models import Conversation, Message, Run, RunStep, User, db


def _seed_user(email):
    user = User(
        email=email,
        password_hash=bcrypt.generate_password_hash("password123").decode("utf-8"),
    )
    db.session.add(user)
    db.session.commit()
    return user


def _seed_run(
    user,
    *,
    status="completed",
    goal="test goal",
    latency=3000,
    tokens=(100, 10),
    tool="search_knowledge",
    created_at=None,
):
    conv = Conversation(user_id=user.id, title=f"conv of {user.email}")
    db.session.add(conv)
    db.session.commit()
    msg = Message(conversation_id=conv.id, role="user", content=goal)
    db.session.add(msg)
    db.session.commit()
    run = Run(
        conversation_id=conv.id,
        user_message_id=msg.id,
        status=status,
        model="llama3.1:8b",
        total_latency_ms=latency,
    )
    db.session.add(run)
    db.session.commit()
    if created_at is not None:
        run.created_at = created_at
        db.session.commit()
    db.session.add_all(
        [
            RunStep(
                run_id=run.id, seq=1, kind="llm_call", result={},
                latency_ms=latency - 500 if latency else None,
                prompt_tokens=tokens[0], completion_tokens=tokens[1],
            ),
            RunStep(
                run_id=run.id, seq=2, kind="tool_call", tool_name=tool,
                arguments={}, result={}, latency_ms=500,
            ),
        ]
    )
    db.session.commit()
    return run


@pytest.fixture
def me(app, auth_headers):
    return User.query.filter_by(email="me@test.com").one()


def test_list_runs_scoped_to_own_user(client, auth_headers, me):
    other = _seed_user("other@test.com")
    mine = _seed_run(me, goal="my goal")
    _seed_run(other, goal="their goal")

    body = client.get("/api/runs", headers=auth_headers).get_json()
    assert body["total"] == 1
    row = body["runs"][0]
    assert row["id"] == mine.id
    assert row["goal"] == "my goal"
    assert row["step_count"] == 2
    assert row["prompt_tokens"] == 100
    assert row["completion_tokens"] == 10
    assert "user_email" not in row

    # user_email param is silently ignored for non-admins
    body = client.get(
        "/api/runs?user_email=other@test.com", headers=auth_headers
    ).get_json()
    assert body["total"] == 1
    assert body["runs"][0]["id"] == mine.id


def test_list_runs_admin_sees_all_and_filters_by_email(client, admin_headers, auth_headers, me):
    other = _seed_user("other@test.com")
    _seed_run(me)
    _seed_run(other)

    body = client.get("/api/runs", headers=admin_headers).get_json()
    assert body["total"] == 2
    assert {r["user_email"] for r in body["runs"]} == {"me@test.com", "other@test.com"}

    body = client.get(
        "/api/runs?user_email=OTHER@test.com", headers=admin_headers
    ).get_json()
    assert body["total"] == 1
    assert body["runs"][0]["user_email"] == "other@test.com"


def test_list_runs_filters_and_pagination(client, auth_headers, me):
    _seed_run(me, status="completed", created_at=datetime(2026, 8, 1, 12, tzinfo=timezone.utc))
    _seed_run(me, status="failed", created_at=datetime(2026, 8, 2, 12, tzinfo=timezone.utc))
    _seed_run(me, status="completed", created_at=datetime(2026, 8, 3, 12, tzinfo=timezone.utc))

    body = client.get("/api/runs?status=completed", headers=auth_headers).get_json()
    assert body["total"] == 2

    body = client.get(
        "/api/runs?date_from=2026-08-02&date_to=2026-08-02", headers=auth_headers
    ).get_json()
    assert body["total"] == 1
    assert body["runs"][0]["status"] == "failed"

    body = client.get("/api/runs?per_page=2&page=2", headers=auth_headers).get_json()
    assert body["total"] == 3
    assert len(body["runs"]) == 1
    # newest first: page 2 holds the oldest run
    assert body["runs"][0]["created_at"].startswith("2026-08-01")
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_audit.py -v`
Expected: FAIL with 404s (endpoint missing).

- [ ] **Step 3: Implement** — in `server/routes.py`. Add `func` to the imports (`from sqlalchemy import func` — it may already be imported in `agent.py` but not here) and `User` to the models import, then add above the run endpoints:

```python
from datetime import date


def _parse_iso_date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _filtered_runs_query():
    """(Run, Conversation, User) rows with audit filters applied, scoped by role."""
    q = (
        db.session.query(Run, Conversation, User)
        .join(Conversation, Run.conversation_id == Conversation.id)
        .join(User, Conversation.user_id == User.id)
    )
    if g.is_admin:
        email = (request.args.get("user_email") or "").strip().lower()
        if email:
            q = q.filter(func.lower(User.email) == email)
    else:
        q = q.filter(Conversation.user_id == g.user.id)
    status = request.args.get("status")
    if status:
        q = q.filter(Run.status == status)
    conv_id = request.args.get("conversation_id", type=int)
    if conv_id:
        q = q.filter(Run.conversation_id == conv_id)
    date_from = _parse_iso_date(request.args.get("date_from"))
    if date_from:
        q = q.filter(func.date(Run.created_at) >= date_from.isoformat())
    date_to = _parse_iso_date(request.args.get("date_to"))
    if date_to:
        q = q.filter(func.date(Run.created_at) <= date_to.isoformat())
    return q


@api_bp.get("/runs")
@require_auth
def list_runs():
    q = _filtered_runs_query()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)
    total = q.count()
    rows = (
        q.order_by(Run.created_at.desc(), Run.id.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )
    run_ids = [run.id for run, _, _ in rows]
    step_aggs = {}
    goals = {}
    if run_ids:
        for run_id, count, pt, ct in (
            db.session.query(
                RunStep.run_id,
                func.count(RunStep.id),
                func.coalesce(func.sum(RunStep.prompt_tokens), 0),
                func.coalesce(func.sum(RunStep.completion_tokens), 0),
            )
            .filter(RunStep.run_id.in_(run_ids))
            .group_by(RunStep.run_id)
        ):
            step_aggs[run_id] = (count, pt, ct)
        goals = dict(
            db.session.query(Message.id, Message.content).filter(
                Message.id.in_([run.user_message_id for run, _, _ in rows])
            )
        )
    runs = []
    for run, conv, user in rows:
        count, pt, ct = step_aggs.get(run.id, (0, 0, 0))
        item = {
            "id": run.id,
            "status": run.status,
            "goal": (goals.get(run.user_message_id) or "")[:80],
            "conversation_id": conv.id,
            "conversation_title": conv.title,
            "model": run.model,
            "step_count": count,
            "total_latency_ms": run.total_latency_ms,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "created_at": run.created_at.isoformat(),
        }
        if g.is_admin:
            item["user_email"] = user.email
        runs.append(item)
    return jsonify({"runs": runs, "total": total, "page": page, "per_page": per_page})
```

- [ ] **Step 4: Run the backend suite**

Run: `python -m pytest server/tests -v`
Expected: all PASS. (Route ordering note: Flask's `<int:run_id>` converter won't swallow `/runs` — no conflict.)

- [ ] **Step 5: Commit**

```bash
git add server/routes.py server/tests/test_audit.py
git commit -m "feat: add filtered paginated runs list endpoint"
```

---

### Task 4: GET /api/runs/stats — aggregates

**Files:**
- Modify: `server/routes.py`
- Test: `server/tests/test_audit.py` (append)

**Interfaces:**
- Consumes: `_filtered_runs_query()` (Task 3).
- Produces: `GET /api/runs/stats` per the spec: `{total_runs, by_status, success_rate, avg_steps, avg_latency_ms, total_prompt_tokens, total_completion_tokens, tool_usage, runs_per_day, latency_buckets}` — same filters as the list, no pagination. `runs_per_day` entries carry exactly `date, completed, failed, declined, needs_confirmation`; sorted by date; only days with runs. Buckets per Global Constraints. Empty DB → zeros, `success_rate`/`avg_steps`/`avg_latency_ms` null, empty lists/objects.

- [ ] **Step 1: Write the failing tests** — append to `server/tests/test_audit.py`:

```python
def test_run_stats_aggregates(client, auth_headers, me):
    _seed_run(me, status="completed", latency=1500, tokens=(100, 10),
              created_at=datetime(2026, 8, 1, 9, tzinfo=timezone.utc))
    _seed_run(me, status="completed", latency=3000, tokens=(200, 20), tool="escalate",
              created_at=datetime(2026, 8, 1, 15, tzinfo=timezone.utc))
    _seed_run(me, status="failed", latency=16000, tokens=(300, 30),
              created_at=datetime(2026, 8, 2, 9, tzinfo=timezone.utc))
    _seed_run(me, status="declined", latency=6000, tokens=(0, 0),
              created_at=datetime(2026, 8, 2, 10, tzinfo=timezone.utc))

    stats = client.get("/api/runs/stats", headers=auth_headers).get_json()
    assert stats["total_runs"] == 4
    assert stats["by_status"] == {"completed": 2, "failed": 1, "declined": 1}
    assert stats["success_rate"] == pytest.approx(0.5)
    assert stats["avg_steps"] == pytest.approx(2.0)
    assert stats["avg_latency_ms"] == pytest.approx((1500 + 3000 + 16000 + 6000) / 4)
    assert stats["total_prompt_tokens"] == 600
    assert stats["total_completion_tokens"] == 60
    assert stats["tool_usage"] == {"search_knowledge": 3, "escalate": 1}
    assert stats["runs_per_day"] == [
        {"date": "2026-08-01", "completed": 2, "failed": 0, "declined": 0, "needs_confirmation": 0},
        {"date": "2026-08-02", "completed": 0, "failed": 1, "declined": 1, "needs_confirmation": 0},
    ]
    assert stats["latency_buckets"] == [
        {"label": "<2s", "count": 1},
        {"label": "2–5s", "count": 1},
        {"label": "5–15s", "count": 1},
        {"label": "15s+", "count": 1},
    ]

    # filters apply to stats too
    stats = client.get("/api/runs/stats?status=completed", headers=auth_headers).get_json()
    assert stats["total_runs"] == 2


def test_run_stats_empty(client, auth_headers):
    stats = client.get("/api/runs/stats", headers=auth_headers).get_json()
    assert stats["total_runs"] == 0
    assert stats["success_rate"] is None
    assert stats["avg_steps"] is None
    assert stats["avg_latency_ms"] is None
    assert stats["runs_per_day"] == []
    assert stats["tool_usage"] == {}
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest server/tests/test_audit.py -v`
Expected: new tests FAIL with 404.

- [ ] **Step 3: Implement** — add to `server/routes.py` (before the `/runs/<int:run_id>` routes for readability; Flask routing is unaffected either way):

```python
LATENCY_BUCKETS = [
    ("<2s", 0, 2000),
    ("2–5s", 2000, 5000),
    ("5–15s", 5000, 15000),
    ("15s+", 15000, None),
]


@api_bp.get("/runs/stats")
@require_auth
def run_stats():
    rows = _filtered_runs_query().all()
    runs = [(run.id, run.status, run.created_at, run.total_latency_ms) for run, _, _ in rows]
    run_ids = [r[0] for r in runs]

    by_status = {}
    for _, status, _, _ in runs:
        by_status[status] = by_status.get(status, 0) + 1
    completed = by_status.get("completed", 0)
    terminal = completed + by_status.get("failed", 0) + by_status.get("declined", 0)
    success_rate = (completed / terminal) if terminal else None

    total_steps = 0
    total_prompt = 0
    total_completion = 0
    tool_usage = {}
    if run_ids:
        total_steps, total_prompt, total_completion = (
            db.session.query(
                func.count(RunStep.id),
                func.coalesce(func.sum(RunStep.prompt_tokens), 0),
                func.coalesce(func.sum(RunStep.completion_tokens), 0),
            )
            .filter(RunStep.run_id.in_(run_ids))
            .one()
        )
        tool_usage = dict(
            db.session.query(RunStep.tool_name, func.count(RunStep.id))
            .filter(
                RunStep.run_id.in_(run_ids),
                RunStep.kind == "tool_call",
                RunStep.tool_name.isnot(None),
            )
            .group_by(RunStep.tool_name)
        )

    per_day = {}
    for _, status, created_at, _ in runs:
        day = created_at.date().isoformat()
        counts = per_day.setdefault(
            day, {"completed": 0, "failed": 0, "declined": 0, "needs_confirmation": 0}
        )
        if status in counts:
            counts[status] += 1
    runs_per_day = [
        {"date": day, **counts} for day, counts in sorted(per_day.items())
    ]

    latencies = [lat for _, _, _, lat in runs if lat is not None]
    latency_buckets = []
    for label, lo, hi in LATENCY_BUCKETS:
        count = sum(1 for lat in latencies if lat >= lo and (hi is None or lat < hi))
        latency_buckets.append({"label": label, "count": count})

    return jsonify(
        {
            "total_runs": len(runs),
            "by_status": by_status,
            "success_rate": success_rate,
            "avg_steps": (total_steps / len(runs)) if runs else None,
            "avg_latency_ms": (sum(latencies) / len(latencies)) if latencies else None,
            "total_prompt_tokens": int(total_prompt),
            "total_completion_tokens": int(total_completion),
            "tool_usage": tool_usage,
            "runs_per_day": runs_per_day,
            "latency_buckets": latency_buckets,
        }
    )
```

- [ ] **Step 4: Run the backend suite**

Run: `python -m pytest server/tests -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add server/routes.py server/tests/test_audit.py
git commit -m "feat: add run stats aggregate endpoint"
```

---

### Task 5: Client api/types + AuthContext is_admin

**Files:**
- Modify: `client/src/types.ts`, `client/src/api.ts`, `client/src/auth/AuthContext.tsx`, `client/src/tests/api.test.ts` (append), `client/src/tests/auth.test.tsx` (append)

**Interfaces:**
- Produces (used by Tasks 6–9):
  - types: `RunFilters {status?, conversationId?, dateFrom?, dateTo?, userEmail?, page?}`, `RunListItem {id, status, goal, conversation_id, conversation_title, model, step_count, total_latency_ms, prompt_tokens, completion_tokens, created_at, user_email?}`, `RunsPage {runs, total, page, per_page}`, `DayCounts {date, completed, failed, declined, needs_confirmation}`, `LatencyBucket {label, count}`, `RunStats {total_runs, by_status, success_rate, avg_steps, avg_latency_ms, total_prompt_tokens, total_completion_tokens, tool_usage, runs_per_day, latency_buckets}`.
  - api: `api.listRuns(f: RunFilters) -> RunsPage` hitting `/api/runs?...`; `api.getRunStats(f: RunFilters) -> RunStats` hitting `/api/runs/stats?...` (page is never included for stats); param names `status, conversation_id, date_from, date_to, user_email, page`, empty values omitted. `api.login` return type gains `email?: string; is_admin?: boolean`.
  - AuthContext: `useAuth()` additionally exposes `isAdmin: boolean`; login stores `agent_is_admin` = `"1"`/`"0"` in localStorage; logout removes it.

- [ ] **Step 1: Add types** — append to `client/src/types.ts`:

```typescript
export interface RunFilters {
  status?: string;
  conversationId?: number;
  dateFrom?: string;
  dateTo?: string;
  userEmail?: string;
  page?: number;
}

export interface RunListItem {
  id: number;
  status: string;
  goal: string;
  conversation_id: number;
  conversation_title: string;
  model: string | null;
  step_count: number;
  total_latency_ms: number | null;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
  user_email?: string;
}

export interface RunsPage {
  runs: RunListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface DayCounts {
  date: string;
  completed: number;
  failed: number;
  declined: number;
  needs_confirmation: number;
}

export interface LatencyBucket {
  label: string;
  count: number;
}

export interface RunStats {
  total_runs: number;
  by_status: Record<string, number>;
  success_rate: number | null;
  avg_steps: number | null;
  avg_latency_ms: number | null;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  tool_usage: Record<string, number>;
  runs_per_day: DayCounts[];
  latency_buckets: LatencyBucket[];
}
```

- [ ] **Step 2: Write the failing api tests** — append to `client/src/tests/api.test.ts`:

```typescript
test("listRuns builds the query string and omits empty filters", async () => {
  const fetchMock = stubFetch({
    "GET /api/runs?status=failed&date_from=2026-08-01&page=2": () =>
      jsonResponse({ runs: [], total: 0, page: 2, per_page: 20 }),
  });
  await api.listRuns({ status: "failed", dateFrom: "2026-08-01", page: 2 });
  expect(fetchMock).toHaveBeenCalledOnce();
});

test("getRunStats never sends page", async () => {
  stubFetch({
    "GET /api/runs/stats?status=failed": () =>
      jsonResponse({
        total_runs: 0, by_status: {}, success_rate: null, avg_steps: null,
        avg_latency_ms: null, total_prompt_tokens: 0, total_completion_tokens: 0,
        tool_usage: {}, runs_per_day: [], latency_buckets: [],
      }),
  });
  await api.getRunStats({ status: "failed", page: 3 });
});
```

- [ ] **Step 3: Implement api** — in `client/src/api.ts`, extend the types import with `RunFilters, RunsPage, RunStats`, change `login`'s generic to `{ token: string; email?: string; is_admin?: boolean }`, and add before `export const api`:

```typescript
function runQuery(filters: RunFilters, includePage: boolean): string {
  const p = new URLSearchParams();
  if (filters.status) p.set("status", filters.status);
  if (filters.conversationId) p.set("conversation_id", String(filters.conversationId));
  if (filters.dateFrom) p.set("date_from", filters.dateFrom);
  if (filters.dateTo) p.set("date_to", filters.dateTo);
  if (filters.userEmail) p.set("user_email", filters.userEmail);
  if (includePage && filters.page) p.set("page", String(filters.page));
  const s = p.toString();
  return s ? `?${s}` : "";
}
```

and inside `api`:

```typescript
  listRuns: (filters: RunFilters) =>
    apiFetch<RunsPage>(`/api/runs${runQuery(filters, true)}`),
  getRunStats: (filters: RunFilters) =>
    apiFetch<RunStats>(`/api/runs/stats${runQuery(filters, false)}`),
```

- [ ] **Step 4: Write the failing auth test** — append to `client/src/tests/auth.test.tsx`:

```tsx
test("login exposes the admin flag", async () => {
  localStorage.clear();
  stubFetch({
    "POST /api/auth/login": () =>
      jsonResponse({ token: "jwt-123", email: "a@b.com", is_admin: true }),
    "GET /api/conversations": () => jsonResponse([]),
  });
  renderApp();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.com");
  await userEvent.type(screen.getByLabelText(/password/i), "password123");
  await userEvent.click(screen.getByRole("button", { name: /log in/i }));
  await screen.findByRole("button", { name: /logout/i });
  expect(localStorage.getItem("agent_is_admin")).toBe("1");
});
```

- [ ] **Step 5: Implement AuthContext** — in `client/src/auth/AuthContext.tsx`:
  - `AuthValue` gains `isAdmin: boolean`.
  - Add state: `const [isAdmin, setIsAdmin] = useState<boolean>(() => localStorage.getItem("agent_is_admin") === "1");`
  - In `login` after the api call: `const admin = resp.is_admin === true; localStorage.setItem("agent_is_admin", admin ? "1" : "0"); setIsAdmin(admin);` (capture `const resp = await api.login(em, pw); const { token: t } = resp;`).
  - In BOTH logout paths (the 401 handler and `logout()`): `localStorage.removeItem("agent_is_admin"); setIsAdmin(false);`
  - Add `isAdmin` to the memo value and its dependency array.

- [ ] **Step 6: Run client tests + build**

Run: `cd client && npm test -- --run && npm run build`
Expected: all PASS, build clean.

- [ ] **Step 7: Commit**

```bash
git add client/src
git commit -m "feat: add runs/stats API client and admin flag in auth context"
```

---

### Task 6: Chat|Audit tabs, AuditPage, StatsCards

**Files:**
- Create: `client/src/audit/AuditPage.tsx`, `client/src/audit/StatsCards.tsx`, `client/src/tests/audit.test.tsx`
- Modify: `client/src/chat/AppPage.tsx` (tabs + view switch)

**Interfaces:**
- Consumes: `api.listRuns`/`api.getRunStats` (Task 5), `useAuth().isAdmin`, `errMsg` (exported from AppPage).
- Produces: `AuditPage` (default export, no props) — owns `filters: RunFilters` (initial `{page: 1}`), `runsPage`, `stats`, `conversations`, `selectedRunId`; fetches list (with page) and stats (without page) on every filters change; renders `StatsCards`, and placeholder slots that Tasks 7–9 fill: it must render `<StatsCards stats={stats} />` then a `<Box data-testid="charts-slot" />` then a `<Box data-testid="table-slot" />` (Tasks 7/8 replace the slots). `StatsCards` props `{stats: RunStats | null}`. AppPage: `Tabs` in the AppBar with values `"chat"`/`"audit"`; audit view replaces the drawer+chat+panel layout with full-width `<AuditPage />`.

- [ ] **Step 1: Write the failing tests** — create `client/src/tests/audit.test.tsx`:

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

export const EMPTY_STATS = {
  total_runs: 0, by_status: {}, success_rate: null, avg_steps: null,
  avg_latency_ms: null, total_prompt_tokens: 0, total_completion_tokens: 0,
  tool_usage: {}, runs_per_day: [], latency_buckets: [],
};

export const STATS = {
  total_runs: 4,
  by_status: { completed: 2, failed: 1, declined: 1 },
  success_rate: 0.5,
  avg_steps: 2.0,
  avg_latency_ms: 6625,
  total_prompt_tokens: 600,
  total_completion_tokens: 60,
  tool_usage: { search_knowledge: 3, escalate: 1 },
  runs_per_day: [
    { date: "2026-08-01", completed: 2, failed: 0, declined: 0, needs_confirmation: 0 },
    { date: "2026-08-02", completed: 0, failed: 1, declined: 1, needs_confirmation: 0 },
  ],
  latency_buckets: [
    { label: "<2s", count: 1 }, { label: "2–5s", count: 1 },
    { label: "5–15s", count: 1 }, { label: "15s+", count: 1 },
  ],
};

export const RUNS_PAGE = {
  runs: [
    {
      id: 17, status: "completed", goal: "Escalate ticket T-1",
      conversation_id: 1, conversation_title: "VPN ticket", model: "llama3.1:8b",
      step_count: 3, total_latency_ms: 5210, prompt_tokens: 1450,
      completion_tokens: 220, created_at: "2026-08-04T10:00:00",
    },
  ],
  total: 1, page: 1, per_page: 20,
};

export function renderAudit(extraRoutes: Parameters<typeof stubFetch>[0] = {}) {
  localStorage.setItem("agent_token", "jwt-123");
  localStorage.setItem("agent_email", "me@test.com");
  stubFetch({
    "GET /api/conversations": () => jsonResponse([]),
    "GET /api/runs?page=1": () => jsonResponse(RUNS_PAGE),
    "GET /api/runs/stats": () => jsonResponse(STATS),
    ...extraRoutes,
  });
  return render(
    <AuthProvider>
      <App />
    </AuthProvider>
  );
}

test("audit tab shows stat cards from the stats endpoint", async () => {
  renderAudit();
  await userEvent.click(await screen.findByRole("tab", { name: /audit/i }));
  expect(await screen.findByText("50%")).toBeInTheDocument(); // success rate
  expect(screen.getByText("4")).toBeInTheDocument(); // total runs
  expect(screen.getByText(/6\.6s/)).toBeInTheDocument(); // avg latency
});

test("chat tab is unaffected and switching back works", async () => {
  renderAudit();
  await userEvent.click(await screen.findByRole("tab", { name: /audit/i }));
  await screen.findByText("50%");
  await userEvent.click(screen.getByRole("tab", { name: /chat/i }));
  expect(
    await screen.findByText(/select or create a conversation/i)
  ).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd client && npm test -- --run src/tests/audit.test.tsx`
Expected: FAIL (no Audit tab exists).

- [ ] **Step 3: Create `client/src/audit/StatsCards.tsx`**

```tsx
import { Card, CardContent, Stack, Typography } from "@mui/material";
import type { RunStats } from "../types";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card sx={{ minWidth: 130, flex: 1 }}>
      <CardContent>
        <Typography variant="caption" color="text.secondary" sx={{ textTransform: "uppercase" }}>
          {label}
        </Typography>
        <Typography variant="h5">{value}</Typography>
      </CardContent>
    </Card>
  );
}

export default function StatsCards({ stats }: { stats: RunStats | null }) {
  const fmt = (v: number | null, f: (n: number) => string) => (v == null ? "—" : f(v));
  return (
    <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap" sx={{ my: 2 }}>
      <StatCard label="Total runs" value={stats ? String(stats.total_runs) : "—"} />
      <StatCard
        label="Success rate"
        value={stats ? fmt(stats.success_rate, (n) => `${Math.round(n * 100)}%`) : "—"}
      />
      <StatCard
        label="Avg steps"
        value={stats ? fmt(stats.avg_steps, (n) => n.toFixed(1)) : "—"}
      />
      <StatCard
        label="Avg latency"
        value={stats ? fmt(stats.avg_latency_ms, (n) => `${(n / 1000).toFixed(1)}s`) : "—"}
      />
      <StatCard
        label="Tokens (prompt / completion)"
        value={
          stats
            ? `${stats.total_prompt_tokens.toLocaleString()} / ${stats.total_completion_tokens.toLocaleString()}`
            : "—"
        }
      />
      <StatCard
        label="Failed + declined"
        value={
          stats
            ? String((stats.by_status["failed"] ?? 0) + (stats.by_status["declined"] ?? 0))
            : "—"
        }
      />
    </Stack>
  );
}
```

- [ ] **Step 4: Create `client/src/audit/AuditPage.tsx`**

```tsx
import { Box, Snackbar, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { api } from "../api";
import { errMsg } from "../chat/AppPage";
import type { Conversation, RunFilters, RunsPage, RunStats } from "../types";
import StatsCards from "./StatsCards";

export default function AuditPage() {
  const [filters, setFilters] = useState<RunFilters>({ page: 1 });
  const [runsPage, setRunsPage] = useState<RunsPage | null>(null);
  const [stats, setStats] = useState<RunStats | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [snack, setSnack] = useState<string | null>(null);

  useEffect(() => {
    api.listConversations().then(setConversations).catch(() => {});
  }, []);

  useEffect(() => {
    api.listRuns(filters).then(setRunsPage).catch((e) => setSnack(errMsg(e)));
    api.getRunStats(filters).then(setStats).catch((e) => setSnack(errMsg(e)));
  }, [filters]);

  return (
    <Box sx={{ p: 3, maxWidth: 1200, mx: "auto" }}>
      <Typography variant="h5" gutterBottom>
        Run audit
      </Typography>
      <StatsCards stats={stats} />
      <Box data-testid="charts-slot" />
      <Box data-testid="table-slot" />
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

(The unused `runsPage`/`conversations`/`selectedRunId`/`setFilters` are consumed by Tasks 8–9; if `noUnusedLocals` complains at this stage, reference them in the slot boxes: `<Box data-testid="table-slot">{runsPage?.total ?? 0}{conversations.length}{selectedRunId}</Box>` and pass `setFilters` nowhere — instead silence with `void setFilters;` on a line inside the component. Remove these shims in Task 8.)

- [ ] **Step 5: Wire tabs into `client/src/chat/AppPage.tsx`**

Add imports: `Tab, Tabs` from `@mui/material`, `AuditPage` from `"../audit/AuditPage"`. Add state: `const [view, setView] = useState<"chat" | "audit">("chat");`

In the AppBar `<Toolbar>`, after the title `Typography`, insert:

```tsx
          <Tabs
            value={view}
            onChange={(_, v: "chat" | "audit") => setView(v)}
            textColor="inherit"
            indicatorColor="secondary"
            sx={{ flexGrow: 1 }}
          >
            <Tab value="chat" label="Chat" />
            <Tab value="audit" label="Audit" />
          </Tabs>
```

and remove `sx={{ flexGrow: 1 }}` from the title Typography.

Wrap the existing layout: when `view === "audit"`, render instead of the Drawer/ChatView/Divider/TracePanel block:

```tsx
        <Box component="main" sx={{ flexGrow: 1, overflowY: "auto" }}>
          <Toolbar />
          <AuditPage />
        </Box>
```

Keep the Snackbar at the AppPage level rendered in both views.

- [ ] **Step 6: Run client tests + build**

Run: `cd client && npm test -- --run && npm run build`
Expected: all PASS (including the two new audit tests), build clean.

- [ ] **Step 7: Commit**

```bash
git add client/src
git commit -m "feat: add audit tab with run health stat cards"
```

---

### Task 7: ChartsRow (recharts)

**Files:**
- Create: `client/src/audit/ChartsRow.tsx`
- Modify: `client/package.json` (add recharts), `client/src/audit/AuditPage.tsx` (replace charts-slot), `client/src/tests/audit.test.tsx` (append)

**Interfaces:**
- Consumes: `RunStats` (Task 5), `stats` from AuditPage (Task 6).
- Produces: `ChartsRow` props `{stats: RunStats | null}` — two Papers with `data-testid="runs-per-day-chart"` and `data-testid="latency-chart"`; when `stats` is null or `total_runs === 0` renders only the empty-state text `No run data yet — charts appear once the agent has handled a few goals.`; status colors: completed `#2e7d32`, failed `#d32f2f`, declined `#9e9e9e`, needs_confirmation `#ed6c02` (matches the MUI chip palette used by TracePanel).

- [ ] **Step 1: Install recharts**

Run: `cd client && npm install recharts`
Expected: added to `dependencies`, no peer errors.

- [ ] **Step 2: Write the failing tests** — append to `client/src/tests/audit.test.tsx`:

```tsx
test("audit tab renders both charts when there is data", async () => {
  renderAudit();
  await userEvent.click(await screen.findByRole("tab", { name: /audit/i }));
  expect(await screen.findByTestId("runs-per-day-chart")).toBeInTheDocument();
  expect(screen.getByTestId("latency-chart")).toBeInTheDocument();
});

test("audit tab shows chart empty state with no runs", async () => {
  renderAudit({
    "GET /api/runs?page=1": () =>
      jsonResponse({ runs: [], total: 0, page: 1, per_page: 20 }),
    "GET /api/runs/stats": () => jsonResponse(EMPTY_STATS),
  });
  await userEvent.click(await screen.findByRole("tab", { name: /audit/i }));
  expect(await screen.findByText(/no run data yet/i)).toBeInTheDocument();
  expect(screen.queryByTestId("runs-per-day-chart")).not.toBeInTheDocument();
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd client && npm test -- --run src/tests/audit.test.tsx`
Expected: the two new tests FAIL.

- [ ] **Step 4: Create `client/src/audit/ChartsRow.tsx`**

```tsx
import { Paper, Stack, Typography } from "@mui/material";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RunStats } from "../types";

const STATUS_COLORS = {
  completed: "#2e7d32",
  failed: "#d32f2f",
  declined: "#9e9e9e",
  needs_confirmation: "#ed6c02",
} as const;

export default function ChartsRow({ stats }: { stats: RunStats | null }) {
  if (!stats || stats.total_runs === 0) {
    return (
      <Typography color="text.secondary" sx={{ my: 2 }}>
        No run data yet — charts appear once the agent has handled a few goals.
      </Typography>
    );
  }
  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ my: 2 }}>
      <Paper sx={{ flex: 1, p: 2, height: 300 }} data-testid="runs-per-day-chart">
        <Typography variant="subtitle2" gutterBottom>
          Runs per day
        </Typography>
        <ResponsiveContainer width="100%" height="88%">
          <BarChart data={stats.runs_per_day}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="date" fontSize={11} />
            <YAxis allowDecimals={false} fontSize={11} />
            <Tooltip />
            <Legend />
            {(Object.keys(STATUS_COLORS) as Array<keyof typeof STATUS_COLORS>).map(
              (status) => (
                <Bar key={status} dataKey={status} stackId="day" fill={STATUS_COLORS[status]} />
              )
            )}
          </BarChart>
        </ResponsiveContainer>
      </Paper>
      <Paper sx={{ flex: 1, p: 2, height: 300 }} data-testid="latency-chart">
        <Typography variant="subtitle2" gutterBottom>
          Run latency distribution
        </Typography>
        <ResponsiveContainer width="100%" height="88%">
          <BarChart data={stats.latency_buckets}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="label" fontSize={11} />
            <YAxis allowDecimals={false} fontSize={11} />
            <Tooltip />
            <Bar dataKey="count" fill="#1976d2" />
          </BarChart>
        </ResponsiveContainer>
      </Paper>
    </Stack>
  );
}
```

- [ ] **Step 5: Replace the slot** — in `AuditPage.tsx`, import `ChartsRow` and replace `<Box data-testid="charts-slot" />` with `<ChartsRow stats={stats} />`.

- [ ] **Step 6: Run client tests + build**

Run: `cd client && npm test -- --run && npm run build`
Expected: all PASS, build clean.

- [ ] **Step 7: Commit**

```bash
git add client/src client/package.json client/package-lock.json
git commit -m "feat: add runs-per-day and latency charts to audit view"
```

---

### Task 8: RunsTable — filters, rows, pagination

**Files:**
- Create: `client/src/audit/RunsTable.tsx`
- Modify: `client/src/audit/AuditPage.tsx` (replace table-slot, remove Task 6 shims), `client/src/tests/audit.test.tsx` (append)

**Interfaces:**
- Consumes: `RunsPage`, `RunFilters`, `Conversation` types; AuditPage state.
- Produces: `RunsTable` props exactly:

```typescript
interface RunsTableProps {
  page: RunsPage | null;
  filters: RunFilters;
  onFiltersChange: (f: RunFilters) => void;
  conversations: Conversation[];
  isAdmin: boolean;
  onOpenRun: (runId: number) => void;
}
```

Filter changes reset `page` to 1; the pagination control sets `page`. Admin-only: `User email` filter TextField (applies on Enter/blur) and a `User` column. Status chips reuse the color mapping (completed=success, needs_confirmation=warning, failed=error, declined=default).

- [ ] **Step 1: Write the failing tests** — append to `client/src/tests/audit.test.tsx`:

```tsx
test("runs table renders rows and drives filters", async () => {
  const routes = {
    "GET /api/runs?status=failed&page=1": () =>
      jsonResponse({ runs: [], total: 0, page: 1, per_page: 20 }),
    "GET /api/runs/stats?status=failed": () => jsonResponse(EMPTY_STATS),
  };
  renderAudit(routes);
  await userEvent.click(await screen.findByRole("tab", { name: /audit/i }));
  expect(await screen.findByText("Escalate ticket T-1")).toBeInTheDocument();
  expect(screen.getByText("5.2s")).toBeInTheDocument();

  // no admin column for regular users
  expect(screen.queryByText(/user email/i)).not.toBeInTheDocument();

  await userEvent.click(screen.getByLabelText(/status filter/i));
  await userEvent.click(await screen.findByRole("option", { name: /^failed$/i }));
  expect(await screen.findByText(/no runs match these filters/i)).toBeInTheDocument();
});

test("admin sees the user column and email filter", async () => {
  localStorage.setItem("agent_is_admin", "1");
  renderAudit({
    "GET /api/runs?page=1": () =>
      jsonResponse({
        ...RUNS_PAGE,
        runs: [{ ...RUNS_PAGE.runs[0], user_email: "someone@test.com" }],
      }),
  });
  await userEvent.click(await screen.findByRole("tab", { name: /audit/i }));
  expect(await screen.findByText("someone@test.com")).toBeInTheDocument();
  expect(screen.getByLabelText(/user email/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd client && npm test -- --run src/tests/audit.test.tsx`
Expected: new tests FAIL.

- [ ] **Step 3: Create `client/src/audit/RunsTable.tsx`**

```tsx
import {
  Box,
  Chip,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import type { Conversation, RunFilters, RunsPage } from "../types";

const STATUS_CHIP: Record<string, "success" | "warning" | "error" | "default"> = {
  completed: "success",
  needs_confirmation: "warning",
  failed: "error",
  declined: "default",
};

const STATUSES = ["completed", "failed", "declined", "needs_confirmation", "running"];

interface RunsTableProps {
  page: RunsPage | null;
  filters: RunFilters;
  onFiltersChange: (f: RunFilters) => void;
  conversations: Conversation[];
  isAdmin: boolean;
  onOpenRun: (runId: number) => void;
}

export default function RunsTable({
  page,
  filters,
  onFiltersChange,
  conversations,
  isAdmin,
  onOpenRun,
}: RunsTableProps) {
  const patch = (p: Partial<RunFilters>) =>
    onFiltersChange({ ...filters, ...p, page: 1 });

  return (
    <Paper sx={{ p: 2 }}>
      <Stack direction="row" spacing={2} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="Status"
          value={filters.status ?? ""}
          onChange={(e) => patch({ status: e.target.value || undefined })}
          sx={{ minWidth: 180 }}
          slotProps={{ htmlInput: { "aria-label": "status filter" } }}
        >
          <MenuItem value="">All statuses</MenuItem>
          {STATUSES.map((s) => (
            <MenuItem key={s} value={s}>
              {s}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label="Conversation"
          value={filters.conversationId ?? ""}
          onChange={(e) =>
            patch({ conversationId: e.target.value ? Number(e.target.value) : undefined })
          }
          sx={{ minWidth: 180 }}
        >
          <MenuItem value="">All conversations</MenuItem>
          {conversations.map((c) => (
            <MenuItem key={c.id} value={c.id}>
              {c.title}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="From"
          type="date"
          value={filters.dateFrom ?? ""}
          onChange={(e) => patch({ dateFrom: e.target.value || undefined })}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          label="To"
          type="date"
          value={filters.dateTo ?? ""}
          onChange={(e) => patch({ dateTo: e.target.value || undefined })}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        {isAdmin && (
          <TextField
            size="small"
            label="User email"
            defaultValue={filters.userEmail ?? ""}
            onBlur={(e) => patch({ userEmail: e.target.value || undefined })}
            onKeyDown={(e) => {
              if (e.key === "Enter")
                patch({ userEmail: (e.target as HTMLInputElement).value || undefined });
            }}
          />
        )}
      </Stack>
      {page && page.runs.length === 0 ? (
        <Typography color="text.secondary" sx={{ py: 3, textAlign: "center" }}>
          No runs match these filters.
        </Typography>
      ) : (
        <Box sx={{ overflowX: "auto" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Time</TableCell>
                {isAdmin && <TableCell>User</TableCell>}
                <TableCell>Goal</TableCell>
                <TableCell>Status</TableCell>
                <TableCell align="right">Steps</TableCell>
                <TableCell align="right">Latency</TableCell>
                <TableCell align="right">Tokens</TableCell>
                <TableCell>Conversation</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {(page?.runs ?? []).map((run) => (
                <TableRow
                  key={run.id}
                  hover
                  sx={{ cursor: "pointer" }}
                  onClick={() => onOpenRun(run.id)}
                >
                  <TableCell>{new Date(run.created_at).toLocaleString()}</TableCell>
                  {isAdmin && <TableCell>{run.user_email}</TableCell>}
                  <TableCell sx={{ maxWidth: 320, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {run.goal}
                  </TableCell>
                  <TableCell>
                    <Chip size="small" label={run.status} color={STATUS_CHIP[run.status] ?? "default"} />
                  </TableCell>
                  <TableCell align="right">{run.step_count}</TableCell>
                  <TableCell align="right">
                    {run.total_latency_ms != null ? `${(run.total_latency_ms / 1000).toFixed(1)}s` : "—"}
                  </TableCell>
                  <TableCell align="right">
                    {run.prompt_tokens + run.completion_tokens}
                  </TableCell>
                  <TableCell>{run.conversation_title}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      )}
      <TablePagination
        component="div"
        count={page?.total ?? 0}
        page={(page?.page ?? 1) - 1}
        onPageChange={(_, newPage) => onFiltersChange({ ...filters, page: newPage + 1 })}
        rowsPerPage={page?.per_page ?? 20}
        rowsPerPageOptions={[20]}
      />
    </Paper>
  );
}
```

- [ ] **Step 4: Wire into AuditPage** — replace `<Box data-testid="table-slot" />` (and remove any Task 6 shims) with:

```tsx
      <RunsTable
        page={runsPage}
        filters={filters}
        onFiltersChange={setFilters}
        conversations={conversations}
        isAdmin={isAdmin}
        onOpenRun={setSelectedRunId}
      />
```

adding `const { isAdmin } = useAuth();` (import `useAuth` from `"../auth/AuthContext"`) and the `RunsTable` import.

- [ ] **Step 5: Run client tests + build**

Run: `cd client && npm test -- --run && npm run build`
Expected: all PASS, build clean.

- [ ] **Step 6: Commit**

```bash
git add client/src
git commit -m "feat: add filterable paginated runs table to audit view"
```

---

### Task 9: RunDrawer + JSON export, docs, full verification

**Files:**
- Create: `client/src/audit/RunDrawer.tsx`
- Modify: `client/src/audit/AuditPage.tsx` (mount drawer), `client/src/tests/audit.test.tsx` (append), `README.md` (observability blurb), `CLAUDE.md` (audit surface note)

**Interfaces:**
- Consumes: `api.getRun` (existing), `TracePanel` (existing — rendered read-only with `onConfirm` no-op and `busy=false`), `RunDetail`.
- Produces: `RunDrawer` props `{runId: number | null; onClose: () => void}` — right-anchored MUI Drawer, open when `runId != null`; fetches `GET /api/runs/<id>` on open; header `Run #<id>` + Download JSON button (client-side Blob, filename `run-<id>.json`) + close; body renders `TracePanel`.

- [ ] **Step 1: Write the failing tests** — append to `client/src/tests/audit.test.tsx`:

```tsx
test("clicking a run opens the drawer with steps and JSON export", async () => {
  const createObjectURL = vi.fn(() => "blob:fake");
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL,
    revokeObjectURL: vi.fn(),
  });
  renderAudit({
    "GET /api/runs/17": () =>
      jsonResponse({
        id: 17, status: "completed", model: "llama3.1:8b",
        total_latency_ms: 5210, created_at: "2026-08-04T10:00:00",
        steps: [
          {
            seq: 1, kind: "tool_call", tool_name: "search_knowledge",
            arguments: { query: "sla" }, result: { answer: "24h" }, latency_ms: 230,
          },
        ],
      }),
  });
  await userEvent.click(await screen.findByRole("tab", { name: /audit/i }));
  await userEvent.click(await screen.findByText("Escalate ticket T-1"));
  expect(await screen.findByText(/#1 · search_knowledge/i)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /download json/i }));
  expect(createObjectURL).toHaveBeenCalledOnce();
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd client && npm test -- --run src/tests/audit.test.tsx`
Expected: new test FAILS.

- [ ] **Step 3: Create `client/src/audit/RunDrawer.tsx`**

```tsx
import CloseIcon from "@mui/icons-material/Close";
import DownloadIcon from "@mui/icons-material/Download";
import { Box, Button, Drawer, IconButton, Stack, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { api } from "../api";
import TracePanel from "../trace/TracePanel";
import type { RunDetail } from "../types";

interface Props {
  runId: number | null;
  onClose: () => void;
}

export default function RunDrawer({ runId, onClose }: Props) {
  const [detail, setDetail] = useState<RunDetail | null>(null);

  useEffect(() => {
    setDetail(null);
    if (runId != null) {
      api.getRun(runId).then(setDetail).catch(() => {});
    }
  }, [runId]);

  const download = () => {
    if (!detail) return;
    const blob = new Blob([JSON.stringify(detail, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `run-${detail.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Drawer anchor="right" open={runId != null} onClose={onClose}>
      <Box sx={{ width: 460, maxWidth: "90vw" }}>
        <Stack direction="row" alignItems="center" spacing={1} sx={{ p: 2, pb: 0 }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Run #{runId}
          </Typography>
          <Button
            size="small"
            startIcon={<DownloadIcon />}
            onClick={download}
            disabled={!detail}
          >
            Download JSON
          </Button>
          <IconButton onClick={onClose} aria-label="close">
            <CloseIcon />
          </IconButton>
        </Stack>
        <TracePanel
          panel={
            detail
              ? {
                  runId: detail.id,
                  status: detail.status,
                  steps: detail.steps,
                  pendingAction: detail.pending_action,
                  totalLatencyMs: detail.total_latency_ms,
                }
              : null
          }
          busy={false}
          onConfirm={() => {}}
        />
      </Box>
    </Drawer>
  );
}
```

- [ ] **Step 4: Mount in AuditPage** — add the import and, after `<RunsTable …/>`:

```tsx
      <RunDrawer runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
```

- [ ] **Step 5: Docs** — `README.md`: in requirement-facing docs, extend the observability mention: after the Quick start section add nothing; instead, in §6's context users read the code — just update `CLAUDE.md`: under Architecture/commands, add one line to the What-this-repo-is paragraph noting the client's Audit tab (runs explorer with stats/charts, admin via `ADMIN_EMAILS`), and add `ADMIN_EMAILS` to the documented env vars list in the Commands section if one exists. In `README.md`'s §7 evaluation section, append a sentence: "The app's **Audit tab** (client) is the built-in run viewer: per-run traces, success rate, latency and token stats — use it when scoring eval runs."

- [ ] **Step 6: Full verification**

Run:
```bash
source .venv/bin/activate && python -m pytest server/tests -v
cd client && npm test -- --run && npm run build
```
Expected: both suites fully green, build clean.

- [ ] **Step 7: Commit**

```bash
git add client/src README.md CLAUDE.md
git commit -m "feat: add run drill-down drawer with JSON export and audit docs"
```

---

## Self-Review Notes

- **Spec coverage:** token capture (T1), admin model + login flag (T2), list endpoint incl. isolation + `user_email` filter (T3), stats endpoint incl. buckets/per-day/tool usage/empty shape (T4), client api/types + `isAdmin` context (T5), tabs + AuditPage + StatsCards (T6), recharts ChartsRow with status colors + empty states (T7), RunsTable filters/pagination/admin column (T8), RunDrawer reuse of TracePanel + Blob export + docs (T9). Spec's "stats and list load independently" honored by separate `.then/.catch` chains in AuditPage.
- **Type consistency checked:** `RunFilters`/`RunsPage`/`RunStats` defined once (T5) and used in T6–T8 with identical fields; `runQuery` param names match the backend's (T3/T4); `data-testid` slot names introduced in T6 are replaced in T7/T8; `STATUS_CHIP` map matches TracePanel's existing mapping; bucket labels identical in T4 backend and T4 test (`2–5s` uses an en-dash — keep it byte-identical in both).
- **Known snags pre-empted:** existing `test_llm` equality assertions updated in T1 (usage key); `noUnusedLocals` interim shims documented in T6 and removed in T8; recharts renders zero-size in jsdom so tests assert container presence/empty-state text, never SVG geometry; `/runs/stats` cannot be shadowed by `/runs/<int:run_id>` (int converter).
