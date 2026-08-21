"""SQLAlchemy database models.

How the tables relate (one line per arrow = one foreign key):

    User ─┬─< Conversation ─< Message
          │        │
          │        └─< Run ─┬─< RunStep        (the visible agent trace)
          │                 └─< PendingAction  (tool call awaiting user OK)
          ├─< GuardrailEvent (pre-run rejections — no Run exists yet)
          └─< Ticket

A "Run" is one execution of the agent loop for one user goal. Every LLM call
and tool call inside it is persisted as a RunStep — that's the observability
requirement: the whole trace can be replayed from the DB.

"""

import secrets
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

# Shared SQLAlchemy handle; bound to the Flask app in app.py via db.init_app().
db = SQLAlchemy()


def utcnow():
    """Timezone-aware 'now' — used as the default for every created_at column.

    (datetime.utcnow() is naive and deprecated; this is the safe replacement.)
    """
    return datetime.now(timezone.utc)


def new_trace_id():
    """A random 128-bit id, 32 lowercase hex chars — the trace_id half of a
    W3C traceparent. Minted once per Run so every RunStep's OTel span (see
    tracing.py) can share it, giving the whole run one real trace_id even
    though it never leaves this one Flask process."""
    return secrets.token_hex(16)


class User(db.Model):
    """An account that can log in. Admin status is NOT stored here — it is
    derived at request time from Config.ADMIN_EMAILS (see auth.require_auth)."""

    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)  # bcrypt, never plaintext
    # Profile fields shown in the UI; defaults match the demo persona.
    full_name = db.Column(db.String(120), default="Support Specialist")
    department = db.Column(db.String(100), default="HR Operations")
    role_title = db.Column(db.String(100), default="Lead Support Specialist")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class Conversation(db.Model):
    """A chat thread grouping messages and agent runs for one user."""

    __tablename__ = "conversations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), default="New conversation")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    # conversation.messages gives the thread in chronological (insertion) order.
    messages = db.relationship("Message", backref="conversation", order_by="Message.id")


class Message(db.Model):
    """One chat turn inside a conversation (either side of the dialogue)."""

    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    role = db.Column(db.String(16), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class Run(db.Model):
    """One execution of the agent loop, triggered by one user message.

    Status lifecycle:
        running -> completed            (agent produced a final answer)
                -> failed               (step cap hit, model down, bad tool calls)
                -> needs_confirmation   (paused; a PendingAction awaits the user)
                -> stopped              (user cancelled mid-flight)
                -> declined             (user rejected the pending action)
    """

    __tablename__ = "runs"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    # The user Message that kicked this run off (its content is the "goal").
    user_message_id = db.Column(db.Integer, db.ForeignKey("messages.id"), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="running")
    model = db.Column(db.String(128))          # which LLM served this run
    # feat/obs-provider-error-type: gen_ai.provider.name — "ollama" (default)
    # or "openai_compatible" (hosted).
    provider = db.Column(db.String(32))
    total_latency_ms = db.Column(db.Integer)   # sum of step latencies, set on finish
    # SHA-256 of the system prompt template actually used (set once, when the
    # run starts) — lets an auditor detect prompt drift ("this run's hash
    # doesn't match last week's") without storing the prompt text a second
    # time; the full text already lives in the first llm_call RunStep.
    system_prompt_hash = db.Column(db.String(64))
    # SHA-256 of the final answer shown to the user, set when the run
    # terminates — an integrity fingerprint for "what the user actually saw,"
    # independent of the plaintext Message row.
    final_output_hash = db.Column(db.String(64))
    # feat/otel-tracing: W3C trace_id (32 hex chars) shared by every RunStep's
    # OTel span — see tracing.py. Minted once here so it survives across the
    # separate HTTP request that resumes a HITL-paused run.
    trace_id = db.Column(db.String(32), default=new_trace_id)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    # run.steps yields the trace in execution order (seq 1, 2, 3, ...).
    steps = db.relationship("RunStep", backref="run", order_by="RunStep.seq")


class RunStep(db.Model):
    """One entry in the agent trace: a single LLM call or tool call.

    Written exclusively by observability.record_step(), which also measures
    latency and captures token usage. `llm_messages` stores the full prompt
    sent to the model for llm_call steps — that's what makes runs resumable
    (see agent.resume_run) and fully auditable in the UI.

    feat/obs-provider-error-type: maps loosely to an OTel GenAI span
    (duration_ms → latency_ms, error.type → error_type). Token counts stay
    as the provider total (not four layers).
    """

    __tablename__ = "run_steps"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("runs.id"), nullable=False)
    seq = db.Column(db.Integer, nullable=False)      # 1-based position within the run
    kind = db.Column(db.String(16), nullable=False)  # llm_call | tool_call | system_event
    tool_name = db.Column(db.String(64))             # tool_call steps only
    arguments = db.Column(db.JSON)                   # tool arguments as passed
    result = db.Column(db.JSON)                      # tool result or LLM decision / {"error": ...}
    llm_messages = db.Column(db.JSON)                # full prompt for llm_call steps
    latency_ms = db.Column(db.Integer)
    prompt_tokens = db.Column(db.Integer)            # token usage reported by the model
    completion_tokens = db.Column(db.Integer)
    # feat/obs-provider-error-type: error.type (OTel) — Timeout | ConnectionError | …
    error_type = db.Column(db.String(64))
    # SHA-256 fingerprints of `arguments`/`result`, computed alongside them in
    # observability.record_step() — the hash gives every step an integrity
    # fingerprint that can be verified, shipped to an external log store, or
    # compared across runs without re-reading (or re-exposing) the plaintext.
    arguments_hash = db.Column(db.String(64))
    result_hash = db.Column(db.String(64))
    # feat/otel-tracing: this step's own OTel span id (16 hex chars), a child
    # of its Run's trace_id — the pair (Run.trace_id, span_id) is this step's
    # W3C-shaped coordinate, pasteable into any OTel-speaking backend.
    span_id = db.Column(db.String(16))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class PendingAction(db.Model):
    """A consequential tool call (create/send/escalate) paused for user approval.

    The guardrail flow: agent loop hits a tool with requires_confirmation=True,
    writes one of these with status='pending', and sets the run to
    'needs_confirmation'. The confirm endpoint later flips status to
    'approved'/'rejected' and calls agent.resume_run().
    """

    __tablename__ = "pending_actions"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("runs.id"), nullable=False)
    tool_name = db.Column(db.String(64), nullable=False)
    arguments = db.Column(db.JSON)
    status = db.Column(db.String(16), nullable=False, default="pending")  # pending | approved | rejected
    resolved_at = db.Column(db.DateTime(timezone=True))


