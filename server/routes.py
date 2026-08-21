"""All non-auth HTTP endpoints, mounted under /api (see app.py).

Roadmap of this file:

  Audit / observability UI
    GET  /runs/stats            aggregate stats + chart data for the Audit tab
    GET  /runs                  paginated run list (admins see all users)
    GET  /runs/<id>             one run with its full step trace
    POST /runs/<id>/stop        cancel a run mid-flight
    GET  /guardrail-events      paginated guardrail-rejection log (admins see all users)

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
import re
from datetime import date
from flask import Blueprint, current_app, g, jsonify, request, send_from_directory
from sqlalchemy import func

from server.agent import resume_run, run_agent
from server.auth import require_auth
from server.hitl import execute_tool_with_hitl
from server.llm import generate, llm_provider, stamp_run_llm_identity
from server.models import Conversation, GuardrailEvent, Message, PendingAction, Run, RunStep, Ticket, User, db, utcnow
from server.observability import record_step
from server.tools import openai_tool_defs, validate_arguments
from server.tools.search_knowledge import search_knowledge
from server.knowledge_sync import sync_one_resolved_ticket
from server.urgency import apply_priority, build_urgency_messages, classify_priority
from server.sanitization import reject_if_injection
from server.utils import clean_draft_text, content_hash, format_knowledge_answer, is_client_disconnected
from server.prompts import (
    TRIAGE_USER_PROMPT,
    PIP_CLASSIFICATION_PROMPT,
    PIP_GENERAL_SYSTEM_PROMPT,
    PIP_SEARCH_KNOWLEDGE_SYSTEM_PROMPT,
    PIP_DRAFT_SYSTEM_PROMPT,
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
            "error_type": s.error_type,
            "span_id": s.span_id,
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
        "provider": run.provider,
        "total_latency_ms": run.total_latency_ms,
        "trace_id": run.trace_id,
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
            "provider": run.provider,
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


@api_bp.get("/guardrail-events")
@require_auth
def list_guardrail_events():
    """Paginated guardrail-rejection log (newest first) — the read side of
    GuardrailEvent. Non-admins see only their own rejections; admins see
    everyone's, same role split as list_runs/_filtered_runs_query.
   
    """
    q = db.session.query(GuardrailEvent, User).join(User, GuardrailEvent.user_id == User.id)
    if not g.is_admin:
        q = q.filter(GuardrailEvent.user_id == g.user.id)
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)
    total = q.count()
    rows = (
        q.order_by(GuardrailEvent.created_at.desc(), GuardrailEvent.id.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )
    events = []
    for event, user in rows:
        item = {
            "id": event.id,
            "source": event.source,
            "filter": event.filter_name,
            "score": event.score,
            "action": event.action,
            "input_hash": event.input_hash,
            "created_at": event.created_at.isoformat(),
        }
        if g.is_admin:
            item["user_email"] = user.email
        events.append(item)
    return jsonify({"events": events, "total": total, "page": page, "per_page": per_page})


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
        "provider": run.provider,
        "total_latency_ms": run.total_latency_ms,
        "trace_id": run.trace_id,
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


@api_bp.post("/runs/<int:run_id>/confirm")
@require_auth
def confirm_run(run_id):
    """Resume the agent loop after approving/rejecting a consequential tool."""
    run = _owned_run(run_id)
    if run is None:
        return jsonify({"error": "run not found"}), 404
    if run.status != "needs_confirmation":
        return jsonify({"error": "run is not awaiting confirmation"}), 409

    data = request.get_json(silent=True) or {}
    if "approved" not in data:
        return jsonify({"error": "approved boolean is required"}), 400
    approved = bool(data["approved"])

    # Keep the pending action so reject can roll back related ticket state
    action = PendingAction.query.filter_by(run_id=run.id, status="pending").first()
    outcome = resume_run(run, approved)

    # Locate the target ticket from the action's arguments
    target_ticket = None
    if action is not None:
        raw_id = (action.arguments or {}).get("ticket_id")
        if raw_id is not None:
            clean_str = str(raw_id).replace("T-", "").replace("APX-", "").strip()
            target_ticket = Ticket.query.filter(
                (Ticket.id == clean_str) | (Ticket.ticket_number == str(raw_id)) | (Ticket.ticket_number == f"APX-{clean_str}"),
                Ticket.user_id == g.user.id,
            ).first()

    # On reject: if the ticket is still in_triage, reopen it so it is not stuck
    if not approved and target_ticket is not None and target_ticket.status == "in_triage":
        target_ticket.status = "open"
        db.session.commit()

    # Weave final drafted reply from the resumed run into the ticket's draft reply
    raw_ans = outcome.get("answer") or ""
    clean_draft = clean_draft_text(raw_ans)
    if target_ticket and clean_draft:
        target_ticket.draft_reply = clean_draft
        if target_ticket.status == "open":
            target_ticket.status = "draft_pending"
        db.session.commit()
        outcome["draft_reply"] = clean_draft
        outcome["ticket_id"] = target_ticket.id

    return jsonify(outcome)


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
            "title": "WEX Healthcare FSA Rollover Limit & Claim Submission",
            "description": "Hi HR team, I recently purchased new prescription eyewear. What is our Healthcare FSA rollover limit and annual contribution maximum, and how do I submit a claim or upload documentation using the WEX mobile app?",
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
            "title": "Work From Anywhere (WFA) Remote Work Policy & Home Office Stipend",
            "description": "Hi HR team, I am planning to work remotely from another state next month. How many calendar days per year does our Work From Anywhere (WFA) travel allowance cover, what are our required core collaboration hours, and what is the home office stipend for remote employees?",
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
            "title": "Replacement UnitedHealthcare Medical ID Card & Temporary Print",
            "description": "Hi HR, I lost my plastic medical ID card while traveling. How can I print a temporary medical ID card right away on myuhc.com and request a physical replacement card?",
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
            "description": "Hi HR team, I have an upcoming medical procedure next month. What percentage of salary does Voluntary Short-Term Disability cover, what is the maximum weekly benefit, and what is the elimination period before benefits begin?",
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

    # After resolve, auto-sync into the KB for later RAG retrieval
    if ticket.status == "resolved":
        sync_one_resolved_ticket(ticket)

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
    stamp_run_llm_identity(run)
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
        # generic holding reply (confidence 0 so the UI flags it).
        current_app.logger.error(f"Agent triage failed for ticket {ticket.id}")

        draft_text = (
            f"Hello {ticket.requester_name.split()[0]},\n\n"
            f"Thank you for contacting ApexCare Support regarding '{ticket.title}'.\n\n"
            f"Our automated triage system is currently experiencing a delay, but your ticket has been securely logged. "
            f"An HR representative will review your request and assist you shortly."
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

    if outcome.get("status") == "completed" and ticket.status != "escalated":
        raw_ans = outcome.get("answer") or ""
        cleaned_ans = clean_draft_text(raw_ans)
        if cleaned_ans:
            ticket.draft_reply = cleaned_ans
            if ticket.status == "open":
                ticket.status = "draft_pending"
            db.session.commit()
    elif (outcome.get("status") == "needs_confirmation" or ticket.status == "escalated") and not ticket.draft_reply:
        requester_first = (ticket.requester_name or "there").split()[0].strip()
        dept_str = ticket.requester_department or "HR Support"
        draft_text = (
            f"Hi {requester_first},\n\n"
            f"Thank you for contacting ApexCare Support regarding '{ticket.title}'. "
            f"I have escalated your request to our {dept_str} specialist team for review.\n\n"
            f"Our team will follow up directly with you shortly with next steps.\n\n"
            f"Best regards,\n"
            f"HR Support Team"
        )
        ticket.draft_reply = draft_text
        if ticket.status == "open":
            ticket.status = "draft_pending"
        db.session.commit()

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
                    if ext == ".pdf":
                        file_type = "pdf"
                        mime_type = "application/pdf"
                        content = "Official policy document (PDF). Full PDF preview and document search available."
                    elif ext == ".md":
                        file_type = "markdown"
                        mime_type = "text/markdown"
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                    else:
                        file_type = "text"
                        mime_type = "text/plain"
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                    docs.append({
                        "filename": fname,
                        "title": title,
                        "size_bytes": size_bytes,
                        "content": content,
                        "category": "HR & Benefits",
                        "file_type": file_type,
                        "mime_type": mime_type,
                    })
                except Exception as e:
                    current_app.logger.warning(f"Failed to process KB file {fname}: {e}")

    return jsonify(docs)


@api_bp.get("/knowledge-base/file/<path:filename>")
@require_auth
def get_knowledge_base_file(filename):
    """Serve raw knowledge base files (PDF, Markdown, plain text) with auth."""
    kb_dir = current_app.config.get("KNOWLEDGE_BASE_DIR") or os.path.join(current_app.root_path, "..", "knowledge_base")
    kb_dir = os.path.abspath(kb_dir)

    # Sanitize and ensure file is within kb_dir
    fpath = os.path.abspath(os.path.join(kb_dir, filename))
    if not fpath.startswith(kb_dir) or not os.path.isfile(fpath):
        return jsonify({"error": "Document not found"}), 404

    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".pdf", ".md", ".txt"):
        return jsonify({"error": "Unsupported file type"}), 400

    mimetypes = {
        ".pdf": "application/pdf",
        ".md": "text/markdown; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }
    return send_from_directory(kb_dir, filename, mimetype=mimetypes.get(ext, "application/octet-stream"))


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
        provider=llm_provider(),
    )
    db.session.add(run)
    db.session.commit()

    # Hardcoded check / explicit flag for DRAFT mode.
    # The ONLY time the draft route is triggered is explicitly when is_draft is True (e.g. "Draft with Pip" button clicked).
    is_explicit_draft = bool(data.get("is_draft") is True or data.get("mode") == "draft")

    if is_explicit_draft:
        route_flag = "DRAFT"
        step1 = RunStep(
            run_id=run.id,
            seq=1,
            kind="llm_call",
            result={"status": "explicit_draft_flag", "route": "DRAFT"}
        )
        db.session.add(step1)
        db.session.commit()
    else:
        # Step 0.5: Classify query strictly between CHITCHAT and SEARCH_KNOWLEDGE
        step1 = RunStep(
            run_id=run.id,
            seq=1,
            kind="llm_call",
            result={"status": "classifying"}
        )
        db.session.add(step1)
        db.session.commit()

        # Hardcoded guardrail: inquiries with explicit policy/work/benefit terms always search knowledge
        has_knowledge_intent = bool(re.search(
            r"\b(policy|policies|wfa|pto|fsa|hsa|benefit|benefits|rollover|limit|limits|coverage|deductible|navigator|qle|life event|std|ltd|insurance|401k|holiday|leave|medical|dental|vision|card|cards|replace|ticket|tickets|apx-|procedure|rules?|guidelines?|how (do|can|to|does)|what (is|are)|where (can|do|is)|tell me about)\b",
            message_text,
            re.IGNORECASE,
        ))

        route_flag = "SEARCH_KNOWLEDGE"
        if not has_knowledge_intent:
            try:
                classification_prompt = PIP_CLASSIFICATION_PROMPT.format(message_text=message_text)
                class_res = generate([{"role": "user", "content": classification_prompt}], tools=[])
                class_content = (class_res.get("content") or "").strip().upper()

                if "CHITCHAT" in class_content or "GENERAL" in class_content or ("NO" in class_content and "YES" not in class_content):
                    route_flag = "GENERAL"
                else:
                    route_flag = "SEARCH_KNOWLEDGE"
            except Exception as e:
                route_flag = "SEARCH_KNOWLEDGE"
        else:
            route_flag = "SEARCH_KNOWLEDGE"

        step1.result = {"status": "classified", "route": route_flag}
        db.session.commit()

    # Step 1: Knowledge Search (always executed for SEARCH_KNOWLEDGE and DRAFT)
    kb_context = ""
    kb_result = None
    no_policy_match = False
    if route_flag in ("SEARCH_KNOWLEDGE", "DRAFT"):
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
                if "NO_POLICY_MATCH" in str(kb_result.get("answer", "")):
                    no_policy_match = True
            step2.result = kb_result
            db.session.commit()
        except Exception as e:
            step2.result = {"error": str(e)}
            db.session.commit()

    # Step 2: Select the dedicated system prompt based on route_flag
    if route_flag == "GENERAL":
        system_prompt = PIP_GENERAL_SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text}
        ]
    elif route_flag == "DRAFT":
        system_prompt = PIP_DRAFT_SYSTEM_PROMPT
        messages = [
            {"role": "system", "content": system_prompt + tickets_context + kb_context},
            {"role": "user", "content": message_text}
        ]
    else:  # SEARCH_KNOWLEDGE
        system_prompt = PIP_SEARCH_KNOWLEDGE_SYSTEM_PROMPT
        if no_policy_match:
            system_prompt += PIP_SYSTEM_PROMPT_NO_POLICY_MATCH
        include_tickets = bool(re.search(r"\b(ticket|tickets|apx-|employee)\b", message_text, re.IGNORECASE))
        t_ctx = tickets_context if include_tickets else ""
        messages = [
            {"role": "system", "content": system_prompt + t_ctx + kb_context},
            {"role": "user", "content": message_text}
        ]

    # Fingerprint the static template (not the per-request tickets_context/
    # kb_context, which vary by design every call) so drift in the wording we
    # actually wrote is detectable independent of the dynamic content around it.
    # 中文：只对静态模板部分打指纹（不包括 tickets_context/kb_context——这两个
    # 本来每次请求就该不一样），这样我们自己写的措辞有没有被改动，能独立于
    # 周围动态内容被检测出来。
    run.system_prompt_hash = content_hash(system_prompt)
    db.session.commit()

    # Cancellation checks before final generation
    if is_client_disconnected():
        current_app.logger.info("Chat generation aborted: client disconnected.")
        run.status = "stopped"
        db.session.commit()
        return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

    db.session.refresh(run)
    if run.status == "stopped":
        current_app.logger.info("Chat generation aborted: run status set to stopped.")
        return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

    # Step 3: Compose the actual reply with explicitly guided output format
    step3 = RunStep(
        run_id=run.id,
        seq=3,
        kind="llm_call",
        llm_messages=messages,
        result={"status": "formulating"}
    )
    db.session.add(step3)
    db.session.commit()

    try:
        res = generate(messages, tools=[])

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

        # 1. Clean and pre-render knowledge search queries if the LLM outputted raw tool JSON
        is_fake_tool_call = (
            content.strip().startswith("{")
            and ("lookup_policy" in content or "search_knowledge" in content or "get_policy" in content)
        )
        sources_list = kb_result.get("sources") if (kb_result and isinstance(kb_result, dict)) else None
        if route_flag == "SEARCH_KNOWLEDGE":
            if is_fake_tool_call or (kb_result and kb_result.get("answer") and content.strip().startswith("{")):
                if kb_result and kb_result.get("answer"):
                    content = format_knowledge_answer(kb_result.get("answer"), sources_list)
            else:
                content = format_knowledge_answer(content, sources_list)

        # 2. Match target ticket & assign draft when in DRAFT route
        target_ticket = None
        extracted_draft = None

        if route_flag == "DRAFT":
            cleaned = clean_draft_text(content)
            extracted_draft = cleaned or content
            content = extracted_draft

            requested_ticket_id = data.get("ticket_id")
            if requested_ticket_id:
                clean_req = str(requested_ticket_id).replace("APX-", "").replace("T-", "").strip().upper()
                for t in active_tickets:
                    clean_num = str(t.ticket_number or "").replace("APX-", "").replace("T-", "").strip().upper()
                    if (
                        str(t.id) == str(requested_ticket_id)
                        or str(t.id) == clean_req
                        or str(t.ticket_number or "").upper() == str(requested_ticket_id).upper()
                        or (clean_num and clean_num == clean_req)
                    ):
                        target_ticket = t
                        break

            if not target_ticket:
                for t in active_tickets:
                    if t.ticket_number and t.ticket_number.lower() in message_text.lower():
                        target_ticket = t
                        break
                    if t.requester_name and t.requester_name.lower() in message_text.lower():
                        target_ticket = t
                        break
                    if t.requester_name:
                        first_name = t.requester_name.split()[0].lower()
                        if len(first_name) >= 3 and first_name in message_text.lower():
                            target_ticket = t
                            break

            if not target_ticket and len(active_tickets) == 1:
                target_ticket = active_tickets[0]

            if target_ticket and extracted_draft:
                target_ticket.draft_reply = extracted_draft
                if target_ticket.status == "open":
                    target_ticket.status = "draft_pending"
                db.session.commit()

        step3.result = {"content": content}
        run.status = "completed"
        # Audit fingerprint of what the user was actually shown.
        # 中文：用户实际看到内容的审计指纹。
        run.final_output_hash = content_hash(content)
        db.session.commit()

        resp_payload = {
            "reply": content,
            "status": "completed",
            "run_id": run.id,
            "route": route_flag,
        }
        if route_flag == "DRAFT" and target_ticket and extracted_draft:
            resp_payload["draft_reply"] = extracted_draft
            resp_payload["ticket_id"] = target_ticket.id
        return jsonify(resp_payload)
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
