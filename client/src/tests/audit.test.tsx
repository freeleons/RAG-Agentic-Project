import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import { jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

export const EMPTY_STATS = {
  total_runs: 0, by_status: {}, success_rate: null, avg_steps: null,
  avg_latency_ms: null, total_prompt_tokens: 0, total_completion_tokens: 0,
  tool_usage: {}, runs_per_day: [], latency_buckets: [],
};

export const STATS = {
  total_runs: 4,
  by_status: { completed: 2, failed: 1, declined: 1 },
  success_rate: 0.5,
  avg_steps: 2.0,
  avg_latency_ms: 6625,
  total_prompt_tokens: 600,
  total_completion_tokens: 60,
  tool_usage: { search_knowledge: 3, escalate: 1 },
  runs_per_day: [
    { date: "2026-08-01", completed: 2, failed: 0, declined: 0, needs_confirmation: 0 },
    { date: "2026-08-02", completed: 0, failed: 1, declined: 1, needs_confirmation: 0 },
  ],
  latency_buckets: [
    { label: "<2s", count: 1 }, { label: "2–5s", count: 1 },
    { label: "5–15s", count: 1 }, { label: "15s+", count: 1 },
  ],
};

export const RUNS_LIST = {
  runs: [
    {
      id: 17, status: "completed", goal: "Escalate ticket T-1",
      conversation_id: 1, conversation_title: "VPN ticket", model: "llama3.1:8b",
      step_count: 3, total_latency_ms: 5210, prompt_tokens: 1450,
      completion_tokens: 220, created_at: "2026-08-04T10:00:00",
    },
  ],
};

export function renderAudit(extraRoutes: Parameters<typeof stubFetch>[0] = {}) {
  localStorage.setItem("apexcare_token", "jwt-123");
  stubFetch({
    "GET /api/auth/me": () => jsonResponse({ id: 1, email: "me@test.com", full_name: "Alexandra Vance", department: "HR Operations", role_title: "Lead Support Specialist" }),
    "GET /api/tickets": () => jsonResponse([]),
    "GET /api/runs": () => jsonResponse(RUNS_LIST),
    "GET /api/runs/stats": () => jsonResponse(STATS),
    "GET /api/runs/17": () => jsonResponse({ run: RUNS_LIST.runs[0], steps: [] }),
    ...extraRoutes,
  });
  return render(<App />);
}

test("audit tab shows stat cards from the stats endpoint", async () => {
  renderAudit();
  await userEvent.click(await screen.findByRole("button", { name: /audit logs/i }));
  expect(await screen.findByText("50%")).toBeInTheDocument(); // success rate
  expect(screen.getByText("4")).toBeInTheDocument(); // total runs
  expect(screen.getByText("6625ms")).toBeInTheDocument(); // avg latency
});

test("workbench tab is unaffected and switching back works", async () => {
  renderAudit();
  await userEvent.click(await screen.findByRole("button", { name: /audit logs/i }));
  await screen.findByText("50%");
  await userEvent.click(screen.getByRole("button", { name: /^workbench$/i }));
  expect(
    (await screen.findAllByText(/Alexandra/i)).length
  ).toBeGreaterThan(0);
});

test("audit tab renders sections when there is data", async () => {
  renderAudit();
  await userEvent.click(await screen.findByRole("button", { name: /audit logs/i }));
  expect(await screen.findByText("Execution Latency Distribution")).toBeInTheDocument();
  expect(screen.getByText("Tool Execution Volume")).toBeInTheDocument();
});

test("audit tab shows empty state with no runs", async () => {
  renderAudit({
    "GET /api/runs": () => jsonResponse({ runs: [] }),
    "GET /api/runs/stats": () => jsonResponse(EMPTY_STATS),
  });
  await userEvent.click(await screen.findByRole("button", { name: /audit logs/i }));
  expect(await screen.findByText("Audit Log Runs (0)")).toBeInTheDocument();
});

test("runs table renders rows", async () => {
  renderAudit();
  await userEvent.click(await screen.findByRole("button", { name: /audit logs/i }));
  expect(await screen.findByText("Audit Log Runs (1)")).toBeInTheDocument();
  expect(screen.getByText(/Escalate ticket/i)).toBeInTheDocument();
});

test("trace breakdown shows a copyable trace_id from the flat run-detail response", async () => {
  // /api/runs/<id> actually returns a flat object (id, status, trace_id, steps,
  // ...) — no `run` wrapper. Unlike renderAudit()'s default mock (which mirrors
  // the component's buggy `.run?.field` reads), this one matches the real
  // backend shape so the trace_id row's `selectedRunDetails.trace_id` read is
  // exercised against actual production data.
  renderAudit({
    "GET /api/runs/17": () =>
      jsonResponse({
        id: 17,
        status: "completed",
        total_latency_ms: 5210,
        trace_id: "eaa5ded750e3b61bd1f3b1205469f768",
        steps: [],
      }),
  });
  await userEvent.click(await screen.findByRole("button", { name: /audit logs/i }));
  expect(await screen.findByText(/trace_id: eaa5ded750e3b61bd1f3b1205469f768/i)).toBeInTheDocument();
});
