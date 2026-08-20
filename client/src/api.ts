import type {
  Conversation,
  ConversationHistory,
  RunDetail,
  RunFilters,
  RunOutcome,
  RunsPage,
  RunStats,
  Ticket,
  TicketFilters,
  KnowledgeDocument,
  UserProfile,
  AgentRun,
} from "./types";

export type {
  Conversation,
  ConversationHistory,
  RunDetail,
  RunFilters,
  RunOutcome,
  RunsPage,
  RunStats,
  Ticket,
  TicketFilters,
  KnowledgeDocument,
  UserProfile,
  AgentRun,
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let token: string | null = null;
let onUnauthorized: (() => void) | null = null;

export function setToken(t: string | null) {
  token = t;
}

export function setOnUnauthorized(handler: (() => void) | null) {
  onUnauthorized = handler;
}


async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  const activeToken = token || localStorage.getItem("apexcare_token");
  if (activeToken) headers["Authorization"] = `Bearer ${activeToken}`;
  const resp = await fetch(path, { ...options, headers });
  let body: unknown = null;
  try {
    body = await resp.json();
  } catch {
    body = null;
  }
  if (!resp.ok) {
    if (resp.status === 401 && onUnauthorized) onUnauthorized();
    const message =
      body && typeof body === "object" && "error" in body
        ? String((body as { error: unknown }).error)
        : `HTTP ${resp.status}`;
    throw new ApiError(resp.status, message);
  }
  return body as T;
}

function runQuery(filters: RunFilters, includePage: boolean): string {
  const p = new URLSearchParams();
  if (filters.status) p.set("status", filters.status);
  if (filters.conversationId) p.set("conversation_id", String(filters.conversationId));
  if (filters.dateFrom) p.set("date_from", filters.dateFrom);
  if (filters.dateTo) p.set("date_to", filters.dateTo);
  if (filters.userEmail) p.set("user_email", filters.userEmail);
  if (includePage && filters.page) p.set("page", String(filters.page));
  const s = p.toString();
  return s ? `?${s}` : "";
}

// Individual named exports for Tailwind components
export async function login(email: string, password: string): Promise<{ token: string; user: UserProfile }> {
  const data = await apiFetch<{ token: string; id: number; email: string; full_name: string; department: string; role_title: string; is_admin?: boolean }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  const user: UserProfile = {
    id: data.id,
    email: data.email,
    full_name: data.full_name,
    department: data.department,
    role_title: data.role_title,
    is_admin: data.is_admin,
  };
  return { token: data.token, user };
}

export async function register(data: {
  email: string;
  password: string;
  full_name: string;
  department: string;
  role_title: string;
}): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getCurrentUser(): Promise<UserProfile> {
  return apiFetch<UserProfile>("/api/auth/me");
}

export async function fetchTickets(params?: {
  status?: string;
  priority?: string;
  category?: string;
  q?: string;
}): Promise<Ticket[]> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.priority) query.set("priority", params.priority);
  if (params?.category) query.set("category", params.category);
  if (params?.q) query.set("q", params.q);

  const qs = query.toString();
  return apiFetch<Ticket[]>(`/api/tickets${qs ? `?${qs}` : ""}`);
}