class GuardrailEvent(db.Model):
    """A guardrail firing — currently just sanitization.reject_if_injection's
    regex blocklist, but the table shape doesn't assume that's the only one.

    Deliberately NOT tied to a Run: prompt-injection rejection happens at the
    HTTP entry point BEFORE a Conversation/Message/Run exists (the request is
    rejected outright), so there is no run_id to attach this to yet. Scoped
    to user_id instead, which @require_auth guarantees is always available.


    """

    __tablename__ = "guardrail_events"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Which call site fired this ("chat" | "triage") — mirrors the `source`
    # kwarg already passed to reject_if_injection.
    source = db.Column(db.String(32), nullable=False)
    # The regex pattern that matched — the "filter" in the audit schema sense
    # (which rule fired), not the user's raw text.
    filter_name = db.Column(db.Text, nullable=False)
    # Deterministic regex match, not a scored classifier, so this is always
    # 1.0 today — the column exists so a future probabilistic filter (see
    # sanitization.py's own docstring: "a classifier can be added later")
    # doesn't need a schema change to report a real confidence score.
    score = db.Column(db.Float, nullable=False, default=1.0)
    # Always "blocked" today (the only action reject_if_injection takes);
    # kept as a field, not a hardcoded assumption, for the same reason.
    action = db.Column(db.String(16), nullable=False, default="blocked")
    # Hash, not the offending text itself — an injection probe is exactly the
    # kind of content an audit log shouldn't store verbatim.
    input_hash = db.Column(db.String(64))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class Ticket(db.Model):
    """A support ticket in the demo HR helpdesk (the domain the agent works on).

    Tickets are seeded per user at registration (routes.seed_apexcare_tickets)
    and mutated by the agent's tools (escalate) and the REST API.
    """

    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), default="APX-1001")  # human-facing ID
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Who filed the ticket (the fictional employee, not the logged-in user).
    requester_name = db.Column(db.String(120), default="Jane Doe")
    requester_email = db.Column(db.String(120), default="jane.doe@apexcare.tech")
    requester_department = db.Column(db.String(100), default="Commercial Operations")
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, default="open")  # open | in_triage | draft_pending | escalated | resolved
    priority = db.Column(db.String(20), nullable=False, default="medium")  # low | medium | high | urgent
    category = db.Column(db.String(50), nullable=False, default="HR & Benefits")  # HR & Benefits | IT Support | Billing & Expenses | General
    channel = db.Column(db.String(50), default="Workday Portal")  # Workday Portal | Slack HR Connect | Email | Helpdesk
    sla_minutes_remaining = db.Column(db.Integer, default=120)
    # Agent output: the drafted reply awaiting review, and its confidence score.
    draft_reply = db.Column(db.Text, nullable=True)
    draft_confidence = db.Column(db.Integer, default=95)
    escalation_reason = db.Column(db.Text, nullable=True)
    # Replies already sent, stored as a JSON-encoded list of strings
    # (kept as TEXT instead of a child table for simplicity).
    replies_json = db.Column(db.Text, nullable=True)
    resolution_notes = db.Column(db.Text)
    # Set once the resolved ticket has been pushed into AnythingLLM
    # (knowledge_sync.py) so it is never re-embedded.
    kb_synced_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = db.relationship("User", backref="tickets")
