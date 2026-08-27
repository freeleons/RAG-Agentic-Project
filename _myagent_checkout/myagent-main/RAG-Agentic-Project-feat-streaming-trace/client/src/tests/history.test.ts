import { expect, test } from "vitest";
import { pairHistory } from "../chat/history";
import type { ConversationHistory } from "../types";

const HISTORY: ConversationHistory = {
  messages: [
    { id: 1, role: "user", content: "reset vpn?", created_at: "t1" },
    { id: 2, role: "assistant", content: "In Settings.", created_at: "t2" },
    { id: 3, role: "user", content: "escalate T-1", created_at: "t3" },
    { id: 4, role: "assistant", content: "Escalated.", created_at: "t4" },
  ],
  runs: [
    { id: 10, user_message_id: 1, status: "completed" },
    { id: 11, user_message_id: 3, status: "completed" },
  ],
};

test("pairs each assistant message with the run of the preceding user message", () => {
  const ui = pairHistory(HISTORY);
  expect(ui).toHaveLength(4);
  expect(ui[0]).toMatchObject({ role: "user", content: "reset vpn?" });
  expect(ui[1]).toMatchObject({ role: "assistant", content: "In Settings.", runId: 10 });
  expect(ui[3]).toMatchObject({ role: "assistant", content: "Escalated.", runId: 11 });
});

test("assistant message without a matching run gets no runId", () => {
  const ui = pairHistory({
    messages: [{ id: 2, role: "assistant", content: "orphan", created_at: "t" }],
    runs: [],
  });
  expect(ui[0].runId).toBeUndefined();
});

test("synthesizes an awaiting-confirmation placeholder for a paused run", () => {
  const ui = pairHistory({
    messages: [
      { id: 1, role: "user", content: "reset vpn?", created_at: "t1" },
      { id: 2, role: "assistant", content: "In Settings.", created_at: "t2" },
      { id: 3, role: "user", content: "escalate T-1", created_at: "t3" },
    ],
    runs: [
      { id: 10, user_message_id: 1, status: "completed" },
      { id: 11, user_message_id: 3, status: "needs_confirmation" },
    ],
  });
  expect(ui).toHaveLength(4);
  expect(ui[2]).toMatchObject({ role: "user", content: "escalate T-1" });
  expect(ui[3]).toMatchObject({
    role: "assistant",
    content: "The agent wants to take an action — review it in the trace panel.",
    runId: 11,
    awaitingConfirmation: true,
  });
});
