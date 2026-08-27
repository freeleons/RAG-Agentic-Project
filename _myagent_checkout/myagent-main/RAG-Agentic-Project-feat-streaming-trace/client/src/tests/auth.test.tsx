import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import App from "../App";
import { jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

function renderApp() {
  return render(<App />);
}

test("logging in stores the token and shows the app", async () => {
  localStorage.clear();
  stubFetch({
    "POST /api/auth/login": () => jsonResponse({ token: "jwt-123", id: 1, email: "a@b.com", full_name: "Test User", department: "HR Operations", role_title: "Lead Support Specialist" }),
    "GET /api/auth/me": () => jsonResponse({ id: 1, email: "a@b.com", full_name: "Test User", department: "HR Operations", role_title: "Lead Support Specialist" }),
    "GET /api/tickets": () => jsonResponse([]),
  });
  renderApp();
  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/password/i);
  await userEvent.clear(emailInput);
  await userEvent.type(emailInput, "a@b.com");
  await userEvent.clear(passwordInput);
  await userEvent.type(passwordInput, "password123");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByRole("button", { name: /logout/i })).toBeInTheDocument();
  expect(localStorage.getItem("apexcare_token")).toBe("jwt-123");
});

test("register auto-logs-in", async () => {
  localStorage.clear();
  stubFetch({
    "POST /api/auth/register": () => jsonResponse({ id: 1, email: "a@b.com" }, 201),
    "POST /api/auth/login": () => jsonResponse({ token: "jwt-456", id: 1, email: "a@b.com", full_name: "Test User", department: "HR Operations", role_title: "Lead Support Specialist" }),
    "GET /api/auth/me": () => jsonResponse({ id: 1, email: "a@b.com", full_name: "Test User", department: "HR Operations", role_title: "Lead Support Specialist" }),
    "GET /api/tickets": () => jsonResponse([]),
  });
  renderApp();
  await userEvent.click(screen.getByRole("tab", { name: /register profile/i }));
  
  const nameInput = screen.getByLabelText(/full name/i);
  const emailInput = screen.getByLabelText(/work email/i);
  const passwordInput = screen.getByLabelText(/password/i);
  
  await userEvent.clear(nameInput);
  await userEvent.type(nameInput, "Test User");
  await userEvent.clear(emailInput);
  await userEvent.type(emailInput, "a@b.com");
  await userEvent.clear(passwordInput);
  await userEvent.type(passwordInput, "password123");
  await userEvent.click(screen.getByRole("button", { name: /create account/i }));
  expect(await screen.findByRole("button", { name: /logout/i })).toBeInTheDocument();
  expect(localStorage.getItem("apexcare_token")).toBe("jwt-456");
});

test("failed login shows the server error", async () => {
  localStorage.clear();
  stubFetch({
    "POST /api/auth/login": () =>
      jsonResponse({ error: "invalid email or password" }, 401),
  });
  renderApp();
  const emailInput = screen.getByLabelText(/email/i);
  const passwordInput = screen.getByLabelText(/password/i);
  await userEvent.clear(emailInput);
  await userEvent.type(emailInput, "a@b.com");
  await userEvent.clear(passwordInput);
  await userEvent.type(passwordInput, "wrongwrong");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
});

test("a stored token skips the auth screen", async () => {
  localStorage.setItem("apexcare_token", "jwt-789");
  stubFetch({ 
    "GET /api/auth/me": () => jsonResponse({ id: 1, email: "a@b.com", full_name: "Test User", department: "HR Operations", role_title: "Lead Support Specialist" }),
    "GET /api/tickets": () => jsonResponse([]) 
  });
  renderApp();
  expect(await screen.findByRole("button", { name: /logout/i })).toBeInTheDocument();
});
