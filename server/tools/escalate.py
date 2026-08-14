"""Tool: escalate — hand a ticket off to a human support queue.

This one is a pure mock: there is no real queue behind it, so it just returns
an acknowledgment payload. The RunStep row written by record_step() (with the
arguments and this result) is the durable record that an escalation happened.
"""

import itertools

# Mints esc-1, esc-2, ... per server process; resets on restart.
_counter = itertools.count(1)


def escalate(ticket_id, priority, reason):
    """Mock: escalate a ticket to a human queue. The trace row is the durable record."""
    return {
        "escalation_id": f"esc-{next(_counter)}",
        "ticket_id": ticket_id,
        "priority": priority,
        "status": "escalated",
    }
