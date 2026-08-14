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
from server.utils import is_client_disconnected
from server.prompts import (
    TRIAGE_USER_PROMPT,
    PIP_CLASSIFICATION_PROMPT,
    PIP_SYSTEM_PROMPT,
    PIP_SYSTEM_PROMPT_NO_POLICY_MATCH,
)


api_bp = Blueprint("api", __name__, url_prefix="/api")


def _serialize_steps(run, include_messages=False):
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
    return (
        Run.query.join(Conversation, Run.conversation_id == Conversation.id)
        .filter(Run.id == run_id, Conversation.user_id == g.user.id)
        .first()
    )


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
    terminal = completed + by_status.get("failed", 0) + by_status.get("stopped", 0)
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
            day, {"completed": 0, "failed": 0, "stopped": 0, "running": 0}
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

@api_bp.get("/runs/<int:run_id>")
@require_auth
def get_run(run_id):
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


def seed_apexcare_tickets(user_id):
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
    status = request.args.get("status")
    category = request.args.get("category")
    q = Ticket.query.filter_by(user_id=g.user.id)
    if status:
        q = q.filter_by(status=status)
    if category and category != "All":
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
    try:
        # 1. Direct bulk delete of child records (RunSteps & PendingActions) across ALL user runs
        user_conv_ids = [c.id for c in Conversation.query.filter_by(user_id=g.user.id).all()]
        user_run_ids = [r.id for r in Run.query.filter(Run.conversation_id.in_(user_conv_ids)).all()] if user_conv_ids else []

        # Delete all RunSteps and PendingActions unconditionally
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
    count = db.session.query(func.count(RunStep.id)).filter_by(run_id=run_id).scalar()
    return count + 1


@api_bp.post("/tickets/<int:ticket_id>/triage")
@require_auth
def triage_ticket_endpoint(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=g.user.id).first()
    if ticket is None:
        return jsonify({"error": "ticket not found"}), 404

    ticket.status = "in_triage"
    db.session.commit()

    # Create a conversation and run for this triage execution
    conv = Conversation(user_id=g.user.id, title=f"Triage {ticket.ticket_number}: {ticket.title[:30]}")
    db.session.add(conv)
    db.session.commit()

    # Placeholder message — content rewritten after urgency classification
    msg = Message(conversation_id=conv.id, role="user", content=f"Triage ticket {ticket.ticket_number}")
    db.session.add(msg)
    db.session.commit()

    run = Run(conversation_id=conv.id, user_message_id=msg.id, status="running")
    db.session.add(run)
    db.session.commit()

    # Step 1: classify urgency / priority from ticket text (inbox-style priority logic)
    urgency_messages = build_urgency_messages(ticket)
    classification = record_step(
        run.id,
        _next_run_seq(run.id),
        "llm_call",
        lambda: classify_priority(ticket),
        llm_messages=urgency_messages,
    )
    apply_priority(ticket, classification)

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

    try:
        outcome = run_agent(run, user_prompt)
    except Exception:
        outcome = {"status": "failed"}

    db.session.refresh(run)
    if run.status == "stopped" or outcome.get("status") == "stopped":
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
        ticket.draft_confidence = 0
        ticket.status = "open"
        run.status = "failed"
        db.session.commit()

        outcome = {
            "run_id": run.id,
            "status": "failed",
            "answer": "Triage failed. Applied safe fallback draft.",
        }

    # Refresh ticket
    db.session.refresh(ticket)
    return jsonify({
        "ticket": _serialize_ticket(ticket),
        "run": outcome,
        "conversation_id": conv.id
    })



@api_bp.get("/knowledge-base")
@require_auth
def get_knowledge_base_articles():
    kb_dir = current_app.config.get("KNOWLEDGE_BASE_DIR") or os.path.join(current_app.root_path, "..", "knowledge_base")
    kb_dir = os.path.abspath(kb_dir)

    docs = []
    if os.path.exists(kb_dir):
        for fname in sorted(os.listdir(kb_dir)):
            if fname.startswith(".") or fname.lower() == "readme.md":
                continue
                
            if fname.endswith((".pdf", ".md", ".txt")):
                fpath = os.path.join(kb_dir, fname)
                try:
                    size_bytes = os.path.getsize(fpath)
                    base_name = os.path.splitext(fname)[0]
                    title = base_name.replace("_", " ").replace("-", " ").title()

                    ext = os.path.splitext(fname)[1].lower()
                    if ext in (".md", ".txt"):
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            snippet = f.read(400).strip()
                        content = f"{snippet}..." if snippet else "Text document."
                    else:
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


@api_bp.post("/chat")
@require_auth
def pip_chat():
    data = request.get_json(silent=True) or {}
    message_text = (data.get("message") or "").strip()
    if not message_text:
        return jsonify({"error": "message is required"}), 400

    # Step 0: Active Support Tickets Context & Name Lookup Engine
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
    step1 = RunStep(
        run_id=run.id,
        seq=1,
        kind="llm_call",
        result={"status": "classifying"}
    )
    db.session.add(step1)
    db.session.commit()

    needs_kb = True
    try:
        classification_prompt = PIP_CLASSIFICATION_PROMPT.format(message_text=message_text)
        class_res = generate([{"role": "user", "content": classification_prompt}], tools=[])
        class_content = (class_res.get("content") or "").strip().upper()
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

    system_prompt = PIP_SYSTEM_PROMPT
    if no_policy_match:
        system_prompt += PIP_SYSTEM_PROMPT_NO_POLICY_MATCH

    messages = [
        {"role": "system", "content": system_prompt + tickets_context + kb_context},
        {"role": "user", "content": message_text}
    ]

    if is_client_disconnected():
        current_app.logger.info("Chat generation aborted: client disconnected.")
        run.status = "stopped"
        db.session.commit()
        return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

    db.session.refresh(run)
    if run.status == "stopped":
        current_app.logger.info("Chat generation aborted: run status set to stopped.")
        return jsonify({"reply": "Response stopped by user.", "status": "stopped", "run_id": run.id}), 499

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
        
        # Verify client is still connected before committing or returning
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