export async function updateTicket(ticketId: number, updates: Partial<Ticket>): Promise<Ticket> {
  return apiFetch<Ticket>(`/api/tickets/${ticketId}`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}

export async function reseedTickets(): Promise<Ticket[]> {
  return apiFetch<Ticket[]>("/api/tickets/reset", {
    method: "POST",
  });
}

export async function triageTicket(ticketId: number, options?: RequestInit): Promise<{
  ticket: Ticket;
  run: AgentRun;
  conversation_id: number;
}> {
  return apiFetch<{ ticket: Ticket; run: AgentRun; conversation_id: number }>(`/api/tickets/${ticketId}/triage`, {
    method: "POST",
    ...options
  });
}

export async function approvePendingAction(runId: number): Promise<AgentRun> {
  return apiFetch<AgentRun>(`/api/runs/${runId}/approve`, {
    method: "POST",
    body: JSON.stringify({ approved: true }),
  });
}

export async function rejectPendingAction(runId: number): Promise<AgentRun> {
  return apiFetch<AgentRun>(`/api/runs/${runId}/reject`, {
    method: "POST",
    body: JSON.stringify({ approved: false }),
  });
}

export async function fetchRunDetails(runId: number): Promise<{ run: any; steps: any[] }> {
  return apiFetch<{ run: any; steps: any[] }>(`/api/runs/${runId}`);
}

export async function fetchAllRunAudits(): Promise<any[]> {
  const res = await apiFetch<{ runs: any[] }>("/api/runs");
  return res.runs || [];
}

export async function fetchRunStats(): Promise<any> {
  return apiFetch<any>("/api/runs/stats");
}

export async function fetchKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
  return apiFetch<KnowledgeDocument[]>("/api/knowledge-base");
}

export async function fetchKnowledgeDocumentBlob(filename: string): Promise<Blob> {
  const activeToken = token || localStorage.getItem("apexcare_token");
  const headers: Record<string, string> = {};
  if (activeToken) headers["Authorization"] = `Bearer ${activeToken}`;
  const resp = await fetch(`/api/knowledge-base/file/${encodeURIComponent(filename)}`, { headers });
  if (!resp.ok) {
    if (resp.status === 401 && onUnauthorized) onUnauthorized();
    throw new ApiError(resp.status, `Failed to load document (${resp.status})`);
  }
  return await resp.blob();
}

// Default export api object for legacy/MUI components
export const api = {
  register: (email: string, password: string) => register({ email, password, full_name: "", department: "", role_title: "" }),
  login: async (email: string, password: string) => {
    const res = await login(email, password);
    return { token: res.token, email: res.user.email, is_admin: res.user.is_admin };
  },
  listConversations: (q?: string) =>
    apiFetch<Conversation[]>(
      q ? `/api/conversations?q=${encodeURIComponent(q)}` : "/api/conversations"
    ),
  createConversation: (title?: string) =>
    apiFetch<{ id: number; title: string }>("/api/conversations", {
      method: "POST",
      body: JSON.stringify(title ? { title } : {}),
    }),
  deleteConversation: (convId: number) =>
    apiFetch<{ success: boolean }>(`/api/conversations/${convId}`, {
      method: "DELETE",
    }),
  updateConversation: (convId: number, title: string) =>
    apiFetch<{ id: number; title: string }>(`/api/conversations/${convId}`, {
      method: "PATCH",
      body: JSON.stringify({ title }),
    }),
  sendMessage: (convId: number, content: string, signal?: AbortSignal) =>
    apiFetch<RunOutcome>(`/api/conversations/${convId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
      signal,
    }),
  getHistory: (convId: number) =>
    apiFetch<ConversationHistory>(`/api/conversations/${convId}/messages`),
  confirmRun: (runId: number, approved: boolean, signal?: AbortSignal) =>
    apiFetch<RunOutcome>(`/api/runs/${runId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ approved }),
      signal,
    }),
  getRun: (runId: number) => apiFetch<RunDetail>(`/api/runs/${runId}`),
  listRuns: (filters: RunFilters) =>
    apiFetch<RunsPage>(`/api/runs${runQuery(filters, true)}`),
  getRunStats: (filters: RunFilters) =>
    apiFetch<RunStats>(`/api/runs/stats${runQuery(filters, false)}`),
  getTickets: (filters?: TicketFilters) => {
    const params = new URLSearchParams();
    if (filters?.status) params.append("status", filters.status);
    if (filters?.priority) params.append("priority", filters.priority);
    if (filters?.category) params.append("category", filters.category);
    if (filters?.q) params.append("q", filters.q);
    const qs = params.toString();
    return apiFetch<Ticket[]>(qs ? `/api/tickets?${qs}` : "/api/tickets");
  },
  updateTicket: (ticketId: number, data: Partial<Ticket>) =>
    updateTicket(ticketId, data),
};

