import type { ConversationHistory, RunSummary, UiMessage } from "../types";

export function pairHistory(history: ConversationHistory): UiMessage[] {
  const runByUserMessage = new Map<number, RunSummary>(
    history.runs.map((r) => [r.user_message_id, r])
  );
  const out: UiMessage[] = [];
  let pendingRun: RunSummary | undefined;
  for (const m of history.messages) {
    if (m.role === "user") {
      pendingRun = runByUserMessage.get(m.id);
      out.push({ role: "user", content: m.content });
      if (pendingRun?.status === "needs_confirmation") {
        out.push({
          role: "assistant",
          content:
            "The agent wants to take an action — review it in the trace panel.",
          runId: pendingRun.id,
          awaitingConfirmation: true,
        });
        pendingRun = undefined;
      }
    } else {
      out.push({
        role: "assistant",
        content: m.content,
        runId: pendingRun?.id,
        stepCount: pendingRun?.step_count,
        totalLatencyMs: pendingRun?.total_latency_ms,
      });
      pendingRun = undefined;
    }

  }
  return out;
}
