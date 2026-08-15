"""All non-auth HTTP endpoints, mounted under /api (see app.py).

Roadmap of this file:

  Audit / observability UI
    GET  /runs/stats            aggregate stats + chart data for the Audit tab
    GET  /runs                  paginated run list (admins see all users)
    GET  /runs/<id>             one run with its full step trace
    POST /runs/<id>/stop        cancel a run mid-flight

  Tickets (the demo HR helpdesk domain)
    GET   /tickets              list the user's tickets
    GET   /tickets/<id>         single ticket
    PATCH /tickets/<id>         edit fields / append a sent reply
    POST  /tickets/reset        wipe & reseed demo data
    POST  /tickets/<id>/triage  run the AGENT LOOP on a ticket  <-- key endpoint

  Other
    GET  /knowledge-base        list files in knowledge_base/ for the KB tab
    POST /chat                  the "Pip" chat widget (fixed pipeline, no loop)

Every endpoint is wrapped in @require_auth, which provides g.user/g.is_admin.
"""

import json
import os
from datetime import date
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import func

from server.agent import resume_run, run_agent
from server.auth import require_auth
from server.llm import generate
from server.models import Conversation, Message, PendingAction, Run, RunStep, Ticket, User, db, utcnow
from server.observability import record_step
from server.tools import create_draft as create_draft
from server.tools.search_knowledge import search_knowledge
from server.urgency import apply_priority, build_urgency_messages, classify_priority
from server.sanitization import reject_if_injection
from server.utils import is_client_disconnected
from server.prompts import (
    TRIAGE_USER_PROMPT,
    PIP_CLASSIFICATION_PROMPT,
    PIP_SYSTEM_PROMPT,
    PIP_SYSTEM_PROMPT_NO_POLICY_MATCH,
)


api_bp = Blueprint("api", __name__, url_prefix="/api")


# --------------------------------------------------------------------------
# Serialization helpers (ORM rows -> JSON-safe dicts for the frontend)
# --------------------------------------------------------------------------

def _serialize_steps(run, include_messages=False):
    """The run's trace, in execution order. `include_messages` additionally
    ships the full LLM prompt of each llm_call step (heavy, so opt-in —
    only the run-detail endpoint asks for it)."""
    steps = RunStep.query.filter_by(run_id=run.id).order_by(RunStep.seq).all()
    out = []
    for s in steps:
        item = {
            "seq": s.seq,
            "kind": s.kind,
            "tool_name": s.tool_name,
            "arguments": s.arguments,
            "result": s.result,
            "latency_ms": s.latency_ms,
        }
        if include_messages:
            item["llm_messages"] = s.llm_messages
        out.append(item)
    return out


