import json

from flask import current_app
from sqlalchemy import func

from server.llm import generate
from server.models import Message, PendingAction, RunStep, db, utcnow
from server.observability import record_step
from server.tools import TOOLS, openai_tool_defs, validate_arguments
from server.utils import is_client_disconnected

SYSTEM_PROMPT = (
    "You are Pip, an AI Support Specialist assistant for ApexCare Technologies.\n\n"
    "CRITICAL PERSONA & VOICE RULES:\n"
    "1. DRAFT ON BEHALF OF HR: Always draft email responses from the perspective of HR / Support staff. "
    "NEVER sign emails as 'Pip' or 'AI Support Assistant'.\n"
    "2. NO META-COMMENTARY OR POST-MORTEMS: NEVER include system notes, developer logs, code explanations, "
    "or references to tool errors (e.g., 'Note: The original error was resolved...'). Output ONLY the professional response.\n\n"
    "WORKFLOW & INTENT EVALUATION:\n"
    "- INFORMATIONAL QUERIES: You MUST call `search_knowledge` before drafting a reply.\n"
    "- ACTION / TICKET RESPONSES: Always use `create_draft` to insert ticket replies.\n"
    "- ESCALATIONS: Use `escalate` ONLY for system outages or explicit policy gaps.\n"
    "- GENERAL CHITCHAT: Respond briefly and gently redirect the user to HR ticket support.\n\n"
    "GROUNDING & FALLBACKS:\n"
    "1. Base policy details strictly on `<tool_result>` data.\n"
    "2. IF `search_knowledge` returns 'no relevant information' or empty sources, DO NOT retry searching.\n"
    "   Immediately call `create_draft` with a polite response acknowledging the request and stating that an "
    "HR Specialist will follow up shortly with specific guidance.\n\n"
    "TOOL CALL RULES:\n"
    "1. ONE AT A TIME: Execute exactly one tool call per turn.\n"
    "2. ZERO PREAMBLE: Output ZERO conversational filler (e.g., 'Since we have a draft...', 'Here is the tool call:'). "
    "Output ONLY the tool invocation.\n"
    "3. FALLBACK FORMAT: If native tool calling fails, output pure JSON ONLY (no markdown, no backticks ```, and NO Python code string like `create_draft(...)`):\n"
    '   {"name": "create_draft", "arguments": {"ticket_id": 4, "reply_text": "Dear Employee..."}}\n'
)





def _assistant_tool_call_message(call_id, name, arguments):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def _tool_result_message(call_id, tool_name, result):
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": f"<tool_result>\n{json.dumps(result)}\n</tool_result>",
    }


def _next_seq(run):
    count = db.session.query(func.count(RunStep.id)).filter_by(run_id=run.id).scalar()
    return count + 1


def _finish(run, status, answer):
    db.session.refresh(run)
    if run.status == "stopped":
        current_app.logger.info(f"Run #{run.id} was cancelled mid-flight. Preserving 'stopped' status.")
        return {"run_id": run.id, "status": "stopped", "answer": "Response stopped by user."}

    db.session.add(Message(conversation_id=run.conversation_id, role="assistant", content=answer))
    run.status = status
    run.total_latency_ms = (
        db.session.query(func.coalesce(func.sum(RunStep.latency_ms), 0))
        .filter_by(run_id=run.id)
        .scalar()
    )
    db.session.commit()
    return {"run_id": run.id, "status": status, "answer": answer}


