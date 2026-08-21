export interface UserProfile {
  id: number;
  email: string;
  full_name: string;
  department: string;
  role_title: string;
  is_admin?: boolean;
}

export interface Conversation {
  id: number;
  title: string;
  created_at: string;
}

export interface Ticket {
  id: number;
  ticket_number: string;
  user_id: number;
  requester_name: string;
  requester_email: string;
  requester_department: string;
  title: string;
  description: string;
  status: "open" | "in_triage" | "draft_pending" | "escalated" | "resolved" | string;
  priority: "low" | "medium" | "high" | "urgent" | string;
  category: "HR & Benefits" | "IT Support" | "Billing & Expenses" | "General" | string;
  channel?: "Workday Portal" | "Slack HR Connect" | "Email" | "Helpdesk" | string;
  sla_minutes_remaining?: number;
  draft_reply?: string | null;
  draft_confidence?: number;
  escalation_reason?: string | null;
  resolution_notes?: string | null;
  replies?: { id: string; sender: string; text: string; timestamp: string }[];
  created_at: string;
  updated_at?: string;
}

export interface TicketFilters {
  status?: string;
  priority?: string;
  category?: string;
  q?: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface TraceStep {
  seq: number;
  kind: "llm_call" | "tool_call" | string;
  tool_name: string | null;
  arguments: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  latency_ms: number | null;
  llm_messages?: unknown[] | null;
  span_id?: string | null;
}

export interface PendingAction {
  id: number;
  tool: string;
  arguments: Record<string, any>;
}

export interface RunOutcome {
  run_id: number;
  status: "completed" | "failed" | "declined" | "needs_confirmation" | string;
  answer?: string;
  pending_action?: PendingAction;
  trace: TraceStep[];
  conversation_title?: string;
}

export interface RunDetail {
  id: number;
  status: string;
  model: string | null;
  provider?: string | null;
  total_latency_ms: number | null;
  trace_id?: string | null;
  created_at: string;
  steps: TraceStep[];
  pending_action?: PendingAction;
}

export interface RunSummary {
  id: number;
  user_message_id: number;
  status: string;
  step_count?: number;
  total_latency_ms?: number | null;
}

export interface ConversationHistory {
  messages: ChatMessage[];
  runs: RunSummary[];
}

export interface UiMessage {
  role: "user" | "assistant";
  content: string;
  runId?: number;
  stepCount?: number;
  totalLatencyMs?: number | null;
  awaitingConfirmation?: boolean;
}

export interface PanelState {
  runId: number;
  status: string;
  steps: TraceStep[];
  pendingAction?: PendingAction;
  totalLatencyMs?: number | null;
  traceId?: string | null;
}

export interface RunFilters {
  status?: string;
  conversationId?: number;
  dateFrom?: string;
  dateTo?: string;
  userEmail?: string;
  page?: number;
}

export interface RunListItem {
  id: number;
  status: string;
  goal: string;
  conversation_id: number;
  conversation_title: string;
  model: string | null;
  provider?: string | null;
  step_count: number;
  total_latency_ms: number | null;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
  user_email?: string;
}

export interface RunsPage {
  runs: RunListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface DayCounts {
  date: string;
  completed: number;
  failed: number;
  declined: number;
  needs_confirmation: number;
}

export interface LatencyBucket {
  label: string;
  count: number;
}

export interface RunStats {
  total_runs: number;
  by_status: Record<string, number>;
  success_rate: number | null;
  avg_steps: number | null;
  avg_latency_ms: number | null;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  tool_usage: Record<string, number>;
  runs_per_day: DayCounts[];
  latency_buckets: LatencyBucket[];
}

export interface AgentRun {
  run_id: number;
  status: "running" | "completed" | "needs_confirmation" | "failed" | "declined";
  answer?: string;
  pending_action?: PendingAction;
  steps?: TraceStep[];
  total_latency_ms?: number;
}

export interface KnowledgeDocument {
  filename: string;
  title: string;
  category: string;
  size_bytes: number;
  content: string;
  file_type?: "pdf" | "markdown" | "text";
  mime_type?: string;
}

