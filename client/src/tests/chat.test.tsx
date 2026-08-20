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

test("draft with pip inputs message into pip chat, states insertion, and automatically inserts draft into reply box", async () => {
  const draftReplyText = "Hi Dave,\n\nPlease reset your VPN token at vpn.apexcare.tech.\n\nBest regards,\nHR Support Team";
  renderAuthed({
    "POST /api/chat": () => jsonResponse({
      reply: `I have inserted this response in the reply chat:\n\n"${draftReplyText}"`,
      draft_reply: draftReplyText,
      ticket_id: 1,
      run_id: 101,
    }),
    "GET /api/runs/101": () => jsonResponse({ run: { id: 101, status: "completed" }, steps: [] }),
    "GET /api/runs?page=1&per_page=1": () => jsonResponse({ runs: [] }),
  });
  
  await userEvent.click((await screen.findAllByText("VPN ticket"))[0]);
  
  const draftBtn = await screen.findByRole("button", { name: /draft with pip/i });
  await userEvent.click(draftBtn);
  
  // The drafted reply should be written as HR rep (e.g. "HR Support Team", not "I am Pip")
  expect((await screen.findAllByText(/HR Support Team/i)).length).toBeGreaterThanOrEqual(1);

  // The reply textarea in the ticket workbench should automatically contain the drafted response without insertion preamble
  await waitFor(() => {
    const replyTextarea = screen.getByPlaceholderText(/Write a reply to Dave or click "Draft with Pip"/i) as HTMLTextAreaElement;
    expect(replyTextarea.value).toContain("Hi Dave");
    expect(replyTextarea.value).toContain("Best regards,\nHR Support Team");
    expect(replyTextarea.value).not.toContain("I have inserted this response in the reply chat");
  });

  // Copy buttons should be present on Pip's replies
  const copyButtons = screen.getAllByRole("button", { name: /copy reply/i });
  expect(copyButtons.length).toBeGreaterThanOrEqual(2);
});

test("pip chat handles policy draft requests and inserts preset draft into reply chat", async () => {
  const sampleDraft =
    "Hi Dave,\n\n" +
    "Thank you for reaching out to us regarding your FSA inquiry. " +
    "According to our WEX Healthcare FSA policy, up to $640 of unused funds may be rolled over into the next plan year.\n\n" +
    "Please let us know if you need any additional assistance.\n\n" +
    "Best regards,\nHR Support Team";

  renderAuthed({
    "POST /api/chat": () =>
      jsonResponse({
        reply: sampleDraft,
        draft_reply: sampleDraft,
        ticket_id: 1,
        status: "completed",
        run_id: 88,
      }),
    "GET /api/runs/88": () => jsonResponse({ run: { id: 88, status: "completed" }, steps: [] }),
    "GET /api/runs?page=1&per_page=1": () => jsonResponse({ runs: [] }),
  });

  expect(await screen.findByText(/I'm Pip, your ApexCare/i)).toBeInTheDocument();

  const textarea = screen.getByPlaceholderText(/Ask Pip any policy question/i);
  await userEvent.type(textarea, "Draft a reply to Dave about his FSA rollover limit");
  await userEvent.click(screen.getByRole("button", { name: /^send$/i }));

  // Verify Pip chat renders the clean draft
  expect((await screen.findAllByText(/WEX Healthcare FSA/i)).length).toBeGreaterThanOrEqual(1);

  // Verify workbench textarea receives the draft reply
  await waitFor(() => {
    const replyTextarea = screen.getByPlaceholderText(/Write a reply to Dave or click "Draft with Pip"/i) as HTMLTextAreaElement;
    expect(replyTextarea.value).toContain("Hi Dave");
    expect(replyTextarea.value).toContain("$640 of unused funds");
    expect(replyTextarea.value).toContain("Best regards,\nHR Support Team");
  });
});

test("pip chat cleans raw JSON tool output and inserts preset draft into reply chat", async () => {
  const rawToolOutput = JSON.stringify({
    name: "draft_replies",
    parameters: {
      ticket_id: "APX-1045",
      reply: {
        body: "Hi Elena,\n\nThank you for reaching out to us regarding your upcoming medical procedure. Our STD plan provides coverage for 60% to 80% of your salary.\n\nBest regards,\nHR Support Team",
        status: "applied",
      },
    },
  });

  renderAuthed({
    "POST /api/chat": () => jsonResponse({
      reply: rawToolOutput,
      run_id: 202,
    }),
    "GET /api/runs/202": () => jsonResponse({ run: { id: 202, status: "completed" }, steps: [] }),
    "GET /api/runs?page=1&per_page=1": () => jsonResponse({ runs: [] }),
  });

  expect(await screen.findByText(/I'm Pip, your ApexCare/i)).toBeInTheDocument();

  const textarea = screen.getByPlaceholderText(/Ask Pip any policy question/i);
  await userEvent.type(textarea, "Draft a reply to Elena for APX-1045");
  await userEvent.click(screen.getByRole("button", { name: /^send$/i }));

  // Verify raw JSON schema keywords are NOT rendered
  expect((await screen.findAllByText(/Hi Elena/i)).length).toBeGreaterThanOrEqual(1);
  expect(screen.queryByText(/draft_replies/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/parameters/i)).not.toBeInTheDocument();
  expect(screen.queryByText(/I have inserted this response in the reply chat/i)).not.toBeInTheDocument();

  // Verify workbench textarea receives the cleaned preset body
  await waitFor(() => {
    const replyTextarea = screen.getByPlaceholderText(/Write a reply to Dave or click "Draft with Pip"/i) as HTMLTextAreaElement;
    expect(replyTextarea.value).toContain("Hi Elena");
    expect(replyTextarea.value).toContain("Best regards,\nHR Support Team");
    expect(replyTextarea.value).not.toContain("I have inserted this response in the reply chat");
  });
});

test("pip chat pre-renders knowledge search query and does NOT insert draft into workbench", async () => {
  renderAuthed({
    "POST /api/chat": () => jsonResponse({
      reply: "The Healthcare FSA Rollover Limit is up to $640 of unused funds from the current plan year.",
      status: "completed",
      run_id: 303,
    }),
    "GET /api/runs/303": () => jsonResponse({ run: { id: 303, status: "completed" }, steps: [] }),
    "GET /api/runs?page=1&per_page=1": () => jsonResponse({ runs: [] }),
  });

  expect(await screen.findByText(/I'm Pip, your ApexCare/i)).toBeInTheDocument();

  const textarea = screen.getByPlaceholderText(/Ask Pip any policy question/i);
  await userEvent.type(textarea, "What is the FSA rollover limit?");
  await userEvent.click(screen.getByRole("button", { name: /^send$/i }));

  // Pip Chat displays the knowledge answer
  expect(await screen.findByText(/Healthcare FSA Rollover Limit is up to \$640/i)).toBeInTheDocument();

  // Reply textarea in ticket workbench remains empty / untouched
  const replyTextarea = screen.getByPlaceholderText(/Write a reply to Dave or click "Draft with Pip"/i) as HTMLTextAreaElement;
  expect(replyTextarea.value).toBe("");
});
