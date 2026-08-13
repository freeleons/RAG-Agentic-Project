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
  { id: 1, requester_name: "Dave", requester_email: "dave@test.com", title: "VPN ticket", description: "VPN issue", status: "open", priority: "medium", category: "IT Support", ticket_number: "T-101", sla_minutes_remaining: 30, created_at: "2026-08-03T00:00:00" },
  { id: 2, requester_name: "Bob", requester_email: "bob@test.com", title: "Refund question", description: "Refund issue", status: "open", priority: "medium", category: "HR & Benefits", ticket_number: "T-102", sla_minutes_remaining: 45, created_at: "2026-08-03T00:00:00" }
];

function renderAuthed() {
  localStorage.setItem("apexcare_token", "jwt-123");
  stubFetch({
    "GET /api/auth/me": () => jsonResponse({ id: 1, email: "me@test.com", full_name: "Alexandra Vance", department: "HR Operations", role_title: "Lead Support Specialist" }),
    "GET /api/tickets": () => jsonResponse(TICKETS),
  });
  return render(<App />);
}

test("lists the user's tickets", async () => {
  renderAuthed();
  expect((await screen.findAllByText("VPN ticket")).length).toBeGreaterThan(0);
  expect(screen.getByText("Refund question")).toBeInTheDocument();
});

test("new ticket creates and displays it", async () => {
  stubFetch({
    "GET /api/auth/me": () => jsonResponse({ id: 1, email: "me@test.com", full_name: "Alexandra Vance", department: "HR Operations", role_title: "Lead Support Specialist" }),
    "GET /api/tickets": () => jsonResponse([]),
    "POST /api/tickets": () => jsonResponse({ id: 5, requester_name: "Self", requester_email: "me@test.com", title: "New ticket", description: "Fresh issue", status: "open", priority: "medium", category: "IT Support", ticket_number: "T-105", sla_minutes_remaining: 60, created_at: "2026-08-03T00:00:00" }, 201),
  });
  localStorage.setItem("apexcare_token", "jwt-123");
  render(<App />);
  await userEvent.click(
    await screen.findByRole("button", { name: /\+ Create Ticket/i })
  );
  await userEvent.type(screen.getByPlaceholderText(/FSA rollover/i), "New ticket");
  await userEvent.type(screen.getByPlaceholderText(/Detail the employee/i), "Fresh issue");
  await userEvent.click(screen.getByRole("button", { name: /^Create Ticket$/i }));
  expect((await screen.findAllByText("New ticket")).length).toBeGreaterThan(0);
});

test("logout returns to the auth screen", async () => {
  renderAuthed();
  await userEvent.click(await screen.findByRole("button", { name: /logout/i }));
  expect(await screen.findByRole("tab", { name: /register profile/i })).toBeInTheDocument();
  expect(localStorage.getItem("apexcare_token")).toBeNull();
});
