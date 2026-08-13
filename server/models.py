from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), default="Support Specialist")
    department = db.Column(db.String(100), default="HR Operations")
    role_title = db.Column(db.String(100), default="Lead Support Specialist")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class Conversation(db.Model):
    __tablename__ = "conversations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(255), default="New conversation")
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    messages = db.relationship("Message", backref="conversation", order_by="Message.id")


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    role = db.Column(db.String(16), nullable=False)  # user | assistant
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class Run(db.Model):
    __tablename__ = "runs"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False)
    user_message_id = db.Column(db.Integer, db.ForeignKey("messages.id"), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="running")
    model = db.Column(db.String(128))
    total_latency_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    steps = db.relationship("RunStep", backref="run", order_by="RunStep.seq")


class RunStep(db.Model):
    __tablename__ = "run_steps"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("runs.id"), nullable=False)
    seq = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(16), nullable=False)  # llm_call | tool_call
    tool_name = db.Column(db.String(64))
    arguments = db.Column(db.JSON)
    result = db.Column(db.JSON)
    llm_messages = db.Column(db.JSON)
    latency_ms = db.Column(db.Integer)
    prompt_tokens = db.Column(db.Integer)
    completion_tokens = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)


class PendingAction(db.Model):
    __tablename__ = "pending_actions"
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("runs.id"), nullable=False)
    tool_name = db.Column(db.String(64), nullable=False)
    arguments = db.Column(db.JSON)
    status = db.Column(db.String(16), nullable=False, default="pending")
    resolved_at = db.Column(db.DateTime(timezone=True))


class Ticket(db.Model):
    __tablename__ = "tickets"
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), default="APX-1001")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
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
    draft_reply = db.Column(db.Text, nullable=True)
    draft_confidence = db.Column(db.Integer, default=95)
    escalation_reason = db.Column(db.Text, nullable=True)
    replies_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user = db.relationship("User", backref="tickets")


