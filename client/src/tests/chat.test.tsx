import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import { jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const TICKETS = [
  { id: 1, requester_name: "Dave", requester_email: "dave@test.com", title: "VPN ticket", description: "VPN issue", status: "open", priority: "medium", category: "IT Support", ticket_number: "T-101", sla_minutes_remaining: 30, created_at: "2026-08-03T00:00:00" }
];

function renderAuthed(extraRoutes: Parameters<typeof stubFetch>[0] = {}) {
  localStorage.setItem("apexcare_token", "jwt-123");
  stubFetch({
    "GET /api/auth/me": () => jsonResponse({ id: 1, email: "me@test.com", full_name: "Alexandra Vance", department: "HR Operations", role_title: "Lead Support Specialist" }),
    "GET /api/tickets": () => jsonResponse(TICKETS),
    ...extraRoutes,
  });
  return render(<App />);
}

test("sending a message to Pip renders the response in the copilot chat", async () => {
  renderAuthed({
    "POST /api/chat": () => jsonResponse({ reply: "I can help with that! Please look at the VPN policy.", run_id: 42 }),
    "GET /api/runs/42": () => jsonResponse({ run: { id: 42, status: "completed" }, steps: [] }),
    "GET /api/runs?page=1&per_page=1": () => jsonResponse({ runs: [] }),
  });
  
  expect(await screen.findByText(/I'm Pip, your ApexCare/i)).toBeInTheDocument();
  
  const textarea = screen.getByPlaceholderText(/Ask Pip any policy question/i);
  await userEvent.type(textarea, "How do I reset my VPN?");
  await userEvent.click(screen.getByRole("button", { name: /^send$/i }));
  
  expect(await screen.findByText("I can help with that! Please look at the VPN policy.")).toBeInTheDocument();
});

test("triage ticket flow", async () => {
  renderAuthed({
    "POST /api/tickets/1/triage": () => jsonResponse({ 
      ticket: { ...TICKETS[0], status: "draft_pending", draft_reply: "Proposed reply: reset your VPN." }, 
      run: { id: 101, run_id: 101, status: "completed" } 
    }),
    "GET /api/runs/101": () => jsonResponse({ run: { id: 101, run_id: 101, status: "completed" }, steps: [] }),
    "GET /api/runs?page=1&per_page=1": () => jsonResponse({ runs: [] }),
  });
  
  await userEvent.click((await screen.findAllByText("VPN ticket"))[0]);
  
  const triageBtn = await screen.findByRole("button", { name: /draft with pip/i });
  await userEvent.click(triageBtn);
  
  await waitFor(() => {
    const textarea = screen.getByPlaceholderText(/Write a reply/i) as HTMLTextAreaElement;
    expect(textarea.value).toBe("Proposed reply: reset your VPN.");
  });
});
