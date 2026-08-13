from datetime import date
from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import func

from server.agent import resume_run, run_agent
from server.auth import require_auth
from server.llm import generate
from server.models import Conversation, Message, PendingAction, Run, RunStep, Ticket, User, db, utcnow


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


@api_bp.get("/conversations")
@require_auth
def list_conversations():
    q = request.args.get("q", "").strip()
    if q:
        query = (
            Conversation.query.outerjoin(Message, Conversation.id == Message.conversation_id)
            .filter(
                (Conversation.user_id == g.user.id)
                & (
                    (Conversation.title.ilike(f"%{q}%"))
                    | (Message.content.ilike(f"%{q}%"))
                )
            )
            .distinct()
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
        convs = query.all()
    else:
        convs = (
            Conversation.query.filter_by(user_id=g.user.id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .all()
        )
    return jsonify(
        [{"id": c.id, "title": c.title, "created_at": c.created_at.isoformat()} for c in convs]
    )



@api_bp.post("/conversations")
@require_auth
def create_conversation():
    data = request.get_json(silent=True) or {}
    conv = Conversation(user_id=g.user.id, title=data.get("title") or "New conversation")
    db.session.add(conv)
    db.session.commit()
    return jsonify({"id": conv.id, "title": conv.title}), 201


@api_bp.delete("/conversations/<int:conv_id>")
@require_auth
def delete_conversation(conv_id):
    conv = Conversation.query.filter_by(id=conv_id, user_id=g.user.id).first()
    if conv is None:
        return jsonify({"error": "conversation not found"}), 404

    runs = Run.query.filter_by(conversation_id=conv.id).all()
    for run in runs:
        PendingAction.query.filter_by(run_id=run.id).delete()
        RunStep.query.filter_by(run_id=run.id).delete()
        db.session.delete(run)

    Message.query.filter_by(conversation_id=conv.id).delete()
    db.session.delete(conv)
    db.session.commit()
    return jsonify({"success": True})


@api_bp.patch("/conversations/<int:conv_id>")
@require_auth
def update_conversation(conv_id):
    conv = Conversation.query.filter_by(id=conv_id, user_id=g.user.id).first()
    if conv is None:
        return jsonify({"error": "conversation not found"}), 404
    data = request.get_json(silent=True) or {}
    new_title = data.get("title", "").strip()
    if not new_title:
        return jsonify({"error": "title is required"}), 400
    conv.title = new_title
    db.session.commit()
    return jsonify({"id": conv.id, "title": conv.title})


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
                {
                    "id": r.id,
                    "user_message_id": r.user_message_id,
                    "status": r.status,
                    "step_count": len(r.steps),
                    "total_latency_ms": r.total_latency_ms,
                }
                for r in runs
            ],
        }
    )


@api_bp.post("/conversations/<int:conv_id>/messages")
@require_auth
def send_message(conv_id):
    conv = Conversation.query.filter_by(id=conv_id, user_id=g.user.id).first()
    if conv is None:
        return jsonify({"error": "conversation not found"}), 404
    conv.updated_at = utcnow()

    goal = ((request.get_json(silent=True) or {}).get("content") or "").strip()
    if not goal:
        return jsonify({"error": "content is required"}), 400

    if conv.title in ("New conversation", "", None):
        try:
            res = generate([
                {
                    "role": "system",
                    "content": "You are a title generator. Summarize the user's prompt into a concise 3 to 6 word title. Return ONLY the plain title text without quotes, markdown, or punctuation.",
                },
                {"role": "user", "content": goal},
            ])
            auto_title = (res.get("content") or "").strip().strip('"').strip("'")
            if auto_title:
                conv.title = auto_title[:60]
            else:
                conv.title = goal[:45].strip() + ("…" if len(goal) > 45 else "")
        except Exception:
            conv.title = goal[:45].strip() + ("…" if len(goal) > 45 else "")

    user_msg = Message(conversation_id=conv.id, role="user", content=goal)
    db.session.add(user_msg)
    db.session.flush()
    run = Run(
        conversation_id=conv.id,
        user_message_id=user_msg.id,
        model=current_app.config["AGENT_MODEL"],
    )
    db.session.add(run)
    db.session.commit()

    outcome = run_agent(run, goal)
    return jsonify({**outcome, "trace": _serialize_steps(run), "conversation_title": conv.title})


@api_bp.post("/runs/<int:run_id>/confirm")
@require_auth
def confirm_run(run_id):
    run = _owned_run(run_id)
    if run is None:
        return jsonify({"error": "run not found"}), 404
    data = request.get_json(silent=True) or {}
    if "approved" not in data:
        return jsonify({"error": "approved (true/false) is required"}), 400
    if not isinstance(data["approved"], bool):
        return jsonify({"error": "approved must be a boolean"}), 400
    if run.status != "needs_confirmation":
        return jsonify({"error": f"run is not awaiting confirmation (status: {run.status})"}), 409

    outcome = resume_run(run, data["approved"])
    return jsonify({**outcome, "trace": _serialize_steps(run)})


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


@api_bp.get("/tickets")
@require_auth
def get_tickets():
    status = request.args.get("status")
    priority = request.args.get("priority")
    category = request.args.get("category")
    q = request.args.get("q", "").strip()

    query = Ticket.query.filter_by(user_id=g.user.id)
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)
    if q:
        query = query.filter(
            (Ticket.title.ilike(f"%{q}%")) | (Ticket.description.ilike(f"%{q}%"))
        )

    tickets = query.order_by(Ticket.id.desc()).all()
    return jsonify(
        [
            {
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "category": t.category,
                "resolution_notes": t.resolution_notes,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tickets
        ]
    )


@api_bp.post("/tickets")
@require_auth
def create_ticket():
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    priority = data.get("priority") or "medium"
    category = data.get("category") or "General"

    if not title or not description:
        return jsonify({"error": "title and description are required"}), 400

    ticket = Ticket(
        user_id=g.user.id,
        title=title,
        description=description,
        priority=priority,
        category=category,
        status="open",
    )
    db.session.add(ticket)
    db.session.commit()
    return (
        jsonify(
            {
                "id": ticket.id,
                "title": ticket.title,
                "description": ticket.description,
                "status": ticket.status,
                "priority": ticket.priority,
                "category": ticket.category,
                "created_at": ticket.created_at.isoformat(),
            }
        ),
        201,
    )


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
    if "resolution_notes" in data and data["resolution_notes"].strip():
        ticket.resolution_notes = data["resolution_notes"].strip()

    db.session.commit()
    return jsonify(
        {
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status,
            "priority": ticket.priority,
            "category": ticket.category,
            "resolution_notes": ticket.resolution_notes,
            "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        }
    )


@api_bp.delete("/tickets/<int:ticket_id>")
@require_auth
def delete_ticket_endpoint(ticket_id):
    ticket = Ticket.query.filter_by(id=ticket_id, user_id=g.user.id).first()
    if ticket is None:
        return jsonify({"error": "ticket not found"}), 404

    db.session.delete(ticket)
    db.session.commit()
    return jsonify({"success": True})
