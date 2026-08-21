import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import TracePanel from "../trace/TracePanel";
import type { PanelState } from "../types";

const STEPS: PanelState["steps"] = [
  {
    seq: 1,
    kind: "llm_call",
    tool_name: null,
    arguments: null,
    result: { type: "tool_call", name: "search_knowledge" },
    latency_ms: 900,
  },
  {
    seq: 2,
    kind: "tool_call",
    tool_name: "search_knowledge",
    arguments: { query: "SLA policy" },
    result: { answer: "24h response", sources: ["policy.md"] },
    latency_ms: 230,
  },
];

test("renders empty state without a panel", () => {
  render(<TracePanel panel={null} busy={false} onConfirm={() => {}} />);
  expect(screen.getByText(/send a goal or click a trace chip/i)).toBeInTheDocument();
});

test("renders steps with tool names and latencies", () => {
  const panel: PanelState = { runId: 17, status: "completed", steps: STEPS };
  render(<TracePanel panel={panel} busy={false} onConfirm={() => {}} />);
  expect(screen.getByText(/run #17/i)).toBeInTheDocument();
  expect(screen.getByText(/#1 · model call/i)).toBeInTheDocument();
  expect(screen.getByText(/#2 · search_knowledge/i)).toBeInTheDocument();
  expect(screen.getByText("230 ms")).toBeInTheDocument();
});

test("needs_confirmation shows the pending action and fires onConfirm", async () => {
  const onConfirm = vi.fn();
  const panel: PanelState = {
    runId: 18,
    status: "needs_confirmation",
    steps: STEPS,
    pendingAction: {
      id: 3,
      tool: "escalate",
      arguments: { ticket_id: "T-1", priority: "high", reason: "outage" },
    },
  };
  render(<TracePanel panel={panel} busy={false} onConfirm={onConfirm} />);
  expect(screen.getByText(/the agent wants to run/i)).toBeInTheDocument();
  expect(screen.getByText("escalate")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: /approve/i }));
  expect(onConfirm).toHaveBeenCalledWith(true);
  await userEvent.click(screen.getByRole("button", { name: /reject/i }));
  expect(onConfirm).toHaveBeenCalledWith(false);
});

test("renders a copyable trace_id when present", () => {
  const panel: PanelState = {
    runId: 19,
    status: "completed",
    steps: STEPS,
    traceId: "eaa5ded750e3b61bd1f3b1205469f768",
  };
  render(<TracePanel panel={panel} busy={false} onConfirm={() => {}} />);
  expect(screen.getByText(/trace_id: eaa5ded750e3b61bd1f3b1205469f768/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /copy trace id/i })).toBeInTheDocument();
});

test("omits the trace_id row when absent", () => {
  const panel: PanelState = { runId: 20, status: "completed", steps: STEPS };
  render(<TracePanel panel={panel} busy={false} onConfirm={() => {}} />);
  expect(screen.queryByText(/trace_id:/i)).not.toBeInTheDocument();
});

test("buttons are disabled while busy", () => {
  const panel: PanelState = {
    runId: 18,
    status: "needs_confirmation",
    steps: [],
    pendingAction: { id: 3, tool: "escalate", arguments: {} },
  };
  render(<TracePanel panel={panel} busy={true} onConfirm={() => {}} />);
  expect(screen.getByRole("button", { name: /approve/i })).toBeDisabled();
});