def _serialize_run(run):
    return {
        "run_id": run.id,
        "status": run.status,
        "model": run.model,
        "total_latency_ms": run.total_latency_ms,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _owned_run(run_id):
    """Fetch a run only if it belongs to the current user (via its
    conversation). Returns None otherwise — the ownership check for
    non-admin access."""
    return (
        Run.query.join(Conversation, Run.conversation_id == Conversation.id)
        .filter(Run.id == run_id, Conversation.user_id == g.user.id)
        .first()
    )


def _parse_iso_date(value):
    """'2026-08-14' -> date, anything else -> None (bad input is ignored,
    not a 400)."""
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _filtered_runs_query():
    """(Run, Conversation, User) rows with audit filters applied, scoped by role.

    Shared by /runs and /runs/stats so both read identical query-string
    filters: user_email (admin only), status, conversation_id, date_from/to.
    Non-admins are always restricted to their own runs.
    """
    q = (
        db.session.query(Run, Conversation, User)
        .join(Conversation, Run.conversation_id == Conversation.id)
        .join(User, Conversation.user_id == User.id)
    )
    if g.is_admin:
        # Admins see everyone by default and may narrow to one user's email.
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


# Histogram edges for the latency chart: [lo, hi) in milliseconds, hi=None = open-ended.
LATENCY_BUCKETS = [
    ("<2s", 0, 2000),
    ("2–5s", 2000, 5000),
    ("5–15s", 5000, 15000),
    ("15s+", 15000, None),
]


# --------------------------------------------------------------------------
# Audit endpoints
# --------------------------------------------------------------------------

@api_bp.get("/runs/stats")
@require_auth
def run_stats():
    """Aggregates for the Audit tab: status counts, success rate, token
    totals, tool-usage counts, runs-per-day series, latency histogram."""
    rows = _filtered_runs_query().all()
    # Squeeze each row down to the four fields the aggregations need.
    runs = [(run.id, run.status, run.created_at, run.total_latency_ms) for run, _, _ in rows]
    run_ids = [r[0] for r in runs]

    by_status = {}
    for _, status, _, _ in runs:
        by_status[status] = by_status.get(status, 0) + 1
    completed = by_status.get("completed", 0)
    # Success rate counts only terminal outcomes — runs still in flight or
    # awaiting confirmation would skew the denominator.
    terminal = completed + by_status.get("failed", 0) + by_status.get("stopped", 0)
    success_rate = (completed / terminal) if terminal else None

    # Step/token totals and tool usage come from SQL aggregates rather than
    # loading every RunStep row into Python.
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

    # Runs-per-day stacked series for the activity chart.
    per_day = {}
    for _, status, created_at, _ in runs:
        day = created_at.date().isoformat()
        counts = per_day.setdefault(
            day, {"completed": 0, "failed": 0, "stopped": 0, "running": 0}
        )
        if status in counts:
            counts[status] += 1
    runs_per_day = [
        {"date": day, **counts} for day, counts in sorted(per_day.items())
    ]

    # Latency histogram (runs without a recorded latency are excluded).
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


@api_bp.get("/runs")
@require_auth
def list_runs():
    """Paginated run table for the Audit tab (newest first)."""
    q = _filtered_runs_query()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)  # clamp 1..100
    total = q.count()
    rows = (
        q.order_by(Run.created_at.desc(), Run.id.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )
    # Fetch per-run step counts / token sums and the goal texts in two bulk
    # queries instead of one query per run (avoids the N+1 problem).
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
            "goal": (goals.get(run.user_message_id) or "")[:80],  # preview only
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
            # Only admins learn whose run each row is.
            item["user_email"] = user.email
        runs.append(item)
    return jsonify({"runs": runs, "total": total, "page": page, "per_page": per_page})


@api_bp.get("/runs/<int:run_id>")
@require_auth
def get_run(run_id):
    """One run with its complete trace (including full LLM prompts) — powers
    the step-by-step trace panel."""
    # Admins may open any run; everyone else only their own.
    run = db.session.get(Run, run_id) if g.is_admin else _owned_run(run_id)
    if run is None:
        return jsonify({"error": "run not found"}), 404
    body = {
        "id": run.id,
        "status": run.status,
        "model": run.model,
        "total_latency_ms": run.total_latency_ms,
        "created_at": run.created_at.isoformat(),
        "steps": _serialize_steps(run, include_messages=True),
    }
    # Surface a pending confirmation so the UI can render approve/reject buttons.
    pending = PendingAction.query.filter_by(run_id=run.id, status="pending").first()
    if pending is not None:
        body["pending_action"] = {
            "id": pending.id,
            "tool": pending.tool_name,
            "arguments": pending.arguments,
        }
    return jsonify(body)


@api_bp.post("/runs/<int:run_id>/stop")
@require_auth
def stop_run(run_id):
    """The Stop button. Sets run.status='stopped' in the DB; the agent loop
    (running inside a DIFFERENT request) polls that status between steps via
    db.session.refresh() and bails out when it sees it."""
    run = _owned_run(run_id) or db.session.get(Run, run_id)
    if not run:
        return jsonify({"error": "run not found"}), 404

    run.status = "stopped"

    # Log a step recording that the run was cancelled by user
    step_count = RunStep.query.filter_by(run_id=run.id).count() + 1
    stop_step = RunStep(
        run_id=run.id,
        seq=step_count,
        kind="system_event",
        result={"event": "user_cancelled", "message": "Execution aborted by user action."}
    )
    db.session.add(stop_step)
    db.session.commit()

    current_app.logger.info(f"Run #{run.id} explicitly marked as STOPPED.")
    return jsonify({"success": True, "status": "stopped", "run_id": run.id})


# --------------------------------------------------------------------------
# Ticket endpoints
# --------------------------------------------------------------------------

def seed_apexcare_tickets(user_id):
    """Insert the five fictional ApexCare demo tickets for a user.

    Called at registration (auth.register) and by /tickets/reset, so every
    account starts with realistic data the agent can triage.
    """
    sample_tickets = [
        {
            "ticket_number": "APX-1049",
            "requester_name": "Jane Doe",
            "requester_email": "jane.doe@apexcare.tech",
            "requester_department": "Commercial Operations",
            "title": "FSA Reimbursement & WEX Mobile Claim Submission",
            "description": "Hi HR team, I recently purchased new prescription eyewear. How do I submit my receipt for WEX Flexible Spending Account (FSA) reimbursement, and can I file the claim using the WEX mobile app?",
            "category": "HR & Benefits",
            "priority": "high",
            "channel": "Workday Portal",
            "status": "open",
            "sla_minutes_remaining": 105,
        },
        {
            "ticket_number": "APX-1048",
            "requester_name": "Marcus Vance",
            "requester_email": "marcus.vance@apexcare.tech",
            "requester_department": "Engineering",
            "title": "Qualifying Life Event (QLE) Dependent Enrollment Instructions",
            "description": "Hi HR team, we recently welcomed a new baby! How many days do I have to add my newborn as a dependent, and what are the step-by-step instructions to report a Qualifying Life Event in Employee Navigator?",
            "category": "Leaves & Disability",
            "priority": "medium",
            "channel": "Workday Portal",
            "status": "open",
            "sla_minutes_remaining": 180,
        },
        {
            "ticket_number": "APX-1047",
            "requester_name": "Sarah Connor",
            "requester_email": "sarah.connor@apexcare.tech",
            "requester_department": "People Operations",
            "title": "Guardian Dental & Vision Out-of-Network Coverage Inquiry",
            "description": "Can someone confirm our Guardian Dental & Vision policy group number (00539142 Class 0001), deductible limits, and how to submit an out-of-network dental claim for reimbursement?",
            "category": "HR & Benefits",
            "priority": "low",
            "channel": "Email",
            "status": "open",
            "sla_minutes_remaining": 240,
        },
        {
            "ticket_number": "APX-1046",
            "requester_name": "David Miller",
            "requester_email": "david.miller@apexcare.tech",
            "requester_department": "Finance",
            "title": "Replacement UnitedHealthcare Medical ID Card Request",
            "description": "Lost my plastic medical ID card while traveling. How can I print a temporary ID card right away on myuhc.com and order a physical replacement card?",
            "category": "HR & Benefits",
            "priority": "medium",
            "channel": "Workday Portal",
            "status": "open",
            "sla_minutes_remaining": 120,
        },
        {
            "ticket_number": "APX-1045",
            "requester_name": "Elena Rostova",
            "requester_email": "elena.rostova@apexcare.tech",
            "requester_department": "Product Design",
            "title": "Voluntary Short-Term Disability (STD) Coverage & Elimination Period",
            "description": "I have an upcoming medical procedure next month. What percentage of salary does Voluntary Short-Term Disability cover, what is the maximum weekly benefit, and what is the elimination period before benefits begin?",
            "category": "Leaves & Disability",
            "priority": "urgent",
            "channel": "Helpdesk",
            "status": "open",
            "sla_minutes_remaining": 30,
        },
    ]
    created = []
    for data in sample_tickets:
        t = Ticket(
            user_id=user_id,
            ticket_number=data["ticket_number"],
            requester_name=data["requester_name"],
            requester_email=data["requester_email"],
            requester_department=data["requester_department"],
            title=data["title"],
            description=data["description"],
            category=data["category"],
            priority=data["priority"],
            channel=data["channel"],
            status=data["status"],
            sla_minutes_remaining=data["sla_minutes_remaining"],
        )
        db.session.add(t)
        created.append(t)
    db.session.commit()
    return created


def _serialize_ticket(t):
    """Ticket row -> frontend dict. getattr(...) defaults guard against rows
    created before newer columns existed (SQLite dev DBs aren't migrated)."""
    # replies_json is a JSON-encoded list in a TEXT column; decode defensively.
    replies = []
    if getattr(t, "replies_json", None):
        try:
            replies = json.loads(t.replies_json)
        except Exception:
            replies = []

    return {
        "id": t.id,
        "ticket_number": getattr(t, "ticket_number", f"APX-{1000 + t.id}"),
        "requester_name": getattr(t, "requester_name", "Employee"),
        "requester_email": getattr(t, "requester_email", "employee@apexcare.tech"),
        "requester_department": getattr(t, "requester_department", "Commercial Operations"),
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "category": t.category,
        "channel": getattr(t, "channel", "Workday Portal"),
        "sla_minutes_remaining": getattr(t, "sla_minutes_remaining", 120),
        "draft_reply": getattr(t, "draft_reply", None),
        "draft_confidence": getattr(t, "draft_confidence", 95),
        "escalation_reason": getattr(t, "escalation_reason", None),
        "resolution_notes": getattr(t, "resolution_notes", None),
        "replies": replies,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


@api_bp.get("/tickets")
@require_auth
def get_tickets():
    """The user's tickets, optionally filtered by ?status= and ?category=."""
    status = request.args.get("status")
    category = request.args.get("category")
    q = Ticket.query.filter_by(user_id=g.user.id)
    if status:
        q = q.filter_by(status=status)
    if category and category != "All":  # "All" is the UI's no-filter sentinel
        q = q.filter_by(category=category)
    tickets = q.order_by(Ticket.created_at.desc()).all()
    return jsonify([_serialize_ticket(t) for t in tickets])


@api_bp.get("/tickets/<int:ticket_id>")
@require_auth
def get_ticket(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=g.user.id).first()
    if ticket is None:
        return jsonify({"error": "ticket not found"}), 404
    return jsonify(_serialize_ticket(ticket))


@api_bp.post("/tickets/reset")
@require_auth
def reset_tickets_endpoint():
    """Demo reset: wipe conversations/runs/messages/tickets, then reseed the
    sample tickets. Children are deleted before parents to satisfy the
    foreign-key constraints."""
    try:
        # 1. Direct bulk delete of child records (RunSteps & PendingActions) across ALL user runs
        user_conv_ids = [c.id for c in Conversation.query.filter_by(user_id=g.user.id).all()]
        user_run_ids = [r.id for r in Run.query.filter(Run.conversation_id.in_(user_conv_ids)).all()] if user_conv_ids else []

        # Delete all RunSteps and PendingActions unconditionally
        # (note: the `... | isnot None` filter matches every row, so this
        # clears ALL users' step/action data — acceptable for a demo reset).
        db.session.query(RunStep).filter(
            (RunStep.run_id.in_(user_run_ids)) | (RunStep.run_id.isnot(None))
        ).delete(synchronize_session=False)

        db.session.query(PendingAction).filter(
            (PendingAction.run_id.in_(user_run_ids)) | (PendingAction.run_id.isnot(None))
        ).delete(synchronize_session=False)

        # 2. Delete all Runs
        db.session.query(Run).delete(synchronize_session=False)

        # 3. Delete all Messages and Conversations
        db.session.query(Message).delete(synchronize_session=False)
        db.session.query(Conversation).delete(synchronize_session=False)

        # 4. Delete all Tickets for this user
        Ticket.query.filter_by(user_id=g.user.id).delete(synchronize_session=False)

        db.session.commit()

        # 5. Reseed fresh sample tickets
        tickets = seed_apexcare_tickets(g.user.id)
        return jsonify([_serialize_ticket(t) for t in tickets])

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Reseed failed: {e}")
        return jsonify({"error": "Failed to reset database", "details": str(e)}), 500


@api_bp.patch("/tickets/<int:ticket_id>")
@require_auth
def update_ticket_endpoint(ticket_id):
    """Partial update: only fields present in the JSON body are changed."""
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=g.user.id).first()
    if ticket is None:
        return jsonify({"error": "ticket not found"}), 404

    data = request.get_json(silent=True) or {}
    if "title" in data and data["title"].strip():
        ticket.title = data["title"].strip()
    if "description" in data and data["description"].strip():
        ticket.description = data["description"].strip()
    if "status" in data:
        ticket.status = data["status"]
    if "priority" in data:
        ticket.priority = data["priority"]
    if "category" in data:
        ticket.category = data["category"]
    if "draft_reply" in data:
        ticket.draft_reply = data["draft_reply"]
    if "escalation_reason" in data:
        ticket.escalation_reason = data["escalation_reason"]
    if "resolution_notes" in data:
        ticket.resolution_notes = data["resolution_notes"]
    if "new_reply" in data and data["new_reply"]:
        # "Send" flow: append the reply to the sent-replies list and clear the
        # draft slot (the draft has now become a real reply).
        existing = []
        if ticket.replies_json:
            try:
                existing = json.loads(ticket.replies_json)
            except Exception:
                existing = []
        existing.append(data["new_reply"])
        ticket.replies_json = json.dumps(existing)
        ticket.draft_reply = None

    db.session.commit()
    return jsonify(_serialize_ticket(ticket))


def _next_run_seq(run_id):
    """Same as agent._next_seq but keyed by id — next free step number."""
    count = db.session.query(func.count(RunStep.id)).filter_by(run_id=run_id).scalar()
    return count + 1


@api_bp.post("/tickets/<int:ticket_id>/triage")
@require_auth
def triage_ticket_endpoint(ticket_id):
    """Run the agent loop against one ticket — the main entry point into
    server/agent.py.

    Sequence:
      1. mark the ticket in_triage, create Conversation + Message + Run rows
      2. classify urgency with the LLM and write the priority onto the ticket
      3. build the triage goal prompt and hand it to run_agent()
      4. translate the outcome (stopped / failed / ok) into ticket state,
         including a safe fallback draft when the agent fails
    """
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=g.user.id).first()
    if ticket is None:
        return jsonify({"error": "ticket not found"}), 404

    # Layer-1 input sanitization: reject obvious injection probes in ticket text
    # before any LLM call or status mutation.
    blocked = reject_if_injection(
        ticket.title or "",
        ticket.description or "",
        source="triage",
    )
    if blocked is not None:
        return blocked

    ticket.status = "in_triage"
    db.session.commit()

    # Create a conversation and run for this triage execution
    conv = Conversation(user_id=g.user.id, title=f"Triage {ticket.ticket_number}: {ticket.title[:30]}")
    db.session.add(conv)
    db.session.commit()

    # Placeholder message — content rewritten after urgency classification
    # (the real prompt needs the classified priority, which we don't have yet,
    # but the Run row requires a user_message_id up front).
    msg = Message(conversation_id=conv.id, role="user", content=f"Triage ticket {ticket.ticket_number}")
    db.session.add(msg)
    db.session.commit()

    run = Run(conversation_id=conv.id, user_message_id=msg.id, status="running")
    db.session.add(run)
    db.session.commit()

    # Step 1: classify urgency / priority from ticket text (inbox-style priority logic).
    # Recorded through record_step so the classification shows up in the trace.
    urgency_messages = build_urgency_messages(ticket)
    classification = record_step(
        run.id,
        _next_run_seq(run.id),
        "llm_call",
        lambda: classify_priority(ticket),
        llm_messages=urgency_messages,
    )
    apply_priority(ticket, classification)

    # Build the actual triage goal (now including the fresh priority) and
    # overwrite the placeholder message so the trace shows the real prompt.
    user_prompt = TRIAGE_USER_PROMPT.format(
        ticket_number=ticket.ticket_number,
        requester_name=ticket.requester_name,
        requester_department=ticket.requester_department,
        requester_email=ticket.requester_email,
        category=ticket.category,
        priority=ticket.priority,
        channel=ticket.channel,
        title=ticket.title,
        description=ticket.description,
        ticket_id=ticket.id,
    )
    msg.content = user_prompt
    db.session.commit()

    # Step 2: the bounded agent loop does the real work.
    try:
        outcome = run_agent(run, user_prompt)
    except Exception:
        # Any unexpected crash inside the loop is treated like a failed run
        # and handled by the fallback below.
        outcome = {"status": "failed"}

    db.session.refresh(run)
    if run.status == "stopped" or outcome.get("status") == "stopped":
        # User cancelled: put the ticket back to open. 499 is the (nginx)
        # convention for "client closed request".
        ticket.status = "open"
        run.status = "stopped"
        db.session.commit()
        return jsonify({
            "ticket": _serialize_ticket(ticket),
            "run": {
                "run_id": run.id,
                "status": "stopped",
                "answer": "Triage was stopped by the user."
            },
            "conversation_id": conv.id
        }), 499

    if outcome.get("status") == "failed":
        # Graceful degradation: never leave the ticket with nothing. Store a
        # generic holding reply (confidence 0 so the UI flags it) and record
        # it in the trace like a normal create_draft call.
        current_app.logger.error(f"Agent triage failed for ticket {ticket.id}")

        draft_text = (
            f"Hello {ticket.requester_name.split()[0]},\n\n"
            f"Thank you for contacting ApexCare Support regarding '{ticket.title}'.\n\n"
            f"Our automated triage system is currently experiencing a delay, but your ticket has been securely logged. "
            f"An HR representative will review your request and assist you shortly."
        )

        record_step(
            run.id,
            _next_run_seq(run.id),
            "tool_call",
            lambda: create_draft(ticket.id, draft_text),
            tool_name="create_draft",
            arguments={"ticket_id": ticket.id, "reply_text": draft_text},
        )

        ticket.draft_reply = draft_text
        ticket.draft_confidence = 0  # signals "fallback, needs human eyes"
        ticket.status = "open"
        run.status = "failed"
        db.session.commit()

        outcome = {
            "run_id": run.id,
            "status": "failed",
            "answer": "Triage failed. Applied safe fallback draft.",
        }

    # Refresh ticket — the agent's tools may have changed it (draft, status).
    db.session.refresh(ticket)
    return jsonify({
        "ticket": _serialize_ticket(ticket),
        "run": outcome,
        "conversation_id": conv.id
    })