def run_agent(run, goal):
    """Run the bounded agent loop for a fresh user goal."""
    history = (
        Message.query.filter(
            Message.conversation_id == run.conversation_id,
            Message.id < run.user_message_id,
        )
        .order_by(Message.id)
        .all()
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": goal})
    return _loop(run, messages, retried=False)


def _loop(run, messages, retried):
    max_steps = current_app.config["MAX_AGENT_STEPS"]
    while True:
        if is_client_disconnected():
            current_app.logger.info(f"Run #{run.id} execution aborted by client disconnect.")
            run.status = "stopped"
            db.session.commit()
            return {
                "run_id": run.id,
                "status": "stopped",
                "answer": "Execution was stopped by the user."
            }

        db.session.refresh(run)
        if run.status == "stopped":
            current_app.logger.info(f"Run #{run.id} execution aborted by stopped status in DB.")
            return {
                "run_id": run.id,
                "status": "stopped",
                "answer": "Execution was stopped by the user."
            }

        if _next_seq(run) > max_steps:
            return _finish(run, "failed", "I ran out of steps before finishing this task.")

        decision = record_step(
            run.id,
            _next_seq(run),
            "llm_call",
            lambda m=messages: generate(m, openai_tool_defs()),
            llm_messages=messages,
        )
        if "error" in decision:
            return _finish(
                run, "failed", "The reasoning model is unavailable right now; please try again."
            )
        if decision["type"] == "final":
            return _finish(run, "completed", decision["content"])

        name = decision["name"]
        arguments = decision["arguments"]
        call_id = decision["call_id"]

        problem = validate_arguments(name, arguments)
        if problem is not None:
            if retried:
                return _finish(
                    run, "failed", "I couldn't complete that: the tool call was malformed twice."
                )
            retried = True
            messages = messages + [
                _assistant_tool_call_message(call_id, name, arguments),
                _tool_result_message(
                    call_id,
                    name,
                    {"error": f"invalid tool call: {problem}. Fix the arguments and try again."},
                ),
            ]
            continue
        retried = False

        tool = TOOLS[name]
        if tool["requires_confirmation"]:
            action = PendingAction(run_id=run.id, tool_name=name, arguments=arguments)
            run.status = "needs_confirmation"
            db.session.add(action)
            db.session.commit()
            return {
                "run_id": run.id,
                "status": "needs_confirmation",
                "pending_action": {"id": action.id, "tool": name, "arguments": arguments},
            }

        # Cap check before tool_call to prevent exceeding MAX_AGENT_STEPS
        if _next_seq(run) > max_steps:
            return _finish(run, "failed", "I ran out of steps before finishing this task.")

        result = record_step(
            run.id,
            _next_seq(run),
            "tool_call",
            lambda t=tool, a=arguments: t["handler"](**a),
            tool_name=name,
            arguments=arguments,
        )
        messages = messages + [
            _assistant_tool_call_message(call_id, name, arguments),
            _tool_result_message(call_id, name, result),
        ]


def resume_run(run, approved):
    """Resume a run paused in needs_confirmation. Caller guarantees that state."""
    action = PendingAction.query.filter_by(run_id=run.id, status="pending").first()
    action.status = "approved" if approved else "rejected"
    action.resolved_at = utcnow()

    llm_steps = [s for s in run.steps if s.kind == "llm_call"]
    last_llm = llm_steps[-1]
    call_id = f"resume_{action.id}"
    messages = list(last_llm.llm_messages) + [
        _assistant_tool_call_message(call_id, action.tool_name, action.arguments)
    ]

    run.status = "running"
    db.session.commit()

    if approved:
        tool = TOOLS[action.tool_name]
        result = record_step(
            run.id,
            _next_seq(run),
            "tool_call",
            lambda t=tool, a=action.arguments: t["handler"](**a),
            tool_name=action.tool_name,
            arguments=action.arguments,
        )
        messages.append(_tool_result_message(call_id, action.tool_name, result))
    else:
        messages.append(
            _tool_result_message(
                call_id,
                action.tool_name,
                {"error": "The user declined this action. Do not retry it; wrap up politely."},
            )
        )

    outcome = _loop(run, messages, retried=False)
    if not approved and outcome["status"] == "completed":
        run.status = "declined"
        db.session.commit()
        outcome["status"] = "declined"
    return outcome
