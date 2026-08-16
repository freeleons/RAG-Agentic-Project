import { render, screen } from "@testing-library/react";
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

test("draft with pip inputs message into pip chat and renders response with copy button", async () => {
  renderAuthed({
    "POST /api/chat": () => jsonResponse({ reply: "Here is a drafted response for Dave: Please reset your VPN token at vpn.apexcare.tech.", run_id: 101 }),
    "GET /api/runs/101": () => jsonResponse({ run: { id: 101, status: "completed" }, steps: [] }),
    "GET /api/runs?page=1&per_page=1": () => jsonResponse({ runs: [] }),
  });
  
  await userEvent.click((await screen.findAllByText("VPN ticket"))[0]);
  
  const draftBtn = await screen.findByRole("button", { name: /draft with pip/i });
  await userEvent.click(draftBtn);
  
  // Pip chat should display the response
  expect(await screen.findByText(/Here is a drafted response for Dave/i)).toBeInTheDocument();
  // Copy buttons should be present on Pip's replies
  const copyButtons = screen.getAllByRole("button", { name: /copy reply/i });
  expect(copyButtons.length).toBeGreaterThanOrEqual(2);
});

test("pip chat renders HITL escalation alert with no draft text and handles approval", async () => {
  let confirmCalledWith: any = null;
  renderAuthed({
    "POST /api/chat": () =>
      jsonResponse({
        reply: "I recommend escalating Ticket APX-101 with URGENT priority.",
        status: "needs_confirmation",
        run_id: 88,
        pending_action: {
          id: 5,
          tool: "escalate",
          arguments: {
            ticket_id: "APX-101",
            priority: "urgent",
            reason: "Critical database connection failure affecting company operations.",
          },
        },
      }),
    "GET /api/runs/88": () => jsonResponse({ run: { id: 88, status: "needs_confirmation" }, steps: [] }),
    "GET /api/runs?page=1&per_page=1": () => jsonResponse({ runs: [] }),
    "POST /api/runs/88/confirm": (req) => {
      confirmCalledWith = req;
      return jsonResponse({
        run_id: 88,
        status: "completed",
        answer: "Ticket APX-101 has been successfully escalated to the Urgent IT Queue.",
      });
    },
  });

  expect(await screen.findByText(/I'm Pip, your ApexCare/i)).toBeInTheDocument();

  const textarea = screen.getByPlaceholderText(/Ask Pip any policy question/i);
  await userEvent.type(textarea, "Escalate ticket APX-101 due to database outage");
  await userEvent.click(screen.getByRole("button", { name: /^send$/i }));

  // Verify HITL escalation card is visible
  expect(await screen.findByText(/Escalation Requires Approval/i)).toBeInTheDocument();
  expect(await screen.findByText(/Critical database connection failure affecting company operations/i)).toBeInTheDocument();
  expect(screen.getByText("APX-101")).toBeInTheDocument();
  expect(screen.getByText("urgent")).toBeInTheDocument();

  // Verify there is NO draft text input or draft action displayed
  expect(screen.queryByText(/draft_reply/i)).not.toBeInTheDocument();

  // Approve the escalation
  const approveBtn = screen.getByRole("button", { name: /approve & escalate/i });
  await userEvent.click(approveBtn);

  // Verify approval post and follow up message
  expect(await screen.findByText(/Escalation Approved & Executed/i)).toBeInTheDocument();
  expect(await screen.findByText(/Ticket APX-101 has been successfully escalated/i)).toBeInTheDocument();
});
