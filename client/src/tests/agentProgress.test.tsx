import { describe, expect, it } from "vitest";
import { deriveAgentProgress } from "../components/AgentProgress";
import { TraceStep } from "../types";

const llmToolCall = (seq: number, name: string, args: Record<string, unknown>): TraceStep => ({
  seq,
  kind: "llm_call",
  tool_name: null,
  arguments: null,
  result: { type: "tool_call", name, arguments: args, call_id: `c${seq}` },
  latency_ms: 40,
});

const toolResult = (seq: number, name: string, result: Record<string, unknown>): TraceStep => ({
  seq,
  kind: "tool_call",
  tool_name: name,
  arguments: { query: "fsa" },
  result,
  latency_ms: 320,
});

describe("deriveAgentProgress", () => {
  it("starts at the analyzing stage with no steps", () => {
    const progress = deriveAgentProgress([]);

    expect(progress.stage).toBe("ANALYZING");
    expect(progress.tools).toHaveLength(0);
    expect(progress.percent).toBe(25);
  });

  it("marks a tool as running once the model has picked it", () => {
    const progress = deriveAgentProgress([llmToolCall(1, "search_knowledge", { query: "fsa" })]);

    expect(progress.stage).toBe("TOOL_CALLING");
    expect(progress.tools).toEqual([
      expect.objectContaining({ tool: "search_knowledge", status: "running", latencyMs: null }),
    ]);
    expect(progress.label).toContain("Searching audited policy knowledge base");
  });

  it("closes the running tool out with latency when its result arrives", () => {
    const progress = deriveAgentProgress([
      llmToolCall(1, "search_knowledge", { query: "fsa" }),
      toolResult(2, "search_knowledge", { answer: "rollover is $640", sources: [] }),
    ]);

    expect(progress.tools).toHaveLength(1);
    expect(progress.tools[0]).toMatchObject({
      tool: "search_knowledge",
      status: "success",
      latencyMs: 320,
    });
  });

  it("flags a failed tool result as an error", () => {
    const progress = deriveAgentProgress([
      llmToolCall(1, "escalate", { ticket_id: "T-1" }),
      toolResult(2, "escalate", { error: "ticket not found" }),
    ]);

    expect(progress.tools[0]).toMatchObject({ tool: "escalate", status: "error" });
    expect(progress.tools[0].summary).toContain("ticket not found");
  });

  it("caps live progress below 100 and only completes on a finished run", () => {
    const steps = [
      llmToolCall(1, "search_knowledge", { query: "fsa" }),
      toolResult(2, "search_knowledge", { answer: "a" }),
      llmToolCall(3, "create_draft", { ticket_id: "T-1", reply_text: "hi" }),
      toolResult(4, "create_draft", { draft_id: 9 }),
    ];

    const live = deriveAgentProgress(steps);
    expect(live.percent).toBeLessThan(100);
    expect(live.percent).toBeLessThanOrEqual(85);

    const done = deriveAgentProgress(steps, "completed");
    expect(done.percent).toBe(100);
    expect(done.stage).toBe("COMPLETED");
  });
});