# --------------------------------------------------------------------------
# Knowledge-base listing
# --------------------------------------------------------------------------

@api_bp.get("/knowledge-base")
@require_auth
def get_knowledge_base_articles():
    """List the documents in knowledge_base/ for the KB tab.

    Reads the folder directly from disk (NOT from AnythingLLM) — this endpoint
    only powers the browsing UI; actual retrieval still goes through
    search_knowledge().
    """
    kb_dir = current_app.config.get("KNOWLEDGE_BASE_DIR") or os.path.join(current_app.root_path, "..", "knowledge_base")
    kb_dir = os.path.abspath(kb_dir)

    docs = []
    if os.path.exists(kb_dir):
        for fname in sorted(os.listdir(kb_dir)):
            # Skip dotfiles and the folder's own README.
            if fname.startswith(".") or fname.lower() == "readme.md":
                continue

            if fname.endswith((".pdf", ".md", ".txt")):
                fpath = os.path.join(kb_dir, fname)
                try:
                    size_bytes = os.path.getsize(fpath)
                    # "benefits_overview_2026.md" -> "Benefits Overview 2026"
                    base_name = os.path.splitext(fname)[0]
                    title = base_name.replace("_", " ").replace("-", " ").title()

                    ext = os.path.splitext(fname)[1].lower()
                    if ext in (".md", ".txt"):
                        # Text files get a real content preview (first 400 chars).
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            snippet = f.read(400).strip()
                        content = f"{snippet}..." if snippet else "Text document."
                    else:
                        # Binary (PDF): no preview, just a pointer to the agent.
                        content = f"Official policy document ({ext.upper()[1:]}). Please use the Pip Assistant to search this document's contents for specific details."

                    docs.append({
                        "filename": fname,
                        "title": title,
                        "size_bytes": size_bytes,
                        "content": content,
                        "category": "HR & Benefits"
                    })
                except Exception as e:
                    current_app.logger.warning(f"Failed to process KB file {fname}: {e}")

    return jsonify(docs)


