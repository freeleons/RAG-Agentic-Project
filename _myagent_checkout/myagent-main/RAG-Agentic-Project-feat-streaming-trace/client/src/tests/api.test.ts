import { afterEach, expect, test, vi } from "vitest";
import { api, setOnUnauthorized, setToken } from "../api";
import { jsonResponse, stubFetch } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  setToken(null);
  setOnUnauthorized(null);
});

test("login posts credentials and returns the token", async () => {
  const fetchMock = stubFetch({
    "POST /api/auth/login": () => jsonResponse({ token: "jwt-123" }),
  });
  const result = await api.login("a@b.com", "password123");
  expect(result).toEqual({ token: "jwt-123" });
  const init = fetchMock.mock.calls[0][1]!;
  expect(JSON.parse(init.body as string)).toEqual({
    email: "a@b.com",
    password: "password123",
  });
});

test("requests carry the bearer token once set", async () => {
  const fetchMock = stubFetch({
    "GET /api/conversations": () => jsonResponse([]),
  });
  setToken("jwt-123");
  await api.listConversations();
  const headers = fetchMock.mock.calls[0][1]!.headers as Record<string, string>;
  expect(headers["Authorization"]).toBe("Bearer jwt-123");
});

test("error responses throw ApiError with the server message", async () => {
  stubFetch({
    "POST /api/auth/login": () => jsonResponse({ error: "invalid email or password" }, 401),
  });
  await expect(api.login("a@b.com", "wrong")).rejects.toThrowError(
    "invalid email or password"
  );
  await expect(api.login("a@b.com", "wrong")).rejects.toMatchObject({
    status: 401,
  });
});

test("401 triggers the onUnauthorized handler", async () => {
  stubFetch({
    "GET /api/conversations": () => jsonResponse({ error: "invalid or expired token" }, 401),
  });
  const handler = vi.fn();
  setOnUnauthorized(handler);
  await expect(api.listConversations()).rejects.toThrow();
  expect(handler).toHaveBeenCalledOnce();
});

test("confirmRun posts the approved boolean", async () => {
  const fetchMock = stubFetch({
    "POST /api/runs/7/confirm": () =>
      jsonResponse({ run_id: 7, status: "completed", answer: "done", trace: [] }),
  });
  await api.confirmRun(7, false);
  expect(JSON.parse(fetchMock.mock.calls[0][1]!.body as string)).toEqual({
    approved: false,
  });
});

test("listRuns builds the query string and omits empty filters", async () => {
  const fetchMock = stubFetch({
    "GET /api/runs?status=failed&date_from=2026-08-01&page=2": () =>
      jsonResponse({ runs: [], total: 0, page: 2, per_page: 20 }),
  });
  await api.listRuns({ status: "failed", dateFrom: "2026-08-01", page: 2 });
  expect(fetchMock).toHaveBeenCalledOnce();
});

test("getRunStats never sends page", async () => {
  stubFetch({
    "GET /api/runs/stats?status=failed": () =>
      jsonResponse({
        total_runs: 0, by_status: {}, success_rate: null, avg_steps: null,
        avg_latency_ms: null, total_prompt_tokens: 0, total_completion_tokens: 0,
        tool_usage: {}, runs_per_day: [], latency_buckets: [],
      }),
  });
  await api.getRunStats({ status: "failed", page: 3 });
});
