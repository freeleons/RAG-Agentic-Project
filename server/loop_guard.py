"""Loop fingerprinting: detect repeated identical tool calls in one agent run.
"""

import hashlib
import json


class LoopGuard:
    """Tracks tool-call fingerprints within a single agent loop.

    A fingerprint is a short hash of (tool_name + stable JSON args). If the same
    fingerprint appears `repeat_threshold` times, the loop should skip executing
    the tool and nudge the model to try a different approach instead.
    """

    def __init__(self, repeat_threshold: int = 3):
        self.history: list[str] = []
        self.threshold = repeat_threshold

    def fingerprint(self, tool_name: str, args: dict) -> str:
        """Build a stable short hash for tool_name + args.
        """
        payload = f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def check(self, tool_name: str, args: dict) -> bool:
        """Return True if this exact tool+args call has hit the repeat threshold.
        Records the fingerprint on every call. When True, the caller should NOT
        execute the tool again — inject an error observation and continue.
        """
        fp = self.fingerprint(tool_name, args)
        self.history.append(fp)
        return self.history.count(fp) >= self.threshold