# --------------------------------------------------------------------------
# Pip chat widget
# --------------------------------------------------------------------------

@api_bp.post("/chat")
@require_auth
def pip_chat():
    """The conversational chat widget.

    Unlike triage, this is NOT the agent loop — it's a fixed 3-step pipeline
    (the model here gets no tools):

      step 1 (seq 1, llm_call):   classify — does this need the knowledge base?
      step 2 (seq 2, tool_call):  search_knowledge, only if step 1 said YES
      step 3 (seq 3, llm_call):   compose the reply with ticket + KB context

    Steps are still logged as RunStep rows so chats appear in the Audit tab.
    A quirk of this fixed pipeline: the RunStep rows are written BEFORE each
    stage runs (with placeholder results like {"status": "searching"}) and
    updated afterwards, unlike the agent loop where record_step writes the
    finished step.
    """
    data = request.get_json(silent=True) or {}
    message_text = (data.get("message") or "").strip()
    if not message_text:
        return jsonify({"error": "message is required"}), 400

    # Layer-1 input sanitization: reject obvious injection probes before any LLM call.
    blocked = reject_if_injection(message_text, source="chat")
    if blocked is not None:
        return blocked

    # Step 0: Active Support Tickets Context & Name Lookup Engine.
    # Serialize ALL of the user's tickets into the system prompt so the model
    # can answer "what's Dave's ticket about?" without any tool call.
    active_tickets = Ticket.query.filter_by(user_id=g.user.id).order_by(Ticket.created_at.desc()).all()
    tickets_summary = []
    for t in active_tickets:
        replies = []
        if getattr(t, "replies_json", None):
            try:
                replies = json.loads(t.replies_json)
            except Exception:
                replies = []
        tickets_summary.append({
            "ticket_number": t.ticket_number,
            "id": t.id,
            "requester_name": t.requester_name,
            "requester_email": t.requester_email,
            "requester_department": t.requester_department,
            "title": t.title,
            "description": t.description,
            "category": t.category,
            "priority": t.priority,
            "status": t.status,
            "draft_reply": t.draft_reply,
            "escalation_reason": t.escalation_reason,
            "sent_replies_count": len(replies),
        })

    tickets_context = f"\n\nCURRENT_ACTIVE_TICKETS:\n{json.dumps(tickets_summary, indent=2)}"

    # All chat turns share one conversation per user (created on first chat).
    conv = Conversation.query.filter_by(user_id=g.user.id).first()
    if not conv:
        conv = Conversation(user_id=g.user.id, title="Pip Chat")
        db.session.add(conv)
        db.session.commit()

    msg = Message(conversation_id=conv.id, role="user", content=message_text)
    db.session.add(msg)
    db.session.commit()

    run = Run(
        conversation_id=conv.id,
        user_message_id=msg.id,
        status="running",
        model=current_app.config["AGENT_MODEL"],
    )
    db.session.add(run)
    db.session.commit()

    # Step 0.5: Classify query to see if it needs knowledge base search
    # (skips the slow RAG round-trip for greetings/small talk).
    step1 = RunStep(
        run_id=run.id,
        seq=1,
        kind="llm_call",
        result={"status": "classifying"}
    )
    db.session.add(step1)
    db.session.commit()

    needs_kb = True  # fail open: when unsure, search anyway
    try:
        classification_prompt = PIP_CLASSIFICATION_PROMPT.format(message_text=message_text)
        class_res = generate([{"role": "user", "content": classification_prompt}], tools=[])
        class_content = (class_res.get("content") or "").strip().upper()
        # Only skip the KB when the model UNambiguously said NO.
        if "NO" in class_content and "YES" not in class_content:
            needs_kb = False
        step1.result = {"status": "classified", "needs_kb": needs_kb}
        db.session.commit()
    except Exception as e:
        step1.result = {"error": str(e)}
        db.session.commit()

    # Step 1: Knowledge Search
    kb_context = ""
    no_policy_match = False
    if needs_kb:
        step2 = RunStep(
            run_id=run.id,
            seq=2,
            kind="tool_call",
            tool_name="search_knowledge",
            arguments={"query": message_text},
            result={"status": "searching"}
        )
        db.session.add(step2)
        db.session.commit()
        try:
            kb_result = search_knowledge(message_text)
            if kb_result and "error" not in str(kb_result):
                kb_context = f"\n\nAUDITED_POLICY_KNOWLEDGE_RESULT:\n{json.dumps(kb_result)}"
                # search_knowledge instructs AnythingLLM to emit this exact
                # sentinel when the documents don't cover the question.
                if "NO_POLICY_MATCH" in str(kb_result.get("answer", "")):
                    no_policy_match = True
            step2.result = kb_result
            db.session.commit()
        except Exception as e:
            step2.result = {"error": str(e)}
            db.session.commit()
    else:
        # If knowledge search was skipped because query is playful/off-topic, treat it as no policy match
        no_policy_match = True

    # Assemble the final prompt: persona (+ no-match addendum) + tickets + KB.
    system_prompt = PIP_SYSTEM_PROMPT
    if no_policy_match:
        system_prompt += PIP_SYSTEM_PROMPT_NO_POLICY_MATCH

    messages = [
        {"role": "system", "content": system_prompt + tickets_context + kb_context},
        {"role": "user", "content": message_text}
    ]

    # Cancellation checks (same two signals the agent loop uses) before the
    # expensive final generation...
    if is_client_disconnected():
        current_app.logger.info("Chat generation aborted: client disconnected.")
        run.status = "stopped"
        db.session.commit()
        return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

    db.session.refresh(run)
    if run.status == "stopped":
        current_app.logger.info("Chat generation aborted: run status set to stopped.")
        return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

    # Step 2 (seq 3): compose the actual reply.
    step3 = RunStep(
        run_id=run.id,
        seq=3,
        kind="llm_call",
        result={"status": "formulating"}
    )
    db.session.add(step3)
    db.session.commit()

    try:
        res = generate(messages, tools=[])

        # ...and re-check after generation, before committing/returning
        # (generation takes seconds; the user may have stopped meanwhile).
        if is_client_disconnected():
            current_app.logger.info("Chat generation aborted: client disconnected.")
            run.status = "stopped"
            db.session.commit()
            return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

        db.session.refresh(run)
        if run.status == "stopped":
            current_app.logger.info("Chat generation aborted: run status set to stopped.")
            return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

        content = res.get("content") or "I'm ready to assist you. Which ticket or policy question shall we tackle next?"

        step3.result = {"content": content}
        run.status = "completed"
        db.session.commit()

        return jsonify({"reply": content, "run_id": run.id})
    except Exception as e:
        # The generate() call itself failed. A stop/disconnect racing with the
        # failure still wins and reports "stopped" rather than an error.
        if is_client_disconnected():
            run.status = "stopped"
            db.session.commit()
            return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

        db.session.refresh(run)
        if run.status == "stopped":
            current_app.logger.info("Chat generation aborted: run status set to stopped.")
            return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

        # Log the exact failure for your own debugging and telemetry
        current_app.logger.error(f"Chat LLM generation failed: {str(e)}")

        step3.result = {"error": str(e)}
        run.status = "failed"
        db.session.commit()

        # Provide a graceful, honest failure message to the user
        reply_text = (
            "I'm sorry, but I am currently experiencing a connection issue and cannot process your request. "
            "Please try asking again in a few moments, or reach out to the HR Helpdesk directly if this is urgent."
        )

        # Return a 200 so the frontend chat UI doesn't crash, but displays the error text smoothly
        return jsonify({"reply": reply_text, "run_id": run.id})
